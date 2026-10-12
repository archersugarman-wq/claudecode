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
