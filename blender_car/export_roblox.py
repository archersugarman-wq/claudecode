#!/usr/bin/env python3
"""Export the procedural sports car to a Roblox-ready FBX (low-poly meshes + baked colour textures).

    python export_roblox.py [--blend sports_car.blend] [--out roblox_export]

Produces in <out>/:
    SportsCar.fbx        one FBX, one object per MeshPart (Body, CabinGlass, CabinFrame, Details,
                         Interior, Wheel_FL/FR/RL/RR) with embedded colour textures
    tex/*.png            the baked textures (also embedded in the FBX)
    manifest.json        triangle counts and dimensions
Scale: 1 Blender unit == 1 stud after export; the 4.52 m car becomes ~16 studs (1 stud = 0.28 m).
Orientation: car faces -Z (Roblox vehicle forward), +Y up, right side is +X.
"""
import argparse
import json
import math
import os
import sys

import bpy  # must come first: it puts bmesh/mathutils on sys.path
import bmesh
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
ap = argparse.ArgumentParser()
ap.add_argument("--blend", default=os.path.join(HERE, "sports_car.blend"))
ap.add_argument("--out", default=os.path.join(HERE, "roblox_export"))
ARGS = ap.parse_args(argv)

STUD = 0.28                      # metres per stud
SCALE = 1.0 / STUD
TEX = os.path.join(ARGS.out, "tex")
os.makedirs(TEX, exist_ok=True)

# triangle budgets (Roblox rejects meshes much above ~20k tris). Cabin and wheels are not decimated:
# collapsing them destroyed the spokes and the window edges, and they fit the limit as built.
BUDGET = dict(Body=17000, CabinGlass=19000, CabinFrame=19000, Details=9000, Interior=3500, Wheel=19000)
TEXSIZE = dict(Body=2048, CabinFrame=512, Details=1024, Interior=512, Wheel=512)

bpy.ops.wm.open_mainfile(filepath=ARGS.blend)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 8
sc.cycles.use_denoising = False


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def select_only(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def to_mesh_objects():
    """Curves (panel lines, tubes, steering wheel) -> meshes."""
    curves = [o for o in bpy.data.objects if o.type == "CURVE"]
    if curves:
        select_only(curves)
        bpy.ops.object.convert(target="MESH")


def base(name):
    return name.split(".")[0]


def join_into(name, objs, location=(0, 0, 0)):
    """Join objs into a new object sitting at `location` (identity rotation/scale)."""
    me = bpy.data.meshes.new(name)
    new = bpy.data.objects.new(name, me)
    sc.collection.objects.link(new)
    new.location = location
    select_only([new] + list(objs))
    bpy.context.view_layer.objects.active = new
    bpy.ops.object.join()
    return new


def tris(ob):
    ob.data.calc_loop_triangles()
    return len(ob.data.loop_triangles)


def triangulate_decimate(ob, target):
    select_only([ob])
    m = ob.modifiers.new("tri", "TRIANGULATE")
    m.min_vertices = 4
    bpy.ops.object.modifier_apply(modifier=m.name)
    n = tris(ob)
    if n > target:
        d = ob.modifiers.new("dec", "DECIMATE")
        d.decimate_type = "COLLAPSE"
        d.ratio = target / n
        d.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=d.name)
    # smooth shading with sharp edges at creases
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(40))
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(ob.data)
    bm.free()
    return tris(ob)


def flatten_material(mat):
    """Copy of `mat` whose DIFFUSE colour pass equals the visible base colour."""
    m = mat.copy()
    m.name = "bake_" + mat.name
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type == "BSDF_PRINCIPLED":
            for sock, val in (("Metallic", 0.0), ("Coat Weight", 0.0), ("Sheen Weight", 0.0),
                              ("Transmission Weight", 0.0), ("Emission Strength", 0.0)):
                if sock in n.inputs:
                    for l in list(n.inputs[sock].links):
                        nt.links.remove(l)
                    n.inputs[sock].default_value = val
            if "Coat Normal" in n.inputs:
                for l in list(n.inputs["Coat Normal"].links):
                    nt.links.remove(l)
        elif n.type == "EMISSION":
            p = nt.nodes.new("ShaderNodeBsdfPrincipled")
            p.inputs["Base Color"].default_value = n.inputs["Color"].default_value
            p.inputs["Roughness"].default_value = 1.0
            for l in list(n.outputs[0].links):
                nt.links.new(p.outputs[0], l.to_socket)
            nt.nodes.remove(n)
    return m


