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

# triangle budgets (Roblox rejects meshes much above ~20k tris)
BUDGET = dict(Body=17000, CabinGlass=3500, CabinFrame=3500, Details=9000, Interior=3500, Wheel=5500)
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
# cabin: split dense mesh into glass / frame by the same masks the render shader uses
# --------------------------------------------------------------------------
me = cabin.data
me.calc_loop_triangles()
vn = me.vertex_normals
cls = {}
for p in me.polygons:
    z = sum(me.vertices[v].co.z for v in p.vertices) / len(p.vertices)
    nx = sum(vn[v].vector.x for v in p.vertices) / len(p.vertices)
    ny = sum(vn[v].vector.y for v in p.vertices) / len(p.vertices)
    if z > 1.10:
        c = "paint"
    elif z > 1.087:
        c = "trim"
    elif abs(abs(nx) - abs(ny)) < 0.085 and abs(nx) > 0.22 and z > 0.83:
        c = "paint"
    else:
        c = "glass"
    cls[p.index] = c


def cabin_part(name, keep):
    sel = bpy.data.objects.new(name, cabin.data.copy())
    sc.collection.objects.link(sel)
    bm = bmesh.new()
    bm.from_mesh(sel.data)
    bm.faces.ensure_lookup_table()
    kill = [f for f in bm.faces if cls[f.index] not in keep]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(sel.data)
    bm.free()
    return sel


glass = cabin_part("CabinGlass", {"glass"})
frame = cabin_part("CabinFrame", {"paint", "trim"})
# frame faces get red / black slots according to class
red = flat_material("FramePaint", (0.36, 0.004, 0.010))
blk = flat_material("FrameTrim", (0.012, 0.012, 0.012))
frame.data.materials.clear()
frame.data.materials.append(red)
frame.data.materials.append(blk)
# classes were dropped with the deleted faces, so re-classify the survivors by height
for p in frame.data.polygons:
    z = sum(frame.data.vertices[v].co.z for v in p.vertices) / len(p.vertices)
    p.material_index = 1 if 1.087 < z <= 1.10 else 0
bpy.data.objects.remove(cabin)

glass.data.materials.clear()
glass.data.materials.append(flat_material("GlassMat", (0.03, 0.04, 0.045), 0.05))

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

for name, ob in export.items():
    kind = "Wheel" if name.startswith("Wheel") else name
    n = triangulate_decimate(ob, BUDGET[kind])
    report[name] = {"tris": n}
    if name == "CabinGlass":
        continue
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
