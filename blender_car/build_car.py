#!/usr/bin/env python3
"""Procedural photoreal sports car + sunset road scene for Blender (bpy 4.x / 5.x).

Run with either:
    blender -b -P build_car.py -- --quality preview
    python build_car.py --quality final        (pip-installed `bpy`)

Everything (body loft, cabin, wheels, materials, lighting, camera) is generated
from code; no external assets or HDRIs are needed.
Units are metres. The car faces +X, its right side is -Y, up is +Z.
"""
import argparse
import math
import os
import sys

import bpy  # must come first: it puts bmesh/mathutils on sys.path
import bmesh
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
ap = argparse.ArgumentParser()
ap.add_argument("--quality", choices=["draft", "preview", "final"], default="preview")
ap.add_argument("--out", default=os.path.join(HERE, "car_render.png"))
ap.add_argument("--blend", default=os.path.join(HERE, "sports_car.blend"))
ap.add_argument("--no-render", action="store_true")
ap.add_argument("--sun", type=float, default=300.0, help="sun azimuth (deg): 0=+Y, 90=+X")
ap.add_argument("--sunel", type=float, default=3.5)
ap.add_argument("--exposure", type=float, default=-0.8)
ap.add_argument("--glow", default="5,0.05,0.45", help="bloom threshold,strength,size ; or off")
ap.add_argument("--cam", default="hero", choices=["hero", "side", "rear", "front", "wheel"])
ARGS = ap.parse_args(argv)

QUALITY = {
    "draft": dict(res=(640, 360), samples=24),
    "preview": dict(res=(1280, 720), samples=64),
    "final": dict(res=(1920, 1080), samples=320),
}[ARGS.quality]

# --------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------


def sgnpow(x, p):
    return np.sign(x) * np.abs(x) ** p


def pchip(xs, ys):
    """Monotone cubic interpolator (Fritsch-Carlson); smooth, no overshoot."""
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    h = np.diff(xs)
    d = np.diff(ys) / h
    m = np.zeros_like(ys)
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(xs) - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1 = 2 * h[i] + h[i - 1]
            w2 = h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        x = np.clip(x, xs[0], xs[-1])
        i = int(np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2))
        t = (x - xs[i]) / h[i]
        return ((2 * t**3 - 3 * t**2 + 1) * ys[i] + (t**3 - 2 * t**2 + t) * h[i] * m[i]
                + (-2 * t**3 + 3 * t**2) * ys[i + 1] + (t**3 - t**2) * h[i] * m[i + 1])

    return f


def link(ob, coll=None):
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def mesh_obj(name, verts, faces, edges=()):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], list(edges), [tuple(f) for f in faces])
    me.update()
    return link(bpy.data.objects.new(name, me))


def bm_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def smooth_by_angle(ob, deg=35.0):
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    thr = math.radians(deg)
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > thr)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()


def apply_mods(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)


def add_mod(ob, kind, **kw):
    m = ob.modifiers.new(kind.title(), kind)
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def assign(ob, material):
    ob.data.materials.clear()
    ob.data.materials.append(material)


def rot_y(v, ang):
    c, s = math.cos(ang), math.sin(ang)
    return Vector((v.x * c + v.z * s, v.y, -v.x * s + v.z * c))


# --------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------


class Mat:
    """Tiny node-graph helper."""

    def __init__(self, name):
        self.m = bpy.data.materials.new(name)
        self.m.use_nodes = True
        self.nt = self.m.node_tree
        self.nt.nodes.clear()
        self.out = self.n("ShaderNodeOutputMaterial")

    def n(self, kind, **kw):
        nd = self.nt.nodes.new(kind)
        for k, v in kw.items():
            setattr(nd, k, v)
        return nd

    def l(self, a, b):
        self.nt.links.new(a, b)

    def principled(self, **inputs):
        p = self.n("ShaderNodeBsdfPrincipled")
        for k, v in inputs.items():
            k = k.replace("_", " ")
            if k in p.inputs:
                p.inputs[k].default_value = v
        return p

    def finish(self, shader):
        self.l(shader.outputs[0], self.out.inputs["Surface"])
        return self.m


def mat_principled(name, color, rough=0.5, metal=0.0, **kw):
    M = Mat(name)
    p = M.principled(Base_Color=(*color, 1), Roughness=rough, Metallic=metal, **kw)
    return M.finish(p)


