# Handoff: get the sports car into Roblox Studio

Paste the prompt at the bottom into a new session that runs on your own computer (Claude desktop app with
Computer use on, or `claude remote-control` in the cloned repo folder).

## State
- Repo: `archersugarman-wq/claudecode`, branch `claude/jolly-sagan-4ualjx`, folder `blender_car/`.
- `build_car.py`: procedural sports car + sunset scene for Blender (tested with pip `bpy` 5.2.2, CPU).
  Final renders: `car_render_hero.png`, `car_render_rear.png` (1920x1080).
- `export_roblox.py` produced `roblox_export/SportsCar.fbx` (+ `tex/`, `manifest.json`): 9 MeshParts
  (Body, CabinGlass, CabinFrame, Details, Interior, Wheel_FL/FR/RL/RR), each < 17k tris, baked colour
  textures embedded, 1 stud = 0.28 m (~16 studs long), faces -Z, +Y up, right side +X.
  Checked only by re-importing into Blender (scale, orientation, textures OK).
- `CarAssembly.server.luau`: welds parts, invisible cylinder wheel colliders, hinge motors, front servo
  steering, VehicleSeat. Constants: `CAR_SCALE` (1.6, because an avatar is taller than the cabin at 1x),
  `DRIVE_SIGN`, `STEER_SIGN`.

## Not done / untested
- Nothing has been imported into Roblox Studio; the FBX import and the Luau script are untested there.
- No Roblox connector or desktop control was available in the cloud session.
- Likely first fixes: imported part names/hierarchy, wheel orientation and axle direction, driving
  direction signs, body collision/mass, glass transparency.

## Prompt for the new session
> Clone `archersugarman-wq/claudecode` branch `claude/jolly-sagan-4ualjx` and read `blender_car/HANDOFF.md`.
> Then, using computer use on this machine, open Roblox Studio, import
> `blender_car/roblox_export/SportsCar.fbx` with File > Import 3D as a Model, name the model `SportsCar`
> in Workspace, add `blender_car/CarAssembly.server.luau` to ServerScriptService as a Script, press Play and
> fix whatever breaks (part names, wheel axes, driving/steering direction, collisions). Don't claim it works
> until you've driven it in Play mode and seen it.

## Studio steps (prepped in the cloud, still untested in Studio)
1. Open the place "Untitled Experience" only. Never Pet City Simulator or RealEstateTycoon.
2. File > Import 3D, pick `roblox_export/SportsCar.fbx`, keep textures/materials on, import as a Model.
   Expected: 9 MeshParts (Body, CabinGlass, CabinFrame, Details, Interior, Wheel_FL/FR/RL/RR).
   The FBX holds ~1614 units of length (100x the 16.14 studs intended). Whatever size it lands at is fine,
   the script rescales it; just note it.
3. Rename the Model `SportsCar`, put it in Workspace, upright, not rotated, with the wheels a few studs above
   the baseplate (the script scales about the model pivot, so it can grow into the ground).
4. Add `CarAssembly.server.luau` to ServerScriptService as a Script. Press Play, sit in the car (walk into it
   or `DriverSeat` is invisible and welded inside the cabin).
5. Check in order: car sits on its wheels and does not jitter; W drives forward (else `DRIVE_SIGN = -1`);
   A/D steer the right way (else `STEER_SIGN = -1`); head height in the cabin (lower `CAR_SCALE` or the seat
   offset in `fromBlender(-0.28, 0.37, 0.50)`); front wheels jitter -> raise the knuckle density.
6. If the Output shows "SportsCar is missing part X", the importer renamed parts; fix names in the Model.

Changes made without Studio (cloud prep): script auto-rescales to the intended size and measures the wheels from
the mesh; wheel colliders no longer collide with the body hull (NoCollisionConstraint); glass gets a dark colour;
`CollisionFidelity` cast for strict typing. FBX itself checked by parsing the binary: 9 meshes, max 17,000 tris
each (under Roblox's ~20k limit), UVs and embedded PNGs present on all but glass, Y-up, front -Z.
