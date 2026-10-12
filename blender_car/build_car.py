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


def mat_car_paint(name="CarPaint", color=(0.36, 0.004, 0.010)):
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

    # lower body (sills, bumpers): satin black plastic, higher at nose / tail
    black = M.principled(Base_Color=(0.012, 0.012, 0.013, 1), Roughness=0.42,
                         Specular_IOR_Level=0.5)
    thr = M.n("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")      # nose
    thr.inputs["From Min"].default_value = 1.95
    thr.inputs["From Max"].default_value = 2.20
    thr.inputs["To Min"].default_value = 0.225
    thr.inputs["To Max"].default_value = 0.300
    M.l(sep.outputs["X"], thr.inputs["Value"])
    thr2 = M.n("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")     # tail: tall black bumper
    thr2.inputs["From Min"].default_value = -1.80
    thr2.inputs["From Max"].default_value = -2.22
    thr2.inputs["To Min"].default_value = 0.225
    thr2.inputs["To Max"].default_value = 0.52
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
    # interior: dark leather where the deck sits under the glass (cabin footprint)
    def gt(src, val, op="GREATER_THAN"):
        n_ = M.n("ShaderNodeMath", operation=op)
        n_.inputs[1].default_value = val
        M.l(src, n_.inputs[0])
        return n_.outputs[0]

    ay_ = M.n("ShaderNodeMath", operation="ABSOLUTE")
    M.l(sep.outputs["Y"], ay_.inputs[0])
    masks = [gt(sep.outputs["X"], -1.18), gt(sep.outputs["X"], 0.93, "LESS_THAN"),
             gt(ay_.outputs[0], 0.66, "LESS_THAN"), gt(sep.outputs["Z"], 0.78)]
    cur = masks[0]
    for m_ in masks[1:]:
        mm = M.n("ShaderNodeMath", operation="MULTIPLY")
        M.l(cur, mm.inputs[0])
        M.l(m_, mm.inputs[1])
        cur = mm.outputs[0]
    leather = M.principled(Base_Color=(0.018, 0.016, 0.016, 1), Roughness=0.5)
    mix2 = M.n("ShaderNodeMixShader")
    M.l(cur, mix2.inputs[0])
    M.l(mix.outputs[0], mix2.inputs[1])
    M.l(leather.outputs[0], mix2.inputs[2])
    return M.finish(mix2)