def mat_emission(name, color, strength):
    M = Mat(name)
    e = M.n("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = strength
    return M.finish(e)


def mat_glass(name, tint=(0.06, 0.07, 0.07), thin_ior=1.5):
    """Thin-walled window glass: reflective at grazing angles, tinted transparency."""
    M = Mat(name)
    fr = M.n("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = thin_ior
    tr = M.n("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (*tint, 1)
    gl = M.n("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.0
    gl.inputs["Color"].default_value = (1, 1, 1, 1)
    mix = M.n("ShaderNodeMixShader")
    M.l(fr.outputs[0], mix.inputs[0])
    M.l(tr.outputs[0], mix.inputs[1])
    M.l(gl.outputs[0], mix.inputs[2])
    return M.finish(mix)


def mat_car_paint(name="CarPaint", color=(0.36, 0.004, 0.010), masks=True):
    """Metallic base + clear coat, flake bump, orange-peel on the coat and a
    pixel-exact black lower-body mask driven by object-space Z (no geometry needed)."""
    M = Mat(name)
    tc = M.n("ShaderNodeTexCoord")
    sep = M.n("ShaderNodeSeparateXYZ")
    M.l(tc.outputs["Object"], sep.inputs[0])

    # metallic flakes
    fl = M.n("ShaderNodeTexVoronoi")
    fl.inputs["Scale"].default_value = 1400
    fl.inputs["Randomness"].default_value = 1.0
    M.l(tc.outputs["Object"], fl.inputs["Vector"])
    flb = M.n("ShaderNodeBump")
    flb.inputs["Strength"].default_value = 0.12
    flb.inputs["Distance"].default_value = 0.0003
    M.l(fl.outputs["Distance"], flb.inputs["Height"])

    # orange peel on the coat
    pe = M.n("ShaderNodeTexNoise")
    pe.inputs["Scale"].default_value = 260
    pe.inputs["Detail"].default_value = 3
    M.l(tc.outputs["Object"], pe.inputs["Vector"])
    peb = M.n("ShaderNodeBump")
    peb.inputs["Strength"].default_value = 0.05
    peb.inputs["Distance"].default_value = 0.0004
    M.l(pe.outputs["Fac"], peb.inputs["Height"])

    paint = M.principled(Base_Color=(*color, 1), Metallic=0.55, Roughness=0.30,
                         Coat_Weight=1.0, Coat_Roughness=0.015, Coat_IOR=1.5)
    M.l(flb.outputs["Normal"], paint.inputs["Normal"])
    M.l(peb.outputs["Normal"], paint.inputs["Coat Normal"])
    if not masks:
        return M.finish(paint)

    # lower body (sills, bumpers): satin black plastic, higher at nose / tail
    black = M.principled(Base_Color=(0.012, 0.012, 0.013, 1), Roughness=0.42,
                         Specular_IOR_Level=0.5)
    thr = M.n("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")      # nose
    thr.inputs["From Min"].default_value = 2.05
    thr.inputs["From Max"].default_value = 2.26
    thr.inputs["To Min"].default_value = 0.215
    thr.inputs["To Max"].default_value = 0.275
    M.l(sep.outputs["X"], thr.inputs["Value"])
    thr2 = M.n("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")     # tail: tall black bumper
    thr2.inputs["From Min"].default_value = -1.86
    thr2.inputs["From Max"].default_value = -2.12
    thr2.inputs["To Min"].default_value = 0.215
    thr2.inputs["To Max"].default_value = 0.50
    M.l(sep.outputs["X"], thr2.inputs["Value"])
    mx = M.n("ShaderNodeMath", operation="MAXIMUM")
    M.l(thr.outputs["Result"], mx.inputs[0])
    M.l(thr2.outputs["Result"], mx.inputs[1])
    lt = M.n("ShaderNodeMath", operation="LESS_THAN")
    M.l(sep.outputs["Z"], lt.inputs[0])
    M.l(mx.outputs[0], lt.inputs[1])
    mix = M.n("ShaderNodeMixShader")
    M.l(lt.outputs[0], mix.inputs[0])
    M.l(paint.outputs[0], mix.inputs[1])
    M.l(black.outputs[0], mix.inputs[2])
    # (the cabin cavity walls get the dark liner from the boolean cutter, so no interior mask here)
    return M.finish(mix)


def mat_tire():
    M = Mat("Tire")
    tc = M.n("ShaderNodeTexCoord")
    nz = M.n("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 400
    nz.inputs["Detail"].default_value = 6
    M.l(tc.outputs["Object"], nz.inputs["Vector"])
    bp = M.n("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.35
    bp.inputs["Distance"].default_value = 0.0008
    M.l(nz.outputs["Fac"], bp.inputs["Height"])
    p = M.principled(Base_Color=(0.018, 0.018, 0.019, 1), Roughness=0.78,
                     Specular_IOR_Level=0.3)
    M.l(bp.outputs["Normal"], p.inputs["Normal"])
    return M.finish(p)


def mat_carbon():
    M = Mat("Carbon")
    tc = M.n("ShaderNodeTexCoord")
    ck = M.n("ShaderNodeTexChecker")
    ck.inputs["Scale"].default_value = 260
    ck.inputs["Color1"].default_value = (0.004, 0.004, 0.005, 1)
    ck.inputs["Color2"].default_value = (0.020, 0.020, 0.022, 1)
    M.l(tc.outputs["Object"], ck.inputs["Vector"])
    bp = M.n("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.2
    bp.inputs["Distance"].default_value = 0.0004
    M.l(ck.outputs["Fac"], bp.inputs["Height"])
    p = M.principled(Roughness=0.25, Coat_Weight=1.0, Coat_Roughness=0.03, Anisotropic=0.5)
    M.l(ck.outputs["Color"], p.inputs["Base Color"])
    M.l(bp.outputs["Normal"], p.inputs["Normal"])
    return M.finish(p)


def mat_asphalt():
    M = Mat("Asphalt")
    tc = M.n("ShaderNodeTexCoord")
    mp = M.n("ShaderNodeMapping")
    M.l(tc.outputs["Object"], mp.inputs["Vector"])
    # grain
    vo = M.n("ShaderNodeTexVoronoi")
    vo.inputs["Scale"].default_value = 900
    M.l(mp.outputs[0], vo.inputs["Vector"])
    nz = M.n("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 18
    nz.inputs["Detail"].default_value = 10
    M.l(mp.outputs[0], nz.inputs["Vector"])
    bump = M.n("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.01
    M.l(vo.outputs["Distance"], bump.inputs["Height"])
    # colour variation
    cr = M.n("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color = (0.020, 0.020, 0.021, 1)
    cr.color_ramp.elements[1].color = (0.075, 0.073, 0.072, 1)
    M.l(nz.outputs["Fac"], cr.inputs["Fac"])
    # patchy wetness -> low roughness reflective puddles
    wn = M.n("ShaderNodeTexNoise")
    wn.inputs["Scale"].default_value = 0.35
    wn.inputs["Detail"].default_value = 5
    M.l(mp.outputs[0], wn.inputs["Vector"])
    wr = M.n("ShaderNodeValToRGB")
    wr.color_ramp.elements[0].position = 0.55
    wr.color_ramp.elements[0].color = (0.82, 0.82, 0.82, 1)
    wr.color_ramp.elements[1].position = 0.62
    wr.color_ramp.elements[1].color = (0.10, 0.10, 0.10, 1)
    M.l(wn.outputs["Fac"], wr.inputs["Fac"])
    p = M.principled(Specular_IOR_Level=0.5)
    M.l(cr.outputs["Color"], p.inputs["Base Color"])
    M.l(wr.outputs["Color"], p.inputs["Roughness"])
    M.l(bump.outputs["Normal"], p.inputs["Normal"])
    return M.finish(p)


# --------------------------------------------------------------------------
# Geometry: lofted body + cabin
# --------------------------------------------------------------------------


def loft(name, stations, section_fn, M=44, taper=None, crown=None, tuck=None, scallop=None):
    """Loft closed superellipse cross-sections along X.

    section_fn(x) -> (half_width, z_bottom, z_top, n_top, n_bottom)
    taper(x) -> scale factor (0..1), or (plan, upper, lower) factors, so the ends round off.
    scallop(x) -> depth (m) of a concave sculpt pressed into the side at mid height.
    """
    verts = []
    for x in stations:
        W, zb, zt, nt, nb = section_fn(x)
        T = taper(x) if taper else 1.0
        if not isinstance(T, tuple):
            T = (T, T, T)
        Tw, Tt, Tb = T            # plan, upper-profile and lower-profile closing factors
        zc = 0.5 * (zb + zt)
        H0 = 0.5 * (zt - zb)
        W = W * Tw
        T = Tw
        for k in range(M):
            th = -math.pi / 2 + 2 * math.pi * k / M
            c, s = math.cos(th), math.sin(th)
            e = 2.0 / (nt if s > 0 else nb)
            y = float(W * sgnpow(c, e))
            z = float(zc + H0 * (Tt if s > 0 else Tb) * sgnpow(s, e))
            lo, hi = zc - H0 * Tb, zc + H0 * Tt
            zrel = (z - lo) / (hi - lo) if hi - lo > 1e-6 else 0.5
            if crown and s > 0:   # raise the outer top corners -> fenders stand above the hood
                z += crown(x) * T * (abs(y) / max(W, 1e-6)) ** 3
            if tuck:              # narrow the sills -> body tumblehome below the shoulder
                y *= 1.0 - tuck(x) * (1.0 - zrel) ** 2
            if scallop and abs(c) > 0.2:   # concave sculpt along the doors, fading out at top/bottom
                y -= math.copysign(scallop(x) * math.exp(-((zrel - 0.42) / 0.13) ** 2), y)
            verts.append((x, y, z))
    faces = []
    S = len(stations)
    for i in range(S - 1):
        for k in range(M):
            a, b = i * M + k, i * M + (k + 1) % M
            faces.append((a, b, b + M, a + M))
    # end caps: a single centre vertex fan (the pole sits on the nose / tail face)
    for i, sgn in ((0, 0), (S - 1, 1)):
        ring = [i * M + k for k in range(M)]
        cx = verts[ring[0]][0]
        cz = float(np.mean([verts[r][2] for r in ring]))
        verts.append((cx, 0.0, cz))
        cidx = len(verts) - 1
        for k in range(M):
            faces.append((ring[k], ring[(k + 1) % M], cidx))
    ob = mesh_obj(name, verts, faces)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


# --------------------------------------------------------------------------
# Car spec. Car frame: metres, +X forward, +Y left, +Z up, origin on the ground at mid-wheelbase.
# Proportions follow the front-engine GT class (published dimensions, quoted from memory, not
# re-checked in this session): Ferrari Roma 4656 / 1974 / 1301 / wb 2670, Aston Martin Vantage
# 4465 / 1942 / 1273 / 2704, Mercedes-AMG GT 4546 / 1939 / 1288 / 2630, Jaguar F-Type
# 4470 / 1923 / 1311 / 2622 (length / width / height / wheelbase, mm).
# --------------------------------------------------------------------------
WHEELBASE = 2.68
FRONT_X, REAR_X = WHEELBASE / 2, -WHEELBASE / 2
X_NOSE = FRONT_X + 0.98          # front overhang 0.98 m
X_TAIL = REAR_X - 0.89           # rear overhang 0.89 m  -> length 4.55 m
CAR_L = X_NOSE - X_TAIL
TRACK_F, TRACK_R = 1.66, 1.64    # tyre centre to tyre centre
TIRE_R = 0.345                   # 255/35 R20 front, 295/30 R20 rear (both ~0.343 m)
TIRE_W_F, TIRE_W_R = 0.255, 0.295
ARCH_R = 0.385
ROOF_Z = 1.285                   # overall height
COWL_X = 0.42                    # windscreen base (dash-to-axle 0.92 m: long-hood GT)

# --- body control lines (few, monotone keys; centreline unless noted) ---
_zt = pchip([X_TAIL, -2.17, -2.02, -1.70, -1.34, -0.80, 0.00, 0.42, 0.85, 1.34, 1.80, 2.12, X_NOSE],
            [0.915, 0.968, 0.966, 0.952, 0.932, 0.905, 0.890, 0.880, 0.845, 0.790, 0.715, 0.615, 0.505])
_zb = pchip([X_TAIL, -2.08, -1.85, -1.34, 0.00, 1.34, 1.95, 2.18, X_NOSE],
            [0.370, 0.280, 0.180, 0.130, 0.120, 0.130, 0.150, 0.185, 0.245])
_w = pchip([X_TAIL, -2.12, -1.85, -1.45, -1.05, -0.55, 0.00, 0.55, 1.00, 1.34, 1.72, 2.05, X_NOSE],
           [0.860, 0.925, 0.962, 0.972, 0.955, 0.918, 0.905, 0.908, 0.935, 0.957, 0.945, 0.910, 0.840])
# fender / haunch rise over the outer top corner and lower-body tumblehome
_crown = pchip([X_TAIL, -2.0, -1.40, -0.80, 0.0, 0.70, 1.34, 1.95, X_NOSE],
               [0.00, 0.022, 0.090, 0.030, 0.010, 0.030, 0.070, 0.045, 0.00])
_tuck = pchip([X_TAIL, -1.5, 0.0, 1.5, X_NOSE], [0.03, 0.055, 0.08, 0.055, 0.03])


def body_section(x):
    return _w(x), _zb(x), _zt(x), 3.7, 4.2


def _falloff(x, x0, x1, p):
    s = min(max((x - x0) / (x1 - x0), 0.0), 1.0)
    return max(1.0 - s**p, 1e-4) ** (1.0 / p)


def body_taper(x):
    """(plan, upper, lower) rounding of the ends. Tail: corners round off in plan over the last
    0.40 m, the deck edge closes only in the last 0.08 m (crisp lip) while the lower panel tucks
    forward over 0.45 m, so the tail face leans under instead of standing as a flat slab.
    Nose: hood rolls over softly, the chin closes late so the splitter area stays forward."""
    if x > 0:
        return (_falloff(x, 2.04, X_NOSE, 3.0), _falloff(x, 1.98, X_NOSE, 2.4),
                _falloff(x, 2.12, X_NOSE, 3.0))
    return (_falloff(x, -1.83, X_TAIL, 2.3), _falloff(x, -2.15, X_TAIL, 3.2),
            _falloff(x, -1.78, X_TAIL, 2.0))


# concave sculpt along the doors (catches a reflection line like a real side panel)
_scallop = pchip([-1.75, -1.2, -0.6, 0.2, 0.75, 1.1], [0.0, 0.012, 0.024, 0.024, 0.012, 0.0])


# --- greenhouse: one lofted canopy shared by the render and the Roblox export ---
GH_X0, GH_X1 = -1.74, COWL_X + 0.03
_rz = pchip([GH_X0, -1.45, -1.15, -0.80, -0.50, -0.22, 0.05, 0.25, GH_X1],
            [0.900, 1.010, 1.125, 1.255, 1.285, 1.262, 1.135, 1.010, 0.850])
_rw = pchip([GH_X0, -1.50, -1.20, -0.80, -0.30, 0.10, GH_X1],
            [0.420, 0.600, 0.725, 0.780, 0.790, 0.765, 0.640])
BELT = 0.905         # side-window sill
XF, XR = -0.22, -0.80  # roof panel: windscreen header / rear-glass top
RY = 0.565           # roof panel half width = top edge of the side windows
PW = 0.036           # half width of the A-pillars and roof rails
TRIM = 0.020         # black frame band inside every glass edge
A1, A2 = (COWL_X - 0.04, 0.655), (XF, RY)   # A-pillar line in plan: screen base corner -> roof corner
C1 = (-1.28, BELT)   # side-window rear edge starts here and leans back up to the roof


def cabin_section(x):
    return _rw(x), 0.55, _rz(x), 2.5, 3.0


def cabin_point(x, th):
    W, zt, zb = _rw(x), _rz(x), 0.55
    c, s = math.cos(th), math.sin(th)
    e = 2.0 / (2.5 if s > 0 else 3.0)
    y = W * math.copysign(abs(c) ** e, c)
    zc, H = 0.5 * (zb + zt), 0.5 * (zt - zb)
    return (x, y, zc + H * math.copysign(abs(s) ** e, s))


def plan_normal(p, q, toward):
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy)
    n = (dy / L, -dx / L)
    if n[0] * toward[0] + n[1] * toward[1] < 0:
        n = (-n[0], -n[1])
    return n


def build_body():
    u = np.linspace(0, 1, 72)
    st = (X_TAIL + CAR_L * (0.5 - 0.5 * np.cos(np.pi * u))).tolist()
    body = loft("Body", st, body_section, M=48, taper=body_taper, crown=_crown, tuck=_tuck,
                scallop=_scallop)
    add_mod(body, "SUBSURF", levels=2, render_levels=2)
    apply_mods(body)

    body.data.materials.append(PAINT)
    liner = mat_principled("ArchLiner", (0.008, 0.008, 0.008), 0.9)
    cutters = []
    # cabin cavity: open the deck under the glass so the interior is a real, hollow space
    u_ = np.linspace(0, 1, 40)
    st_ = (GH_X0 + 0.06 + (GH_X1 - GH_X0 - 0.12) * (0.5 - 0.5 * np.cos(np.pi * u_))).tolist()
    cav = loft("CabinCavity", st_, lambda x: (_rw(x) * 0.90, 0.30, _rz(x) - 0.01, 2.5, 3.0), M=32)
    assign(cav, liner)
    cutters.append(cav)
    for wx, tr in ((FRONT_X, TRACK_F), (REAR_X, TRACK_R)):
        for sy in (1, -1):
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=64,
                                  radius1=ARCH_R, radius2=ARCH_R, depth=0.9)
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                             matrix=Matrix.Rotation(math.radians(90), 3, "X"))
            bmesh.ops.translate(bm, verts=bm.verts, vec=(wx, sy * (tr / 2 - 0.20 + 0.45), TIRE_R + 0.012))
            c = bm_obj("ArchCutter", bm)
            assign(c, liner)
            cutters.append(c)
    for c in cutters:
        add_mod(body, "BOOLEAN", operation="DIFFERENCE", solver="EXACT", object=c)
        apply_mods(body)
        bpy.data.objects.remove(c)
    smooth_by_angle(body, 38)
    print("body materials:", [m.name for m in body.data.materials])
    return body


def build_greenhouse(paint, trim, glass_mat):
    """Canopy cut by exact planes along every window edge: CabinGlass (glass) and CabinFrame
    (painted roof / pillars + black trim band). Same objects go to the render and to Roblox."""
    NXS, NTH = 84, 60
    xs = [GH_X0 + (GH_X1 - GH_X0) * (0.5 - 0.5 * math.cos(math.pi * i / (NXS - 1))) for i in range(NXS)]
    ths = [-0.32 + (math.pi + 0.64) * j / (NTH - 1) for j in range(NTH)]
    bm = bmesh.new()
    grid = [[bm.verts.new(cabin_point(x, th)) for th in ths] for x in xs]
    for i in range(NXS - 1):
        for j in range(NTH - 1):
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    NA = plan_normal(A1, A2, (0.0, -1.0))      # A-pillar line normal, pointing inboard
    th_edge = min(ths, key=lambda th: abs(cabin_point(XR, th)[1] - RY) if math.sin(th) > 0 else 9)
    z_edge = cabin_point(XR, th_edge)[2]
    C2 = (XR - 0.10, z_edge)
    NC = plan_normal(C1, C2, (1.0, 0.0))       # (nx, nz), pointing forward

    def d_a(x, y):
        return NA[0] * (x - A1[0]) + NA[1] * (abs(y) - A1[1])

    def d_c(x, z):
        return NC[0] * (x - C1[0]) + NC[1] * (z - C1[1])

    planes = []
    for k in (0.0, TRIM):
        planes += [((0, 0, BELT + k), (0, 0, 1)), ((XF + k, 0, 0), (1, 0, 0)), ((XR - k, 0, 0), (1, 0, 0)),
                   ((C1[0] + NC[0] * k, 0, C1[1] + NC[1] * k), (NC[0], 0, NC[1]))]
        for sg in (1, -1):
            planes += [((0, sg * (RY + k), 0), (0, 1, 0)), ((0, sg * (RY - PW - k), 0), (0, 1, 0))]
            for off in (PW + k, -PW - k):
                co = (A1[0] + NA[0] * off, sg * (A1[1] + NA[1] * off), 0)
                planes.append((co, (NA[0], sg * NA[1], 0)))
    for co, no in planes:
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6,
                               plane_co=co, plane_no=no)

    def classify(f):
        x, y, z = f.calc_center_median()
        ay = abs(y)
        insets = (
            min(x - XF, d_a(x, y) - PW, z - BELT),                      # windscreen
            min(z - BELT, ay - RY, -d_a(x, y) - PW, d_c(x, z)),          # side windows
            min(XR - x, (RY - PW) - ay, z - BELT),                       # rear glass
        )
        best = max(insets)
        return "glass" if best > TRIM else ("trim" if best > 0 else "paint")

    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    cls = [classify(f) for f in bm.faces]

    def part(name, keep):
        b2 = bm.copy()
        b2.faces.ensure_lookup_table()
        bmesh.ops.delete(b2, geom=[f for f, c in zip(b2.faces, cls) if c not in keep], context="FACES")
        for f in b2.faces:
            f.smooth = True
            f.material_index = 1 if classify(f) == "trim" else 0
        ob = bm_obj(name, b2)
        return ob

    glass = part("CabinGlass", {"glass"})
    assign(glass, glass_mat)
    frame = part("CabinFrame", {"paint", "trim"})
    frame.data.materials.append(paint)
    frame.data.materials.append(trim)
    bm.free()
    return glass, frame


# --------------------------------------------------------------------------
# Wheels
# --------------------------------------------------------------------------


def lathe(name, profile, steps=96, close=True):
    """Revolve (axial, radius) profile about the Y axis."""
    bm = bmesh.new()
    vs = [bm.verts.new((r, a, 0)) for a, r in profile]
    es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    if close:
        es.append(bm.edges.new((vs[-1], vs[0])))
    bmesh.ops.spin(bm, geom=list(vs) + list(es), cent=(0, 0, 0), axis=(0, 1, 0),
                   angle=2 * math.pi, steps=steps, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm_obj(name, bm)


def spoke(bm, r0, r1, w0, w1, a0, a1, t, phi):
    """Tapered prism from radius r0->r1 in the wheel plane, rotated by phi about Y."""
    vs = []
    for r, w, a in ((r0, w0, a0), (r1, w1, a1)):
        for sz in (-1, 1):
            for sa in (-1, 1):
                v = Vector((r, a + sa * t / 2, sz * w / 2))
                vs.append(bm.verts.new(rot_y(v, phi) if phi else v))
    # vs index: (r, sz, sa) -> r*4 + (sz>0)*2 + (sa>0)
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for q in quads:
        bm.faces.new([vs[i] for i in q])


def build_wheel(tire_w):
    """20-inch wheel: tyre of section width tire_w (m), concave 10-spoke rim, slotted disc, caliper."""
    width_scale = tire_w / 0.277
    parts = []
    RR = 0.268                       # rim lip radius (21")
    hw = 0.1385 * width_scale
    ws = width_scale
    half = [(0.0, 0.345), (0.04, 0.345), (0.044, 0.3405), (0.054, 0.3405), (0.058, 0.345),
            (0.095 * ws, 0.345), (0.118 * ws, 0.3395), (0.1335 * ws, 0.324),
            (hw, 0.306), (hw * 0.99, 0.288), (0.128 * ws, 0.2735), (0.1135 * ws, RR - 0.003)]
    prof = [(-a, r) for a, r in reversed(half[1:])] + half
    tire = lathe("Tire", prof, steps=160)
    smooth_by_angle(tire, 50)
    assign(tire, TIRE_MAT)
    parts.append(tire)

    bw = 0.115 * ws
    barrel = lathe("RimBarrel", [(bw, RR), (bw + 0.004, RR - 0.009), (bw - 0.012, RR - 0.022),
                                 (0.0, RR - 0.026), (-bw + 0.012, RR - 0.022), (-bw - 0.004, RR - 0.009),
                                 (-bw, RR)], steps=96, close=False)
    add_mod(barrel, "SOLIDIFY", thickness=0.006, offset=-1)
    apply_mods(barrel)
    smooth_by_angle(barrel, 50)
    assign(barrel, RIM_MAT)
    parts.append(barrel)

    # concave 10-spoke face: spokes run from a recessed hub out to the lip, widening as they go
    bm = bmesh.new()
    face_a = 0.080 * ws
    for i in range(10):
        spoke(bm, 0.052, RR - 0.014, 0.022, 0.034, face_a - 0.040, face_a + 0.012, 0.020, i * 2 * math.pi / 10)
    bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=0.068, radius2=0.060,
                          depth=0.032, matrix=Matrix.Translation((0, face_a - 0.036, 0)) @
                          Matrix.Rotation(math.pi / 2, 4, "X"))
    spokes = bm_obj("Spokes", bm)
    add_mod(spokes, "BEVEL", width=0.0025, segments=2, limit_method="ANGLE")
    apply_mods(spokes)
    smooth_by_angle(spokes, 40)
    assign(spokes, RIM_MAT)
    parts.append(spokes)

    # machined outer lip
    lip = lathe("RimLip", [(face_a + 0.016, RR + 0.002), (face_a + 0.018, RR - 0.006), (face_a + 0.010, RR - 0.012),
                           (face_a + 0.004, RR - 0.004)], steps=96)
    smooth_by_angle(lip, 50)
    assign(lip, LIP_MAT)
    parts.append(lip)

    # lug nuts
    bm = bmesh.new()
    for i in range(5):
        a = i * 2 * math.pi / 5
        bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.0085, radius2=0.0085, depth=0.014,
                              matrix=Matrix.Translation((0.040 * math.cos(a), face_a - 0.018, 0.040 * math.sin(a))) @
                              Matrix.Rotation(math.pi / 2, 4, "X"))
    lugs = bm_obj("Lugs", bm)
    assign(lugs, CHROME)
    parts.append(lugs)

    # slotted brake disc
    bm = bmesh.new()
    segs = 80
    for i in range(segs):
        if i % 3 == 2:
            continue
        a0, a1 = i * 2 * math.pi / segs, (i + 0.8) * 2 * math.pi / segs
        vs = []
        for ang in (a0, a1):
            for r in (0.12, 0.205):
                for ay in (-0.013, 0.013):
                    vs.append(bm.verts.new((r * math.cos(ang), ay + 0.012, r * math.sin(ang))))
        for q in [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]:
            bm.faces.new([vs[j] for j in q])
    bmesh.ops.create_cone(bm, cap_ends=True, segments=64, radius1=0.122, radius2=0.122, depth=0.05,
                          matrix=Matrix.Translation((0, 0.02, 0)) @ Matrix.Rotation(math.pi / 2, 4, "X"))
    disc = bm_obj("BrakeDisc", bm)
    assign(disc, DISC_MAT)
    smooth_by_angle(disc, 40)
    parts.append(disc)

    # caliper (arc segment behind the spokes)
    bm = bmesh.new()
    prof = [(-0.036, 0.158), (0.042, 0.158), (0.042, 0.232), (-0.036, 0.232)]
    vs = [bm.verts.new((r, a + 0.012, 0)) for a, r in prof]
    es = [bm.edges.new((vs[i], vs[(i + 1) % 4])) for i in range(4)]
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 1, 0), angle=math.radians(62),
                   steps=14, use_merge=False)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(20), 3, "Y"))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    cal = bm_obj("Caliper", bm)
    add_mod(cal, "BEVEL", width=0.004, segments=2, limit_method="ANGLE")
    apply_mods(cal)
    smooth_by_angle(cal, 40)
    assign(cal, CALIPER_MAT)
    parts.append(cal)
    return parts


def place_wheel(parts, x, side):
    """side=-1 right (outer face towards -Y), +1 left."""
    y = side * (TRACK_F if x > 0 else TRACK_R) / 2
    for p in parts:
        p.location = (x, y, TIRE_R)
        # set the whole orientation: copies of the right wheels used to keep their 180 deg turn, so the
        # left wheels showed their back (brake disc) outwards and hid the spokes on the inside
        p.rotation_euler = (0, 0, math.pi if side < 0 else 0.0)
        p.rotation_euler[1] = math.radians(35 * (1 if x > 0 else 2.3) + 17 * side)


# --------------------------------------------------------------------------
# Scene
# --------------------------------------------------------------------------


def duplicate_group(parts, x, side):
    new = []
    for p in parts:
        d = p.copy()
        d.data = p.data  # shared mesh -> cheap
        link(d)
        new.append(d)
    place_wheel(new, x, side)
    return new


def build_world():
    w = bpy.data.worlds.new("Sunset")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = math.radians(ARGS.sunel)
    sky.sun_rotation = math.radians(ARGS_SUN_AZ)
    sky.sun_size = math.radians(0.9)
    sky.sun_intensity = 1.0
    sky.air_density = 1.4
    sky.aerosol_density = 2.2
    sky.ozone_density = 1.0
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.8
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs[0], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], out.inputs[0])
    bpy.context.scene.world = w