def make_uv(ob):
    select_only([ob])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_colour(ob, size):
    """Bake base colour of all material slots into one image; replace slots with one textured material."""
    make_uv(ob)
    img = bpy.data.images.new(ob.name + "_color", size, size, alpha=False)
    img.colorspace_settings.name = "sRGB"
    flats = []
    for i, slot in enumerate(ob.material_slots):
        if slot.material is None:
            print("  empty slot", i, "on", ob.name)
            slot.material = flat_material("fallback", (0.05, 0.05, 0.05))
        fm = flatten_material(slot.material)
        slot.material = fm
        tn = fm.node_tree.nodes.new("ShaderNodeTexImage")
        tn.image = img
        fm.node_tree.nodes.active = tn
        flats.append(fm)
    select_only([ob])
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=8, use_clear=True)
    path = os.path.join(TEX, ob.name + "_color.png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    img.pack()
    # final single material: image -> Principled
    mat = bpy.data.materials.new(ob.name + "_mat")
    mat.use_nodes = True
    nt = mat.node_tree
    p = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    nt.links.new(t.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.45
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    return path


def flat_material(name, colour, rough=0.4, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    p = mat.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*colour, 1)
    p.inputs["Roughness"].default_value = rough
    return mat


# --------------------------------------------------------------------------
# gather objects
# --------------------------------------------------------------------------
to_mesh_objects()
objs = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
SKIP = {"Road", "Verge", "Hills", "RoadMarkings"}
WHEEL_PARTS = {"Tire", "RimBarrel", "Spokes", "Lugs", "BrakeDisc", "Caliper"}
INTERIOR = ("SeatBase", "SeatBack", "SeatBolster", "SeatInsert", "Headrest", "DashTop", "Cluster",
            "Console", "Floor", "SteeringWheel")

wheel_groups, interior, details = {}, [], []
# .blend files built before the place_wheel fix have the left wheels turned back to front (spokes inboard)
for o in objs.values():
    if base(o.name) in WHEEL_PARTS and o.location.y > 0 and abs(o.rotation_euler.z - math.pi) < 1e-3:
        o.rotation_euler.z = 0.0
bpy.context.view_layer.update()
body = objs["Body"]
cabin = objs["Cabin"]
for name, o in objs.items():
    b = base(name)
    if name in SKIP or o is body or o is cabin:
        continue
    if b in WHEEL_PARTS:
        key = ("F" if o.location.x > 0 else "R") + ("L" if o.location.y > 0 else "R")
        wheel_groups.setdefault(key, []).append(o)
    elif b.startswith(INTERIOR):
        interior.append(o)
    else:
        details.append(o)

# --------------------------------------------------------------------------
# palette texturing: every face samples the centre of one solid colour tile, so colour borders follow
# the geometry exactly and stay sharp at any texture size (a baked texture smears thin parts like
# spokes and turns face-by-face masks into staircases)
# --------------------------------------------------------------------------
PAL_TILES = 4                    # 4x4 tiles
PAL_SIZE = 256


def palette_texture(ob, colour_of):
    """colour_of(material_name) -> sRGB (r, g, b). Replaces ob's materials with one palette texture."""
    names = [base(s.material.name) if s.material else "none" for s in ob.material_slots] or ["none"]
    colours = []
    for n in names:
        c = tuple(colour_of(n))
        if c not in colours:
            colours.append(c)
    assert len(colours) <= PAL_TILES * PAL_TILES, (ob.name, colours)
    img = bpy.data.images.new(ob.name + "_color", PAL_SIZE, PAL_SIZE, alpha=False)
    img.colorspace_settings.name = "sRGB"
    tile = PAL_SIZE // PAL_TILES
    px = [0.0] * (PAL_SIZE * PAL_SIZE * 4)
    for i, c in enumerate(colours):
        tx, ty = i % PAL_TILES, i // PAL_TILES
        for yy in range(ty * tile, (ty + 1) * tile):
            for xx in range(tx * tile, (tx + 1) * tile):
                k = (yy * PAL_SIZE + xx) * 4
                px[k:k + 4] = [c[0], c[1], c[2], 1.0]
    img.pixels[:] = px
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active.data
    slot_tile = [colours.index(tuple(colour_of(n))) for n in names]
    for p in me.polygons:
        i = slot_tile[min(p.material_index, len(slot_tile) - 1)]
        centre = ((i % PAL_TILES + 0.5) / PAL_TILES, (i // PAL_TILES + 0.5) / PAL_TILES)
        for li in p.loop_indices:
            uv[li].uv = centre
    path = os.path.join(TEX, ob.name + "_color.png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    img.pack()
    mat = bpy.data.materials.new(ob.name + "_mat")
    mat.use_nodes = True
    nt = mat.node_tree
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    t.interpolation = "Closest"
    nt.links.new(t.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    me.materials.clear()
    me.materials.append(mat)
    for p in me.polygons:
        p.material_index = 0
    return path


def srgb(lin):
    return tuple(12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055 for c in lin)


PAINT_SRGB = srgb((0.36, 0.004, 0.010))   # same red as the body paint
TRIM_SRGB = srgb((0.012, 0.012, 0.012))

# --------------------------------------------------------------------------
# cabin: rebuilt for Roblox as a real greenhouse instead of splitting the render's glass dome by shader
# masks (that gave a floating red cap with jagged edges). Same lofted profile as build_car.cabin_section,
# with the roof lifted so a seated Roblox avatar fits. Window outlines are exact plane cuts.
# --------------------------------------------------------------------------
def pchip(xs, ys):
    """Monotone cubic interpolator (same as build_car.pchip)."""
    h = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(len(h))]
    m = [0.0] * len(xs)
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(xs) - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        x = min(max(x, xs[0]), xs[-1])
        i = max(0, min(len(xs) - 2, next((k for k in range(len(xs) - 1) if x <= xs[k + 1]), len(xs) - 2)))
        t = (x - xs[i]) / h[i]
        return ((2 * t**3 - 3 * t**2 + 1) * ys[i] + (t**3 - 2 * t**2 + t) * h[i] * m[i]
                + (-2 * t**3 + 3 * t**2) * ys[i + 1] + (t**3 - t**2) * h[i] * m[i + 1])
    return f


_rz = pchip([-1.50, -1.20, -0.90, -0.50, -0.10, 0.20, 0.50, 0.80, 1.05],
            [0.80, 0.90, 1.02, 1.12, 1.17, 1.15, 1.04, 0.88, 0.72])
_rw = pchip([-1.50, -1.20, -0.90, -0.50, -0.10, 0.30, 0.70, 1.05],
            [0.45, 0.64, 0.75, 0.80, 0.80, 0.78, 0.72, 0.55])

BELT = 0.80          # window line: where the cabin leaves the body shoulder
ROOF_RAISE = 0.13    # m added at the roof so a seated avatar's head clears it (car ~1.30 m tall)
XF, XR = 0.30, -0.80  # roof panel front / rear edge (windscreen top, rear glass top)
RY = 0.56            # roof panel half width = top edge of the side windows
PW = 0.035           # half width of A-pillars and C-pillar / roof rails
TRIM = 0.022         # black frame band inside every glass edge
A1, A2 = (1.05, 0.66), (XF, RY)  # A-pillar line in plan view (x, |y|): windscreen base corner -> roof corner


def smooth01(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def cabin_point(x, th):
    W, zt, zb = _rw(x), _rz(x), 0.55
    c, s = math.cos(th), math.sin(th)
    e = 2.0 / (2.5 if s > 0 else 3.0)
    y = W * math.copysign(abs(c) ** e, c)
    zc, H = 0.5 * (zb + zt), 0.5 * (zt - zb)
    z = zc + H * math.copysign(abs(s) ** e, s)
    # lift the roof, fading out towards the windscreen base and the rear deck so those still meet the body
    along = smooth01((1.0 - x) / 0.55) * smooth01((x + 1.45) / 0.50)
    if zt > BELT:
        z += ROOF_RAISE * along * smooth01((z - BELT) / (zt - BELT))
    return (x, y, z)


def plan_normal(p, q, toward):
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy)
    n = (dy / L, -dx / L)
    if n[0] * toward[0] + n[1] * toward[1] < 0:
        n = (-n[0], -n[1])
    return n


NA = plan_normal(A1, A2, (0.0, -1.0))   # A-pillar line normal, pointing inboard


def build_greenhouse():
    NXS, NTH = 72, 56
    xs = [-1.5 + 2.55 * (0.5 - 0.5 * math.cos(math.pi * i / (NXS - 1))) for i in range(NXS)]
    ths = [-0.32 + (math.pi + 0.64) * j / (NTH - 1) for j in range(NTH)]
    bm = bmesh.new()
    grid = [[bm.verts.new(cabin_point(x, th)) for th in ths] for x in xs]
    for i in range(NXS - 1):
        for j in range(NTH - 1):
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    # rear C-pillar edge: slanted line in side view from the belt up to the roof's rear corner
    th_edge = min(ths, key=lambda th: abs(cabin_point(XR, th)[1] - RY) if math.sin(th) > 0 else 9)
    z_edge = cabin_point(XR, th_edge)[2]
    C1, C2 = (-0.60, BELT), (XR - 0.07, z_edge)
    NC = plan_normal(C1, C2, (1.0, 0.0))  # (nx, nz), pointing forward

    def d_a(x, y):
        return NA[0] * (x - A1[0]) + NA[1] * (abs(y) - A1[1])

    def d_c(x, z):
        return NC[0] * (x - C1[0]) + NC[1] * (z - C1[1])

    # cut along every window / frame edge so colour borders are exact
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
            min(x - XF, d_a(x, y) - PW, z - BELT),                       # windscreen
            min(z - BELT, ay - RY, -d_a(x, y) - PW, d_c(x, z)),           # side windows
            min(XR - x, (RY - PW) - ay, z - BELT),                        # rear glass
        )
        best = max(insets)
        if best > TRIM:
            return "glass"
        if best > 0:
            return "trim"
        return "paint"

    cls = {f: classify(f) for f in bm.faces}
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    # triangulate keeps each new face's class via its centre (all fragments of one face share a region)
    cls = {f: classify(f) for f in bm.faces}

    def part(name, keep):
        b2 = bm.copy()
        b2.faces.ensure_lookup_table()
        ref = list(cls.values())
        bmesh.ops.delete(b2, geom=[f for f, c in zip(b2.faces, ref) if c not in keep], context="FACES")
        for f in b2.faces:
            f.smooth = True
        me = bpy.data.meshes.new(name)
        b2.to_mesh(me)
        b2.free()
        ob = bpy.data.objects.new(name, me)
        sc.collection.objects.link(ob)
        return ob

    glass_ob = part("CabinGlass", {"glass"})
    frame_ob = part("CabinFrame", {"paint", "trim"})
    paint = flat_material("FramePaint", (0.36, 0.004, 0.010))
    trim = flat_material("FrameTrim", (0.012, 0.012, 0.012))
    frame_ob.data.materials.append(paint)
    frame_ob.data.materials.append(trim)
    fb = bmesh.new()
    fb.from_mesh(frame_ob.data)
    for f in fb.faces:
        f.material_index = 1 if classify(f) == "trim" else 0
    fb.to_mesh(frame_ob.data)
    fb.free()
    glass_ob.data.materials.append(flat_material("GlassMat", (0.03, 0.04, 0.045), 0.05))
    bm.free()
    return glass_ob, frame_ob


bpy.data.objects.remove(cabin)
glass, frame = build_greenhouse()

# seats sit 10 cm lower (the Roblox VehicleSeat is lowered to match) for avatar headroom
SEAT_DROP = 0.10
for o in interior:
    if base(o.name).startswith(("SeatBase", "SeatBack", "SeatBolster", "SeatInsert", "Headrest")):
        o.location.z -= SEAT_DROP

# --------------------------------------------------------------------------
# build the export set
# --------------------------------------------------------------------------
export = {}
report = {}

det = join_into("Details", details)
export["Details"] = det
inter = join_into("Interior", interior)
export["Interior"] = inter
export["Body"] = body
export["CabinFrame"] = frame
export["CabinGlass"] = glass

for key, parts in wheel_groups.items():
    # origin at the wheel centre; mesh stays in world orientation relative to that centre
    centre = parts[0].location.copy()
    w = join_into("Wheel_" + key, parts, location=centre)
    export["Wheel_" + key] = w

WHEEL_SRGB = {"Tire": srgb((0.018, 0.018, 0.019)), "RimSatin": (0.66, 0.67, 0.69), "Chrome": (0.88, 0.88, 0.9),
              "BrakeDisc": (0.30, 0.29, 0.29), "Caliper": srgb((0.9, 0.55, 0.0))}
for name, ob in export.items():
    kind = "Wheel" if name.startswith("Wheel") else name
    n = triangulate_decimate(ob, BUDGET[kind])
    report[name] = {"tris": n}
    if name == "CabinGlass":
        continue
    if kind == "Wheel":
        palette_texture(ob, lambda m: WHEEL_SRGB.get(m, (0.5, 0.5, 0.5)))
    elif name == "CabinFrame":
        palette_texture(ob, lambda m: TRIM_SRGB if m == "FrameTrim" else PAINT_SRGB)
    else:
        bake_colour(ob, TEXSIZE[kind])

# --------------------------------------------------------------------------
# orientation + scale: Blender (+X forward, +Y left, +Z up) -> Roblox (-Z forward, +X right, +Y up)
# --------------------------------------------------------------------------
M = Matrix.Scale(SCALE, 4) @ Matrix.Rotation(math.radians(90), 4, "Z")
for ob in export.values():
    ob.matrix_world = M @ ob.matrix_world
select_only(list(export.values()))
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

for name, ob in export.items():
    xs = [v.co for v in ob.data.vertices]
    mn = [min(c[i] for c in xs) + ob.location[i] for i in range(3)]
    mx = [max(c[i] for c in xs) + ob.location[i] for i in range(3)]
    report[name]["bbox_blender_studs_min"] = [round(v, 2) for v in mn]
    report[name]["bbox_blender_studs_max"] = [round(v, 2) for v in mx]

# delete everything not exported so the FBX only holds the car
keep = set(export.values())
for o in list(bpy.data.objects):
    if o not in keep:
        bpy.data.objects.remove(o)

select_only(list(export.values()))
fbx = os.path.join(ARGS.out, "SportsCar.fbx")
bpy.ops.export_scene.fbx(
    filepath=fbx, use_selection=True, object_types={"MESH"}, use_mesh_modifiers=True,
    mesh_smooth_type="FACE", axis_forward="-Z", axis_up="Y", bake_space_transform=True,
    global_scale=1.0, apply_unit_scale=False, apply_scale_options="FBX_SCALE_NONE",
    path_mode="COPY", embed_textures=True, add_leaf_bones=False)

# validate by re-importing into an empty scene
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
imp = [o for o in bpy.data.objects if o.type == "MESH"]
lo = [1e9] * 3
hi = [-1e9] * 3
for o in imp:
    for c in o.bound_box:
        w = o.matrix_world @ __import__("mathutils").Vector(c)
        for i in range(3):
            lo[i], hi[i] = min(lo[i], w[i]), max(hi[i], w[i])
report["_reimport"] = {"objects": sorted(o.name for o in imp),
                       "extent_xyz_blender_axes": [round(hi[i] - lo[i], 2) for i in range(3)],
                       "note": "after re-import Blender is Z-up: X=width, Y=length, Z=height (studs)"}
with open(os.path.join(ARGS.out, "manifest.json"), "w") as f:
    json.dump(report, f, indent=2)
print(json.dumps(report, indent=2))