def mat_roof(name="Roof"):
    """Cabin: glass everywhere, painted roof panel above a z contour, thin black frame."""
    M = Mat(name)
    tc = M.n("ShaderNodeTexCoord")
    sep = M.n("ShaderNodeSeparateXYZ")
    M.l(tc.outputs["Object"], sep.inputs[0])
    glass = mat_glass("_g").node_tree.nodes  # reuse by building inline instead
    # inline glass
    fr = M.n("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.5
    tr = M.n("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (0.20, 0.21, 0.21, 1)
    gl = M.n("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.0
    gmix = M.n("ShaderNodeMixShader")
    M.l(fr.outputs[0], gmix.inputs[0])
    M.l(tr.outputs[0], gmix.inputs[1])
    M.l(gl.outputs[0], gmix.inputs[2])
    # roof = same red clear-coated paint
    paint = M.principled(Base_Color=(0.36, 0.004, 0.010, 1), Metallic=0.55, Roughness=0.30,
                         Coat_Weight=1.0, Coat_Roughness=0.015)
    trim = M.principled(Base_Color=(0.01, 0.01, 0.01, 1), Roughness=0.35)
    # masks
    gt_roof = M.n("ShaderNodeMath", operation="GREATER_THAN")
    gt_roof.inputs[1].default_value = 1.10
    M.l(sep.outputs["Z"], gt_roof.inputs[0])
    gt_trim = M.n("ShaderNodeMath", operation="GREATER_THAN")
    gt_trim.inputs[1].default_value = 1.087
    M.l(sep.outputs["Z"], gt_trim.inputs[0])
    m1 = M.n("ShaderNodeMixShader")  # glass -> trim
    M.l(gt_trim.outputs[0], m1.inputs[0])
    M.l(gmix.outputs[0], m1.inputs[1])
    M.l(trim.outputs[0], m1.inputs[2])
    m2 = M.n("ShaderNodeMixShader")  # -> roof paint
    M.l(gt_roof.outputs[0], m2.inputs[0])
    M.l(m1.outputs[0], m2.inputs[1])
    M.l(paint.outputs[0], m2.inputs[2])
    # A / C pillars: band where the surface normal faces equally forwards/backwards and sideways
    geo = M.n("ShaderNodeNewGeometry")
    sn = M.n("ShaderNodeSeparateXYZ")
    M.l(geo.outputs["Normal"], sn.inputs[0])
    ax = M.n("ShaderNodeMath", operation="ABSOLUTE")
    ay = M.n("ShaderNodeMath", operation="ABSOLUTE")
    M.l(sn.outputs["X"], ax.inputs[0])
    M.l(sn.outputs["Y"], ay.inputs[0])
    df = M.n("ShaderNodeMath", operation="SUBTRACT")
    M.l(ax.outputs[0], df.inputs[0])
    M.l(ay.outputs[0], df.inputs[1])
    ad = M.n("ShaderNodeMath", operation="ABSOLUTE")
    M.l(df.outputs[0], ad.inputs[0])
    band = M.n("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    band.inputs["From Min"].default_value = 0.11
    band.inputs["From Max"].default_value = 0.06
    band.inputs["To Min"].default_value = 0.0
    band.inputs["To Max"].default_value = 1.0
    M.l(ad.outputs[0], band.inputs["Value"])
    facing = M.n("ShaderNodeMath", operation="GREATER_THAN")
    facing.inputs[1].default_value = 0.22
    M.l(ax.outputs[0], facing.inputs[0])
    above = M.n("ShaderNodeMath", operation="GREATER_THAN")
    above.inputs[1].default_value = 0.83
    M.l(sep.outputs["Z"], above.inputs[0])
    mk = M.n("ShaderNodeMath", operation="MULTIPLY")
    M.l(band.outputs["Result"], mk.inputs[0])
    M.l(facing.outputs[0], mk.inputs[1])
    mk2 = M.n("ShaderNodeMath", operation="MULTIPLY")
    M.l(mk.outputs[0], mk2.inputs[0])
    M.l(above.outputs[0], mk2.inputs[1])
    m3 = M.n("ShaderNodeMixShader")
    M.l(mk2.outputs[0], m3.inputs[0])
    M.l(m2.outputs[0], m3.inputs[1])
    M.l(paint.outputs[0], m3.inputs[2])
    return M.finish(m3)


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


def loft(name, stations, section_fn, M=44, taper=None, crown=None, tuck=None):
    """Loft closed superellipse cross-sections along X.

    section_fn(x) -> (half_width, z_bottom, z_top, n_top, n_bottom)
    taper(x) -> scale factor (0..1) applied to width and height so the ends round off.
    """
    verts = []
    for x in stations:
        W, zb, zt, nt, nb = section_fn(x)
        T = taper(x) if taper else 1.0
        zc = 0.5 * (zb + zt)
        H = 0.5 * (zt - zb) * T
        W = W * T
        for k in range(M):
            th = -math.pi / 2 + 2 * math.pi * k / M
            c, s = math.cos(th), math.sin(th)
            e = 2.0 / (nt if s > 0 else nb)
            y = float(W * sgnpow(c, e))
            z = float(zc + H * sgnpow(s, e))
            zrel = (z - (zc - H)) / (2 * H) if H > 1e-6 else 0.5
            if crown and s > 0:   # raise the outer top corners -> fenders stand above the hood
                z += crown(x) * T * (abs(y) / max(W, 1e-6)) ** 3
            if tuck:              # narrow the sills -> body tumblehome below the shoulder
                y *= 1.0 - tuck(x) * (1.0 - zrel) ** 2
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


CAR_L = 4.52
WHEELBASE = 2.70
FRONT_X, REAR_X = WHEELBASE / 2, -WHEELBASE / 2
TIRE_R = 0.345
ARCH_R = 0.378

# --- body profile curves (tuned by eye on side / top / front silhouettes) ---
_zt = pchip([-2.26, -2.10, -1.75, -1.30, -0.80, 0.00, 0.80, 1.30, 1.80, 2.10, 2.26],
            [0.86, 0.90, 0.93, 0.92, 0.87, 0.83, 0.80, 0.765, 0.64, 0.53, 0.47])
_zb = pchip([-2.26, -2.00, -1.70, -1.00, 0.00, 1.00, 1.80, 2.10, 2.26],
            [0.40, 0.31, 0.17, 0.145, 0.14, 0.14, 0.15, 0.17, 0.21])
_w = pchip([-2.26, -2.00, -1.60, -1.35, -0.90, -0.30, 0.30, 0.90, 1.35, 1.70, 2.00, 2.26],
           [0.82, 0.92, 0.985, 1.00, 0.95, 0.915, 0.915, 0.95, 0.975, 0.95, 0.915, 0.87])


_crown = pchip([-2.26, -1.9, -1.35, -0.8, 0.0, 0.8, 1.35, 1.9, 2.26],
               [0.0, 0.06, 0.12, 0.05, 0.0, 0.05, 0.11, 0.06, 0.0])
_tuck = pchip([-2.26, -1.5, 0.0, 1.5, 2.26], [0.02, 0.05, 0.075, 0.05, 0.02])


def body_section(x):
    return _w(x), _zb(x), _zt(x), 3.7, 4.2


def body_taper(x):
    # round the nose and tail in plan and profile with a superellipse falloff
    x0f, x0r, p = 1.80, -1.80, 3.6
    if x > x0f:
        s = min((x - x0f) / (CAR_L / 2 - x0f), 1.0)
    elif x < x0r:
        s = min((x0r - x) / (CAR_L / 2 + x0r), 1.0)
    else:
        return 1.0
    return max(1.0 - s**p, 1e-4) ** (1.0 / p)


_rz = pchip([-1.50, -1.20, -0.90, -0.50, -0.10, 0.20, 0.50, 0.80, 1.05],
            [0.80, 0.90, 1.02, 1.12, 1.17, 1.15, 1.04, 0.88, 0.72])
_rw = pchip([-1.50, -1.20, -0.90, -0.50, -0.10, 0.30, 0.70, 1.05],
            [0.45, 0.64, 0.75, 0.80, 0.80, 0.78, 0.72, 0.55])


def cabin_section(x):
    return _rw(x), 0.55, _rz(x), 2.5, 3.0


def build_body():
    u = np.linspace(0, 1, 64)
    st = (-CAR_L / 2 + CAR_L * (0.5 - 0.5 * np.cos(np.pi * u))).tolist()
    body = loft("Body", st, body_section, M=44, taper=body_taper, crown=_crown, tuck=_tuck)
    add_mod(body, "SUBSURF", levels=2, render_levels=2)
    apply_mods(body)

    body.data.materials.append(PAINT)
    # wheel arches: boolean-subtract cylinders, cutter faces carry the arch-liner material
    liner = mat_principled("ArchLiner", (0.008, 0.008, 0.008), 0.9)
    cutters = []
    # cabin cavity: open the deck under the glass so the interior is a real, hollow space
    u_ = np.linspace(0, 1, 40)
    st_ = (-1.5 + 2.55 * (0.5 - 0.5 * np.cos(np.pi * u_))).tolist()
    cav = loft("CabinCavity", st_, lambda x: (_rw(x) * 0.90, 0.30, _rz(x) - 0.01, 2.5, 3.0), M=32)
    assign(cav, liner)
    cutters.append(cav)
    for wx in (FRONT_X, REAR_X):
        for sy in (1, -1):
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=64,
                                  radius1=ARCH_R, radius2=ARCH_R, depth=0.9)
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0),
                             matrix=Matrix.Rotation(math.radians(90), 3, "X"))
            bmesh.ops.translate(bm, verts=bm.verts, vec=(wx, sy * (0.50 + 0.45), TIRE_R + 0.01))
            c = bm_obj("ArchCutter", bm)
            assign(c, liner)
            cutters.append(c)
    for c in cutters:
        m = add_mod(body, "BOOLEAN", operation="DIFFERENCE", solver="EXACT", object=c)
        apply_mods(body)
        bpy.data.objects.remove(c)
    smooth_by_angle(body, 38)
    print("body materials:", [m.name for m in body.data.materials])
    return body


def build_cabin():
    u = np.linspace(0, 1, 56)
    st = (-1.5 + 2.55 * (0.5 - 0.5 * np.cos(np.pi * u))).tolist()
    cab = loft("Cabin", st, cabin_section, M=40)
    add_mod(cab, "SUBSURF", levels=2, render_levels=2)
    apply_mods(cab)
    smooth_by_angle(cab, 50)
    assign(cab, mat_roof())
    return cab


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


def build_wheel(width_scale=1.0, front=True):
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

    # twin-spoke face: 5 pairs, slightly dished
    bm = bmesh.new()
    face_a = 0.078 * ws
    for i in range(5):
        base = i * 2 * math.pi / 5
        for off in (-0.105, 0.105):
            spoke(bm, 0.048, RR - 0.020, 0.034, 0.058, face_a - 0.024, face_a + 0.014, 0.024, base + off)
    bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=0.066, radius2=0.062,
                          depth=0.03, matrix=Matrix.Translation((0, face_a - 0.010, 0)) @
                          Matrix.Rotation(math.pi / 2, 4, "X"))
    spokes = bm_obj("Spokes", bm)
    add_mod(spokes, "BEVEL", width=0.0025, segments=2, limit_method="ANGLE")
    apply_mods(spokes)
    smooth_by_angle(spokes, 40)
    assign(spokes, RIM_MAT)
    parts.append(spokes)

    # lug nuts
    bm = bmesh.new()
    for i in range(5):
        a = i * 2 * math.pi / 5
        bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.0085, radius2=0.0085, depth=0.014,
                              matrix=Matrix.Translation((0.040 * math.cos(a), face_a + 0.008, 0.040 * math.sin(a))) @
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
    y = side * 0.795
    for p in parts:
        p.location = (x, y, TIRE_R)
        if side < 0:
            p.rotation_euler = (0, 0, math.pi)
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
        "side": ((0.0, -9.0, 0.62), (0.0, 0.0, 0.58), 70),
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
    global M_BLACK, M_RUBBER, M_HEAD, M_DRL, M_TAIL, M_TAILGLOW, M_GRILLE, M_VENT, M_MIRRORGLASS
    M_BLACK = mat_principled("BlackPlastic", (0.012, 0.012, 0.013), 0.42, 0.0)
    M_RUBBER = mat_principled("Rubber", (0.004, 0.004, 0.004), 0.35, 0.0)
    M_HEAD = mat_principled("HeadlightGlass", (0.004, 0.005, 0.006), 0.04, 0.0, Coat_Weight=1.0,
                            Coat_Roughness=0.0)
    M_DRL = mat_emission("DRL", (1.0, 0.93, 0.80), 18.0)
    M_TAIL = mat_principled("TailGlass", (0.35, 0.0, 0.01), 0.05, 0.0, Coat_Weight=1.0, Coat_Roughness=0.0)
    M_TAILGLOW = mat_emission("TailGlow", (1.0, 0.02, 0.01), 14.0)
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
    M_VENT = M_GRILLE