ARGS_SUN_AZ = ARGS.sun


def build_ground():
    bm = bmesh.new()
    verts = [bm.verts.new(v) for v in ((-900, -7.5, 0), (900, -7.5, 0), (900, 7.5, 0), (-900, 7.5, 0))]
    bm.faces.new(verts)
    road = bm_obj("Road", bm)
    assign(road, ASPHALT)
    return road


def build_camera(kind):
    cam = bpy.data.cameras.new("Cam")
    co = link(bpy.data.objects.new("Camera", cam))
    bpy.context.scene.camera = co
    presets = {
        "hero": ((6.3, -5.6, 0.78), (0.35, 0.0, 0.50), 60),
        "side": ((0.0, -11.5, 0.62), (0.0, 0.0, 0.60), 70),
        "front": ((8.0, 0.4, 0.62), (0.0, 0.0, 0.55), 75),
        "rear": ((-6.5, -4.8, 0.85), (-0.3, 0.0, 0.55), 60),
        "wheel": ((3.3, -2.5, 0.42), (1.35, -0.8, 0.36), 70),
    }
    loc, tgt, lens = presets[kind]
    co.location = loc
    cam.lens = lens
    d = Vector(tgt) - Vector(loc)
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.sensor_width = 36
    cam.clip_start = 0.1
    cam.clip_end = 2000
    cam.dof.use_dof = True
    cam.dof.focus_distance = d.length
    cam.dof.aperture_fstop = 4.5
    return co


