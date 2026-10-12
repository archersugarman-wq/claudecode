# Procedural sports car (Blender)

`build_car.py` builds the whole scene from code (no external assets, no HDRI download) and renders it with Cycles:
lofted body with fender crowns and sill tuck, boolean-cut wheel arches and cabin cavity, glass canopy with
painted roof and pillar bands, twin-spoke wheels with slotted discs and calipers, car-paint shader
(metallic base, flake bump, clear coat, orange peel), projected headlights / DRLs / intakes / panel
shut lines / tail lights, mirrors, exhausts, diffuser, a simple interior, wet asphalt, a procedural
sunset sky and a light bloom pass.

## Run

Tested with the pip wheel `bpy==5.2.2` on Python 3.13 (CPU only). Blender 4.2+ should work; the sky node
type names changed in 5.0, so older versions may need `MULTIPLE_SCATTERING` swapped for `NISHITA`.

```bash
pip install bpy pillow numpy
python build_car.py --quality final --cam hero      # 1920x1080, 320 samples (~20 min on 4 cores)
python build_car.py --quality preview --cam rear    # 1280x720, 64 samples
python build_car.py --quality draft                 # 640x360, quick check
# inside Blender:  blender -b -P build_car.py -- --quality final
```

Options: `--cam hero|side|front|rear|wheel`, `--sun <azimuth deg>`, `--sunel <deg>`, `--exposure`,
`--glow thr,strength,size|off`, `--out`, `--blend`, `--no-render`.

## Known limits

- It is a convincing stylised sports car, not a photo-scan-level model: the body is a smooth
  superellipse loft, so it has no hand-sculpted panel creases, no real light internals, no badges or
  lettering, and the tyre tread is only a groove profile plus bump noise.
- Not a copy of any real car design.

## Roblox

`export_roblox.py` converts the scene into `roblox_export/SportsCar.fbx` (9 MeshParts, each under 17k triangles,
baked colour textures embedded; 1 stud = 0.28 m, ~16 studs long, faces -Z). `CarAssembly.server.luau` welds
the parts, adds invisible cylinder wheel colliders, hinge motors/steering and a VehicleSeat.

I could not open Studio from the cloud session, so the FBX import and the Luau script are **untested in
Studio**. I did re-import the FBX into Blender to check scale, orientation and textures.
Import with File > Import 3D (as a Model), then follow the header comment in the Luau file.
Known losses: no metallic / clear-coat / glass refraction, jagged roof-frame edges, and the avatar only
fits after `CAR_SCALE` enlargement.