def build_details(body, cabin):
    bpy.context.view_layer.update()
    build_materials_detail()
    carbon = mat_carbon()
    for s in (1, -1):  # +1 = left (+Y), -1 = right (-Y)
        side = Vector((0, -s, 0))
        # ---- headlights --------------------------------------------------
        d = (-0.93, 0.0, -0.37)
        P = (2.12, s * 0.63, 0.57)
        HA, HB, HN, HR = 0.27, 0.070, 3.6, 0.20
        surface_patch(f"Headlight{s}", body, P, d, (0, s, 0), HA, HB, n=HN, rot=HR,
                      mat=M_HEAD, offset=0.0025)
        dd, u, v = basis(d, (0, s, 0))
        cr_, sr_ = math.cos(HR), math.sin(HR)
        pl = []
        for t in np.linspace(-0.88, 0.88, 14):
            px = HA * t
            py = HB * 0.74 * (1 - abs(t) ** HN) ** (1 / HN)
            pl.append(Vector(P) + u * (px * cr_ - py * sr_) + v * (px * sr_ + py * cr_))
        surface_tube(f"DRL{s}", body, pl, d, 0.0038, M_DRL, offset=0.0045, step=0.006)
        # ---- front intakes ----------------------------------------------
        surface_patch(f"CornerIntake{s}", body, (2.2, s * 0.64, 0.325), (-1, 0, 0), (0, s, 0), 0.17, 0.07,
                      n=3.0, rot=-0.06 * s * 0, mat=M_GRILLE, offset=0.002)
        # ---- door shut line + handle ---------------------------------------
        door = [(-0.60, 0.745), (-0.62, 0.60), (-0.60, 0.34), (-0.55, 0.288), (0.60, 0.288), (0.66, 0.30),
                (0.70, 0.36), (0.715, 0.60), (0.70, 0.745)]
        surface_tube(f"DoorLine{s}", body, [(x, s * 3.0, z) for x, z in door], (0, -s, 0), 0.0022, M_RUBBER,
                     offset=-0.0008, step=0.01)
        surface_patch(f"DoorHandle{s}", body, (-0.30, s * 3.0, 0.655), (0, -s, 0), (1, 0, 0), 0.075, 0.014,
                      n=3.5, mat=M_BLACK, offset=0.0025, v=(0, 0, 1))
        surface_patch(f"FenderGill{s}", body, (0.84, s * 3.0, 0.58), (0, -s, 0), (1, 0, 0), 0.075, 0.032,
                      n=3.0, rot=0.35, mat=M_VENT, offset=0.002, v=(0, 0, 1))
        # ---- rear lights -----------------------------------------------------
        Pt = (-2.25, s * 0.52, 0.80)
        surface_patch(f"TailLens{s}", body, Pt, (1, 0, 0), (0, s, 0), 0.33, 0.052, n=3.0, rot=-0.06,
                      mat=M_TAIL, offset=0.0025)
        dd, u, v = basis((1, 0, 0), (0, s, 0))
        surface_tube(f"TailGlow{s}", body, [Vector(Pt) + u * (-0.28) + v * 0.0, Vector(Pt) + u * 0.31 + v * (-0.004)],
                     (1, 0, 0), 0.0065, M_TAILGLOW, offset=0.0045, step=0.008)
        # ---- exhaust tip (placed from a ray-cast of the tail surface) --------------------
        ey = s * 0.46
        loc, nor = cast(body, (-4.0, ey, 0.43), (1, 0, 0), 6.0)
        x0 = loc.x if loc else -2.15
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=False, segments=48, radius1=0.050, radius2=0.052, depth=0.16,
                              matrix=Matrix.Translation((x0 - 0.01, ey, 0.43)) @ Matrix.Rotation(math.pi / 2, 4, "Y"))
        ex = bm_obj(f"Exhaust{s}", bm)
        add_mod(ex, "SOLIDIFY", thickness=0.004, offset=0)
        add_mod(ex, "BEVEL", width=0.0015, segments=2)
        apply_mods(ex)
        smooth_by_angle(ex, 50)
        assign(ex, CHROME)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=0.047, radius2=0.047, depth=0.01,
                              matrix=Matrix.Translation((x0 + 0.03, ey, 0.43)) @ Matrix.Rotation(math.pi / 2, 4, "Y"))
        exi = bm_obj(f"ExhaustInner{s}", bm)
        assign(exi, M_BLACK)
        # ---- mirrors ------------------------------------------------------------
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=1.0,
                                  matrix=Matrix.Translation((0.60, s * 0.97, 0.865)) @
                                  Matrix.Rotation(s * 0.2, 4, "Z") @ Matrix.Diagonal((0.095, 0.07, 0.048, 1)))
        mir = bm_obj(f"Mirror{s}", bm)
        smooth_by_angle(mir, 80)
        assign(mir, PAINT)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.014, radius2=0.012, depth=0.16,
                              matrix=Matrix.Translation((0.60, s * 0.885, 0.84)) @
                              Matrix.Rotation(math.pi / 2, 4, "X"))
        st = bm_obj(f"MirrorStalk{s}", bm)
        smooth_by_angle(st, 80)
        assign(st, M_BLACK)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0,
                                  matrix=Matrix.Translation((0.515, s * 0.975, 0.865)) @
                                  Matrix.Rotation(s * 0.2, 4, "Z") @ Matrix.Diagonal((0.008, 0.064, 0.038, 1)))
        mg = bm_obj(f"MirrorGlass{s}", bm)
        assign(mg, M_MIRRORGLASS)
        # ---- pillars ------------------------------------------------------------
        belt = [(0.56, 0.772), (0.3, 0.78), (-0.4, 0.80), (-1.0, 0.84), (-1.3, 0.875)]
        surface_tube(f"BeltTrim{s}", cabin, [(x, s * 3.0, z) for x, z in belt], (0, -s, 0), 0.007, M_RUBBER,
                     offset=-0.001, step=0.01)
    # ---- centre grille, hood & trunk lines, diffuser, splitter ----------------------
    surface_patch("Grille", body, (2.3, 0, 0.318), (-1, 0, 0), (0, 1, 0), 0.40, 0.068, n=3.4,
                  mat=M_GRILLE, offset=0.002)
    hood = [(0.97, -0.52), (1.25, -0.60), (1.7, -0.66), (2.0, -0.55), (2.17, -0.30), (2.2, 0.0),
            (2.17, 0.30), (2.0, 0.55), (1.7, 0.66), (1.25, 0.60), (0.97, 0.52), (0.97, -0.52)]
    surface_tube("HoodLine", body, [(x, y, 3.0) for x, y in hood], (0, 0, -1), 0.0022, M_RUBBER,
                 offset=-0.0008, step=0.01)
    trunk = [(-1.38, -0.60), (-1.8, -0.72), (-2.1, -0.60), (-2.2, -0.35), (-2.22, 0.0), (-2.2, 0.35),
             (-2.1, 0.60), (-1.8, 0.72), (-1.38, 0.60), (-1.38, -0.60)]
    surface_tube("TrunkLine", body, [(x, y, 3.0) for x, y in trunk], (0, 0, -1), 0.0022, M_RUBBER,
                 offset=-0.0008, step=0.01)
    # splitter
    bm = bmesh.new()
    verts = []
    for k in range(64):
        th = 2 * math.pi * k / 64
        verts.append(bm.verts.new((2.05 + 0.24 * float(sgnpow(math.cos(th), 0.5)),
                                   0.66 * float(sgnpow(math.sin(th), 0.5)), 0.158)))
    bm.faces.new(verts)
    spl = bm_obj("Splitter", bm)
    add_mod(spl, "SOLIDIFY", thickness=0.016, offset=0)
    add_mod(spl, "BEVEL", width=0.004, segments=2)
    apply_mods(spl)
    assign(spl, carbon)
    # diffuser + fins
    bm = bmesh.new()
    box(bm, (0.40, 1.10, 0.014), (-2.02, 0, 0.30))
    for i in range(-3, 4):
        box(bm, (0.38, 0.010, 0.07), (-2.02, i * 0.16, 0.265))
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
    rbox("Floor", (2.0, 1.15, 0.02), (-0.15, 0, 0.32), carpet, 0.004, seg=1)
    tilt = (0, math.radians(-14), 0)
    for s in (1, -1):
        y = s * 0.37
        rbox(f"SeatBase{s}", (0.52, 0.46, 0.12), (-0.28, y, 0.46), lea, 0.035)
        rbox(f"SeatBack{s}", (0.12, 0.46, 0.50), (-0.58, y, 0.76), lea, 0.035, rot=tilt)
        rbox(f"SeatBolster{s}", (0.14, 0.07, 0.42), (-0.55, y + s * 0.20, 0.74), lea, 0.03, rot=tilt)
        rbox(f"SeatInsert{s}", (0.015, 0.24, 0.34), (-0.515, y, 0.76), acc, 0.006, rot=tilt)
        rbox(f"Headrest{s}", (0.09, 0.24, 0.11), (-0.655, y, 0.94), lea, 0.025, rot=tilt)
    rbox("DashTop", (0.34, 1.20, 0.07), (0.60, 0, 0.745), dark, 0.025)
    rbox("Cluster", (0.20, 0.42, 0.10), (0.46, 0.37, 0.79), dark, 0.03)
    rbox("Console", (0.80, 0.20, 0.22), (-0.10, 0, 0.42), dark, 0.03)
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
    sw.location = (0.28, 0.37, 0.86)
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
TIRE_MAT = mat_tire()
RIM_MAT = mat_principled("RimSatin", (0.42, 0.42, 0.44), 0.22, 1.0)
CHROME = mat_principled("Chrome", (0.9, 0.9, 0.9), 0.06, 1.0)
DISC_MAT = mat_principled("BrakeDisc", (0.16, 0.15, 0.15), 0.55, 1.0)
CALIPER_MAT = mat_principled("Caliper", (0.9, 0.55, 0.0), 0.28, 0.0, Coat_Weight=1.0)
ASPHALT = mat_asphalt()

build_world()
build_ground()
body = build_body()
cabin = build_cabin()
build_details(body, cabin)
build_interior()
build_environment()

proto = build_wheel(1.0, True)
rproto = build_wheel(1.12, False)
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