def setup_compositor():
    """Subtle bloom around the sun / DRLs (runs before the view transform)."""
    try:
        sc = bpy.context.scene
        sc.render.compositor_device = "CPU"   # GPU path needs libEGL, absent on headless boxes
        ng = bpy.data.node_groups.new("Compositing", "CompositorNodeTree")
        sc.compositing_node_group = ng
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = ng.nodes.new("CompositorNodeRLayers")
        gl = ng.nodes.new("CompositorNodeGlare")
        out = ng.nodes.new("NodeGroupOutput")
        thr_, str_, size_ = [float(x) for x in ARGS.glow.split(",")]
        for k, v in (("Type", "Bloom"), ("Threshold", thr_), ("Strength", str_), ("Size", size_), ("Quality", "High")):
            try:
                gl.inputs[k].default_value = v
            except Exception as e:  # noqa
                print("glare input", k, e)
        ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
        ng.links.new(gl.outputs["Image"], out.inputs[0])
    except Exception as e:  # noqa
        print("compositor skipped:", e)


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    cy = sc.cycles
    cy.device = "CPU"
    cy.samples = QUALITY["samples"]
    cy.use_denoising = True
    try:
        cy.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    cy.max_bounces = 12
    cy.glossy_bounces = 8
    cy.transparent_max_bounces = 16
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.sample_clamp_indirect = 8.0
    sc.render.resolution_x, sc.render.resolution_y = QUALITY["res"]
    sc.render.resolution_percentage = 100
    sc.render.threads = 0
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "Medium High Contrast"
    except Exception:
        pass
    sc.view_settings.exposure = ARGS.exposure
    if ARGS.glow != "off":
        setup_compositor()
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "16" if ARGS.quality == "final" else "8"


