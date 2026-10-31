# Procedural GT car for Halvern GT (Blender)

The car for Halvern GT: an original front-engine GT coupe. `build_car.py` builds the whole scene from code
(no external assets, no HDRI download) and renders it with Cycles:

- **Body:** a lofted body with fender crowns, a door scallop, sill tuck and separately shaped nose and tail
  ends (crisp deck lip over a tucked-under tail panel), plus boolean-cut wheel arches and a cabin cavity.
- **Greenhouse:** cut by exact planes into windscreen, side and rear glass, with painted roof, pillars and a
  black trim band.
- **Wheels:** concave 10-spoke 20" rims with machined lips, slotted discs and calipers.
- **Paint:** metallic base, flake bump, clear coat and orange peel.
- **Details:** headlamps with L-shaped DRLs, a grille with surround, corner intakes and hood louvres;
  clamshell, door and deck shut lines; wrap-around tail lamps with a light bar; door mirrors on short
  arms, quad exhausts, diffuser, splitter and carbon sills; a simple interior.
- **Scene:** wet asphalt, a procedural sunset sky and a light bloom pass.

## Proportions

The car is built to front-engine GT class dimensions:

| Dimension | Value |
|---|---|
| Length | 4.55 m |
| Width (body) | 1.94 m |
| Height | 1.285 m |
| Wheelbase | 2.68 m |
| Overhang, front / rear | 0.98 / 0.89 m |
| Track, front / rear | 1.66 / 1.64 m |
| Tyres, front / rear | 255/35 R20 / 295/30 R20 |

These numbers follow the published dimensions of the Ferrari Roma, Aston Martin Vantage, Mercedes-AMG GT and
Jaguar F-Type. They are quoted from memory, because the cloud session could not reach spec sheets or photos.
The styling is original: the shape is not matched to photos of any real car.

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
With the default low sun, the rear view is lit head-on. Use `--sun 160 --sunel 14` to see the surfaces
under side light.

## Known limits

- Not photo-matched: proportions come from class dimensions and the surfaces were judged by eye in renders.
- The body is a superellipse loft, so it has no sharp character creases.
- The nose is rounder than a current GT's.
- The headlamps are a dark lens plus a DRL, with no internals.
- There are no badges or lettering.
- The tyre tread is only a groove profile plus bump noise.
- Not a copy of any real car design.

## Roblox

`export_roblox.py` converts the scene into `roblox_export/SportsCar.fbx`:

- **Parts:** 10 MeshParts: Body, CabinGlass, CabinFrame, Details, Trim, Interior and Wheel_FL/FR/RL/RR. Each
  is at most 17k triangles, under Roblox's ~20k limit.
- **Scale and orientation:** 1 stud = 0.28 m, so the car is about 16.4 studs long and 4.6 studs tall. It
  faces -Z.
- **Cabin:** comes straight from the .blend, so the game and the renders share the same greenhouse.
- **Colour:** the cabin frame and wheels use a solid-colour palette, so their edges stay sharp; everything
  else uses baked colour textures, embedded in the FBX.
- **Seats:** lowered 10 cm, so a seated avatar's head clears the roof.

`CarAssembly.server.luau` makes it drivable. It welds the parts, adds invisible cylinder wheel colliders,
hinge motors with front steering, and a VehicleSeat. Press E at the car to get in. The driver gets a mph
speedometer.

Import with File > Import 3D (as a Model), then follow the header comment in the Luau file (the import
arrives 100x too big and facing +Z).

The previous export of this car was driven in Studio (W/A/S/D, steering, reverse). The current export,
with the new body and the added Trim part, has only been checked by re-importing the FBX into Blender. It
has not been re-tested in Studio. Known losses in the export:

- no metallic, clear-coat or glass refraction;
- the 2 mm panel lines are low-poly;
- Details is decimated from ~32k to 17k triangles.