# --------------------------------------------------------------------------
# Surface projection helpers (ray-cast onto the finished body)
# --------------------------------------------------------------------------


def cast(target, origin, d, dist):
    hit, loc, nor, _ = target.ray_cast(Vector(origin), Vector(d), distance=dist)
    return (loc.copy(), nor.copy()) if hit else (None, None)


def basis(d, u, v=None):
    d = Vector(d).normalized()
    u = Vector(u)
    u = (u - d * u.dot(d)).normalized()
    if v is None:
        v = d.cross(u)
        if v.z < 0:
            v = -v
    return d, u, Vector(v).normalized()


def surface_patch(name, target, P, d, u, a, b, n=2.0, rot=0.0, rings=7, sectors=64,
                  offset=0.0015, mat=None, reach=6.0, v=None):
    """Superellipse decal conformed to `target`, projected along d from point P."""
    d, u, v = basis(d, u, v)
    P = Vector(P)
    cr, sr = math.cos(rot), math.sin(rot)

    def hit(px, py):
        qx, qy = px * cr - py * sr, px * sr + py * cr
        loc, nor = cast(target, P + u * qx + v * qy - d * reach, d, reach * 2 + 10)
        return None if loc is None else (loc + nor * offset, nor)

    verts, norms = [], []
    h0 = hit(0, 0)
    if h0 is None:
        print("patch miss:", name)
        return None
    verts.append(h0[0]); norms.append(h0[1])
    grid = {}
    for i in range(1, rings + 1):
        r = i / rings
        for j in range(sectors):
            th = 2 * math.pi * j / sectors
            px = a * r * float(sgnpow(math.cos(th), 2.0 / n))
            py = b * r * float(sgnpow(math.sin(th), 2.0 / n))
            h = hit(px, py)
            if h is not None:
                grid[(i, j)] = len(verts)
                verts.append(h[0]); norms.append(h[1])
    faces = []
    for j in range(sectors):
        j2 = (j + 1) % sectors
        if (1, j) in grid and (1, j2) in grid:
            faces.append((0, grid[(1, j)], grid[(1, j2)]))
        for i in range(1, rings):
            q = [grid.get((i, j)), grid.get((i, j2)), grid.get((i + 1, j2)), grid.get((i + 1, j))]
            if None not in q:
                faces.append(tuple(q))
    fixed = []
    for f in faces:
        pts = [verts[i] for i in f]
        nrm = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        avg = sum((norms[i] for i in f), Vector())
        fixed.append(tuple(reversed(f)) if nrm.dot(avg) < 0 else f)
    ob = mesh_obj(name, verts, fixed)
    for p in ob.data.polygons:
        p.use_smooth = True
    if mat:
        assign(ob, mat)
    return ob


def surface_tube(name, target, pts, d, radius, mat, offset=0.0, step=0.01, reach=6.0, closed=False):
    d = Vector(d).normalized()
    P = [Vector(p) for p in pts]
    if closed:
        P.append(P[0])
    dense = []
    for p, q in zip(P[:-1], P[1:]):
        k = max(1, int((q - p).length / step))
        dense += [p + (q - p) * (i / k) for i in range(k)]
    dense.append(P[-1])
    runs, cur = [], []
    for p in dense:
        loc, nor = cast(target, p - d * reach, d, reach * 2 + 10)
        if loc is None:
            if cur:
                runs.append(cur)
            cur = []
        else:
            cur.append(loc + nor * offset)
    if cur:
        runs.append(cur)
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    cu.use_fill_caps = True
    cu.resolution_u = 1
    for run in runs:
        if len(run) < 2:
            continue
        sp = cu.splines.new("POLY")
        sp.points.add(len(run) - 1)
        for i, p in enumerate(run):
            sp.points[i].co = (p.x, p.y, p.z, 1.0)
    cu.materials.append(mat)
    return link(bpy.data.objects.new(name, cu))


def box(bm, size, loc, rot_z=0.0):
    sx, sy, sz = size
    M = Matrix.Translation(loc) @ Matrix.Rotation(rot_z, 4, "Z") @ Matrix.Diagonal((sx, sy, sz, 1))
    bmesh.ops.create_cube(bm, size=1.0, matrix=M)


def mat_grass():
    M = Mat("Verge")
    tc = M.n("ShaderNodeTexCoord")
    n1 = M.n("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 0.25
    n1.inputs["Detail"].default_value = 6
    M.l(tc.outputs["Object"], n1.inputs["Vector"])
    cr = M.n("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color = (0.035, 0.030, 0.012, 1)
    cr.color_ramp.elements[1].color = (0.085, 0.075, 0.030, 1)
    M.l(n1.outputs["Fac"], cr.inputs["Fac"])
    n2 = M.n("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 300
    M.l(tc.outputs["Object"], n2.inputs["Vector"])
    bp = M.n("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.8
    bp.inputs["Distance"].default_value = 0.05
    M.l(n2.outputs["Fac"], bp.inputs["Height"])
    p = M.principled(Roughness=0.95)
    M.l(cr.outputs["Color"], p.inputs["Base Color"])
    M.l(bp.outputs["Normal"], p.inputs["Normal"])
    return M.finish(p)


def build_materials_detail():
    global M_BLACK, M_RUBBER, M_HEAD, M_DRL, M_TAIL, M_TAILGLOW, M_GRILLE, M_MIRRORGLASS
    global M_SATIN, M_LOUVRE, M_TIPS
    M_BLACK = mat_principled("BlackPlastic", (0.012, 0.012, 0.013), 0.42, 0.0)
    M_RUBBER = mat_principled("Rubber", (0.004, 0.004, 0.004), 0.35, 0.0)
    M_HEAD = mat_principled("HeadlightGlass", (0.004, 0.005, 0.006), 0.04, 0.0, Coat_Weight=1.0,
                            Coat_Roughness=0.0)
    M_DRL = mat_emission("DRL", (1.0, 0.93, 0.80), 12.0)
    M_TAIL = mat_principled("TailGlass", (0.045, 0.0, 0.002), 0.04, 0.0, Coat_Weight=1.0, Coat_Roughness=0.0)
    M_TAILGLOW = mat_emission("TailGlow", (1.0, 0.03, 0.01), 5.0)
    M_MIRRORGLASS = mat_principled("MirrorGlass", (0.02, 0.02, 0.02), 0.0, 1.0)
    # horizontal-slat intake: dark gaps with satin bars
    M = Mat("Slats")
    tc = M.n("ShaderNodeTexCoord")
    wv = M.n("ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z", wave_profile="SAW")
    wv.inputs["Scale"].default_value = 85
    wv.inputs["Distortion"].default_value = 0.0
    M.l(tc.outputs["Object"], wv.inputs["Vector"])
    cr = M.n("ShaderNodeValToRGB")
    cr.color_ramp.interpolation = "CONSTANT"
    cr.color_ramp.elements[0].color = (0.002, 0.002, 0.002, 1)
    cr.color_ramp.elements[1].position = 0.55
    cr.color_ramp.elements[1].color = (0.12, 0.12, 0.125, 1)
    M.l(wv.outputs["Fac"], cr.inputs["Fac"])
    bp = M.n("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.6
    bp.inputs["Distance"].default_value = 0.004
    M.l(wv.outputs["Fac"], bp.inputs["Height"])
    pr = M.principled(Roughness=0.32, Metallic=0.8)
    M.l(cr.outputs["Color"], pr.inputs["Base Color"])
    M.l(bp.outputs["Normal"], pr.inputs["Normal"])
    M_GRILLE = M.finish(pr)
    M_SATIN = mat_principled("SatinTrim", (0.25, 0.25, 0.26), 0.28, 1.0)
    M_TIPS = mat_principled("ExhaustTip", (0.30, 0.29, 0.28), 0.22, 1.0)
    # hood louvres: slats running across the car, stacked along x
    M = Mat("Louvre")
    tc = M.n("ShaderNodeTexCoord")
    wv = M.n("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", wave_profile="SAW")
    wv.inputs["Scale"].default_value = 70
    wv.inputs["Distortion"].default_value = 0.0
    M.l(tc.outputs["Object"], wv.inputs["Vector"])
    cr = M.n("ShaderNodeValToRGB")
    cr.color_ramp.interpolation = "CONSTANT"
    cr.color_ramp.elements[0].color = (0.002, 0.002, 0.002, 1)
    cr.color_ramp.elements[1].position = 0.5
    cr.color_ramp.elements[1].color = (0.03, 0.03, 0.032, 1)
    M.l(wv.outputs["Fac"], cr.inputs["Fac"])
    bp = M.n("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.8
    bp.inputs["Distance"].default_value = 0.004
    M.l(wv.outputs["Fac"], bp.inputs["Height"])
    pr = M.principled(Roughness=0.4)
    M.l(cr.outputs["Color"], pr.inputs["Base Color"])
    M.l(bp.outputs["Normal"], pr.inputs["Normal"])
    M_LOUVRE = M.finish(pr)


def superellipsoid(name, centre, size, n=2.6, mat=None, rot=(0.0, 0.0, 0.0), seg=(40, 20), taper=None):
    """|x/a|^n + |y/b|^n + |z/c|^n = 1. taper(t) scales the x/z half sizes along y (t in -1..1)."""
    a, b, c = size
    bm = bmesh.new()
    rings = []
    nu, nv = seg
    e = 2.0 / n
    for i in range(1, nv):
        ph = -math.pi / 2 + math.pi * i / nv
        cp, sp = math.cos(ph), math.sin(ph)
        ring = []
        for j in range(nu):
            th = 2 * math.pi * j / nu
            ct, st = math.cos(th), math.sin(th)
            y = b * float(sgnpow(sp, e))
            k = taper(y / b) if taper else 1.0
            x = a * k * float(sgnpow(cp, e) * sgnpow(ct, e))
            z = c * k * float(sgnpow(cp, e) * sgnpow(st, e))
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for j in range(nu):
            bm.faces.new((r0[j], r0[(j + 1) % nu], r1[(j + 1) % nu], r1[j]))
    for ring, sgn in ((rings[0], -1), (rings[-1], 1)):
        pole = bm.verts.new((0, sgn * b, 0))
        for j in range(nu):
            bm.faces.new((ring[j], ring[(j + 1) % nu], pole))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = bm_obj(name, bm)
    ob.location = centre
    ob.rotation_euler = rot
    smooth_by_angle(ob, 70)
    if mat:
        assign(ob, mat)
    return ob


def outline(cx, cy, a, b, n, k=48):
    """Superellipse outline points in a 2D plane (used for shut lines and surrounds)."""
    pts = []
    for i in range(k):
        th = 2 * math.pi * i / k
        pts.append((cx + a * float(sgnpow(math.cos(th), 2.0 / n)), cy + b * float(sgnpow(math.sin(th), 2.0 / n))))
    return pts


def build_details(body):
    bpy.context.view_layer.update()
    build_materials_detail()
    carbon = mat_carbon()
    for s in (1, -1):  # +1 = left (+Y), -1 = right (-Y)
        # ---- headlights: dark lens with an L-shaped DRL ---------------------------------------
        d = Vector((-0.86, -s * 0.22, -0.46)).normalized()
        P = Vector((2.17, s * 0.655, 0.585))
        HA, HB, HN, HR = 0.235, 0.060, 3.4, 0.12
        surface_patch(f"Headlight{s}", body, P, d, (0, s, 0), HA, HB, n=HN, rot=HR, mat=M_HEAD, offset=0.0025)
        dd, u, v = basis(d, (0, s, 0))
        cr_, sr_ = math.cos(HR), math.sin(HR)

        def lp(px, py):
            return P + u * (px * cr_ - py * sr_) + v * (px * sr_ + py * cr_)

        drl = [lp(HA * t, HB * 0.62) for t in np.linspace(-0.85, 0.80, 12)]
        drl += [lp(HA * 0.80 + HB * 0.25 * k, HB * (0.62 - 1.2 * k)) for k in np.linspace(0.1, 1.0, 5)]
        surface_tube(f"DRL{s}", body, drl, d, 0.0034, M_DRL, offset=0.0048, step=0.005)
        # ---- lower corner intakes ------------------------------------------------------------
        surface_patch(f"CornerIntake{s}", body, (2.40, s * 0.56, 0.305), (-1, 0, 0), (0, s, 0), 0.115, 0.058,
                      n=3.2, rot=0.10, mat=M_GRILLE, offset=0.002)
        # ---- door shut line, flush handle, fender vent, carbon sill blade ----------------------
        door = [(0.60, 0.90), (0.615, 0.60), (0.585, 0.34), (0.52, 0.292), (-0.70, 0.292), (-0.77, 0.33),
                (-0.81, 0.60), (-0.815, 0.90)]
        surface_tube(f"DoorLine{s}", body, [(x, s * 3.0, z) for x, z in door], (0, -s, 0), 0.0021, M_RUBBER,
                     offset=-0.0008, step=0.01)
        surface_patch(f"DoorHandle{s}", body, (-0.50, s * 3.0, 0.775), (0, -s, 0), (1, 0, 0), 0.070, 0.012,
                      n=4.0, mat=M_BLACK, offset=0.0022, v=(0, 0, 1))
        surface_patch(f"FenderVent{s}", body, (0.80, s * 3.0, 0.585), (0, -s, 0), (1, 0, 0), 0.085, 0.030,
                      n=3.0, rot=0.28, mat=M_GRILLE, offset=0.002, v=(0, 0, 1))
        surface_patch(f"SillBlade{s}", body, (-0.02, s * 3.0, 0.235), (0, -s, 0), (1, 0, 0), 0.86, 0.040,
                      n=8.0, mat=carbon, offset=0.0025, v=(0, 0, 1))
        # ---- tail lamps: wrap-around lens with a glow line inside --------------------------------
        Pt = Vector((-2.30, s * 0.555, 0.835))
        surface_patch(f"TailLens{s}", body, Pt, (1, 0, 0), (0, s, 0), 0.315, 0.046, n=3.6, rot=-0.05,
                      mat=M_TAIL, offset=0.0025)
        dd, u, v = basis((1, 0, 0), (0, s, 0))
        for k, dz in enumerate((0.016, -0.014)):
            tl = [Pt + u * t + v * (dz + t * math.sin(-0.05)) for t in np.linspace(-0.25, 0.29, 14)]
            surface_tube(f"TailGlow{s}_{k}", body, tl, (1, 0, 0), 0.0038, M_TAILGLOW, offset=0.0042, step=0.006)
        surface_patch(f"TailSide{s}", body, (-2.10, s * 3.0, 0.84), (0, -s, 0), (1, 0, 0), 0.085, 0.030,
                      n=4.0, mat=M_TAIL, offset=0.0025, v=(0, 0, 1))
        # ---- quad exhaust tips in the diffuser (x placed by a ray-cast of the tail) -----------
        for ey in (0.36, 0.49):
            ey *= s
            ez = 0.355
            loc, nor = cast(body, (-4.0, ey, ez), (1, 0, 0), 6.0)
            x0 = (loc.x if loc else -2.15) - 0.015
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=False, segments=40, radius1=0.043, radius2=0.044, depth=0.14,
                                  matrix=Matrix.Translation((x0 + 0.05, ey, ez)) @ Matrix.Rotation(math.pi / 2, 4, "Y"))
            ex = bm_obj(f"Exhaust{s}", bm)
            add_mod(ex, "SOLIDIFY", thickness=0.004, offset=0)
            add_mod(ex, "BEVEL", width=0.0015, segments=2)
            apply_mods(ex)
            smooth_by_angle(ex, 50)
            assign(ex, M_TIPS)
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=0.040, radius2=0.040, depth=0.01,
                                  matrix=Matrix.Translation((x0 + 0.07, ey, ez)) @ Matrix.Rotation(math.pi / 2, 4, "Y"))
            assign(bm_obj(f"ExhaustInner{s}", bm), M_RUBBER)
        # ---- door mirrors: painted housing on a thin arm from the door top ------------------
        hc = Vector((0.30, s * 0.975, 0.890))
        # housing: wider at the outer end, swept back
        superellipsoid(f"Mirror{s}", hc, (0.062, 0.100, 0.054), n=2.3, mat=PAINT_PLAIN, rot=(0, 0, s * 0.12),
                       taper=lambda t, s=s: 0.82 + 0.18 * (t * s + 1) / 2)
        superellipsoid(f"MirrorGlass{s}", hc + Vector((-0.058, -s * 0.006, 0)), (0.005, 0.086, 0.042), n=3.0,
                       mat=M_MIRRORGLASS, rot=(0, 0, s * 0.12))
        # arm root sits on the door top: ray-cast straight down onto the shoulder
        loc, _ = cast(body, (0.35, s * 0.80, 2.0), (0, 0, -1), 3.0)
        base_ = Vector((0.35, s * 0.80, (loc.z if loc else 0.82) - 0.004))
        tip_ = Vector((0.31, s * 0.885, 0.885))
        mid_, dv = (base_ + tip_) / 2, tip_ - base_
        superellipsoid(f"MirrorArm{s}", mid_, (0.034, dv.length / 2 + 0.02, 0.016), n=2.2, mat=PAINT_PLAIN,
                       rot=(s * math.atan2(dv.z, abs(dv.y)), 0, 0))
    # ---- grille: wide rounded-trapezoid opening with slats and a satin surround -----------------
    surface_patch("Grille", body, (2.40, 0, 0.345), (-1, 0, 0), (0, 1, 0), 0.400, 0.082, n=4.2,
                  mat=M_GRILLE, offset=0.002)
    surface_tube("GrilleSurround", body, [(2.6, y, z) for y, z in outline(0.0, 0.345, 0.407, 0.089, 4.2, 72)],
                 (-1, 0, 0), 0.0055, M_SATIN, offset=0.002, step=0.006, closed=True)
    # ---- clamshell hood line, hood louvres, deck lid line ------------------------------------------
    hood = [(0.52, -0.62), (0.90, -0.70), (1.40, -0.735), (1.85, -0.70), (2.12, -0.56), (2.20, -0.30), (2.22, 0.0),
            (2.20, 0.30), (2.12, 0.56), (1.85, 0.70), (1.40, 0.735), (0.90, 0.70), (0.52, 0.62)]
    hood = hood + [(0.52, -0.62)]
    surface_tube("HoodLine", body, [(x, y, 3.0) for x, y in hood], (0, 0, -1), 0.0021, M_RUBBER,
                 offset=-0.0008, step=0.01)
    for s in (1, -1):
        surface_patch(f"HoodLouvre{s}", body, (1.52, s * 0.36, 3.0), (0, 0, -1), (1, 0, 0), 0.17, 0.062,
                      n=3.0, rot=-s * 0.10, mat=M_LOUVRE, offset=0.002, v=(0, s, 0))
    trunk = [(-1.66, -0.56), (-1.95, -0.68), (-2.12, -0.62), (-2.165, -0.35), (-2.175, 0.0), (-2.165, 0.35),
             (-2.12, 0.62), (-1.95, 0.68), (-1.66, 0.56), (-1.66, -0.56)]
    surface_tube("TrunkLine", body, [(x, y, 3.0) for x, y in trunk], (0, 0, -1), 0.0021, M_RUBBER,
                 offset=-0.0008, step=0.01)
    # smoked light bar joining the tail lamps
    surface_patch("TailBar", body, (-2.30, 0, 0.840), (1, 0, 0), (0, 1, 0), 0.32, 0.016, n=6.0,
                  mat=M_TAIL, offset=0.0022)
    # ---- splitter -------------------------------------------------------------------------------------
    bm = bmesh.new()
    verts = []
    for k in range(64):
        th = 2 * math.pi * k / 64
        verts.append(bm.verts.new((2.13 + 0.22 * float(sgnpow(math.cos(th), 0.55)),
                                   0.70 * float(sgnpow(math.sin(th), 0.45)), 0.165)))
    bm.faces.new(verts)
    spl = bm_obj("Splitter", bm)
    add_mod(spl, "SOLIDIFY", thickness=0.016, offset=0)
    add_mod(spl, "BEVEL", width=0.004, segments=2)
    apply_mods(spl)
    assign(spl, carbon)
    # ---- diffuser + fins --------------------------------------------------------------------------
    bm = bmesh.new()
    # sits under the tucked lower tail: plate just below the body floor, fins hang from it
    loc, _ = cast(body, (-4.0, 0.0, 0.31), (1, 0, 0), 6.0)
    x_end = (loc.x if loc else -2.12) + 0.01
    box(bm, (0.40, 1.10, 0.012), (x_end + 0.20, 0, 0.300))
    for i in (-2, -1, 0, 1, 2):
        box(bm, (0.36, 0.010, 0.080), (x_end + 0.20, i * 0.125, 0.258))
    dif = bm_obj("Diffuser", bm)
    add_mod(dif, "BEVEL", width=0.003, segments=1)
    apply_mods(dif)
    assign(dif, carbon)


def rbox(name, size, loc, mat, bevel=0.02, rot=(0, 0, 0), seg=3):
    bm = bmesh.new()
    box(bm, size, (0, 0, 0))
    ob = bm_obj(name, bm)
    add_mod(ob, "BEVEL", width=bevel, segments=seg, limit_method="NONE")
    apply_mods(ob)
    smooth_by_angle(ob, 60)
    ob.location = loc
    ob.rotation_euler = rot
    assign(ob, mat)
    return ob


def build_interior():
    lea = mat_principled("SeatLeather", (0.03, 0.026, 0.024), 0.42, 0.0, Sheen_Weight=0.3)
    acc = mat_principled("SeatAccent", (0.30, 0.02, 0.02), 0.45, 0.0)
    dark = mat_principled("DashPlastic", (0.012, 0.012, 0.013), 0.5, 0.0)
    carpet = mat_principled("Carpet", (0.012, 0.012, 0.012), 0.95, 0.0)
    rbox("Floor", (2.0, 1.20, 0.02), (-0.55, 0, 0.32), carpet, 0.004, seg=1)
    tilt = (0, math.radians(-16), 0)
    for s in (1, -1):
        y = s * 0.37
        rbox(f"SeatBase{s}", (0.52, 0.46, 0.12), (-0.36, y, 0.46), lea, 0.035)
        rbox(f"SeatBack{s}", (0.12, 0.46, 0.52), (-0.67, y, 0.77), lea, 0.035, rot=tilt)
        rbox(f"SeatBolster{s}", (0.14, 0.07, 0.44), (-0.64, y + s * 0.20, 0.75), lea, 0.03, rot=tilt)
        rbox(f"SeatInsert{s}", (0.015, 0.24, 0.34), (-0.605, y, 0.77), acc, 0.006, rot=tilt)
        rbox(f"Headrest{s}", (0.09, 0.24, 0.11), (-0.75, y, 0.96), lea, 0.025, rot=tilt)
    rbox("DashTop", (0.36, 1.24, 0.08), (0.24, 0, 0.80), dark, 0.03)
    rbox("Cluster", (0.18, 0.40, 0.09), (0.09, 0.37, 0.84), dark, 0.03)
    rbox("Console", (0.85, 0.20, 0.24), (-0.20, 0, 0.43), dark, 0.03)
    cu = bpy.data.curves.new("SteeringRim", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.017
    cu.bevel_resolution = 5
    sp = cu.splines.new("POLY")
    sp.use_cyclic_u = True
    sp.points.add(63)
    for i in range(64):
        a_ = 2 * math.pi * i / 64
        sp.points[i].co = (0.17 * math.cos(a_), 0.17 * math.sin(a_), 0.0, 1.0)
    cu.materials.append(dark)
    sw = link(bpy.data.objects.new("SteeringWheel", cu))
    sw.location = (-0.02, 0.37, 0.84)
    sw.rotation_euler = (0, math.radians(62), 0)


def build_environment():
    # distant hills silhouette
    rng = np.random.default_rng(7)
    N = 720
    th = np.linspace(0, 2 * np.pi, N, endpoint=False)
    h = np.zeros(N)
    for k, amp in ((2, 25), (3, 18), (5, 12), (9, 8), (17, 5), (33, 3)):
        h += amp * np.sin(k * th + rng.uniform(0, 6.28))
    h = 28 + h * 0.8
    h = np.maximum(h, 6)
    R = 1400
    verts, faces = [], []
    for i in range(N):
        verts.append((R * math.cos(th[i]), R * math.sin(th[i]), -5.0))
        verts.append((R * math.cos(th[i]), R * math.sin(th[i]), float(h[i])))
    for i in range(N):
        j = (i + 1) % N
        faces.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
    hills = mesh_obj("Hills", verts, faces)
    assign(hills, mat_emission("HillHaze", (0.11, 0.075, 0.09), 1.0))
    for p in hills.data.polygons:
        p.use_smooth = True
    # grass / dirt verge beyond the tarmac
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=2, y_segments=2, size=900)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, -0.02))
    grass = bm_obj("Verge", bm)
    assign(grass, mat_grass())
    # lane markings
    bm = bmesh.new()
    for i in range(-30, 30):
        box(bm, (3.0, 0.15, 0.004), (i * 9.0, 3.9, 0.002))
    box(bm, (400, 0.18, 0.004), (0, -3.3, 0.002))
    lines = bm_obj("RoadMarkings", bm)
    assign(lines, mat_principled("RoadPaint", (0.55, 0.55, 0.52), 0.55, 0.0))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

bpy.ops.wm.read_factory_settings(use_empty=True)

PAINT = mat_car_paint()
PAINT_PLAIN = mat_car_paint("PaintPlain", masks=False)   # for parts whose object space isn't the car's
TIRE_MAT = mat_tire()
RIM_MAT = mat_principled("RimSatin", (0.13, 0.13, 0.14), 0.30, 1.0)    # dark gunmetal
LIP_MAT = mat_principled("RimLip", (0.75, 0.75, 0.77), 0.12, 1.0)      # machined lip
CHROME = mat_principled("Chrome", (0.9, 0.9, 0.9), 0.06, 1.0)
DISC_MAT = mat_principled("BrakeDisc", (0.16, 0.15, 0.15), 0.55, 1.0)
CALIPER_MAT = mat_principled("Caliper", (0.9, 0.55, 0.0), 0.28, 0.0, Coat_Weight=1.0)
ASPHALT = mat_asphalt()

build_world()
build_ground()
body = build_body()
build_greenhouse(PAINT_PLAIN,
                 mat_principled("FrameTrim", (0.012, 0.012, 0.012), 0.35), mat_glass("CabinGlassMat", tint=(0.17, 0.18, 0.18)))
build_details(body)
build_interior()
build_environment()

proto = build_wheel(TIRE_W_F)
rproto = build_wheel(TIRE_W_R)
place_wheel(proto, FRONT_X, -1)
place_wheel(rproto, REAR_X, -1)
duplicate_group(proto, FRONT_X, +1)
duplicate_group(rproto, REAR_X, +1)

build_camera(ARGS.cam)
setup_render()

bpy.ops.wm.save_as_mainfile(filepath=ARGS.blend)
if not ARGS.no_render:
    bpy.context.scene.render.filepath = ARGS.out
    bpy.ops.render.render(write_still=True)
    print("RENDERED", ARGS.out)
