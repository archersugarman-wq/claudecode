# Handoff: get the sports car into Roblox Studio

Paste the prompt at the bottom into a new session that runs on your own computer (Claude desktop app with
Computer use on, or `claude remote-control` in the cloned repo folder).

## State
- Repo: `archersugarman-wq/claudecode`, branch `claude/sleepy-hamilton-9ma2tr`, folder `blender_car/`.
- `build_car.py`: procedural sports car + sunset scene for Blender (tested with pip `bpy` 5.2.2, CPU).
  Final renders: `car_render_hero.png`, `car_render_rear.png` (1920x1080).
- `export_roblox.py` produced `roblox_export/SportsCar.fbx` (+ `tex/`, `manifest.json`): 10 MeshParts
  (Body, CabinGlass, CabinFrame, Details, Trim, Interior, Wheel_FL/FR/RL/RR), each at most 17k tris,
  colour textures embedded, 1 stud = 0.28 m (~16.4 studs long), faces -Z, +Y up, right side +X.
  The new body (front-engine GT proportions, see README) is checked only by re-importing into Blender.
  The earlier version of the car was driven in Studio; this one has not been re-tested there.
- `CarAssembly.server.luau`: welds parts, invisible cylinder wheel colliders, hinge motors, front servo
  steering, VehicleSeat. Constants: `CAR_SCALE` (1.6, because an avatar is taller than the cabin at 1x),
  `DRIVE_SIGN`, `STEER_SIGN`.

## Not done / untested
- The new export (new body, new `Trim` part, seat moved to x = -0.36 m) has not been imported into Studio.
- No Roblox connector or desktop control was available in the cloud session.
- Likely first checks: the `Trim` part is welded (mirrors, exhausts, splitter, diffuser stay on the car),
  the driver sits in the seat with the head under the roof, and the wider track still steers cleanly.

## Prompt for the new session
> Clone `archersugarman-wq/claudecode` branch `claude/sleepy-hamilton-9ma2tr` and read `blender_car/HANDOFF.md`.
> Then, using computer use on this machine, open Roblox Studio, import
> `blender_car/roblox_export/SportsCar.fbx` with File > Import 3D as a Model, name the model `SportsCar`
> in Workspace, add `blender_car/CarAssembly.server.luau` to ServerScriptService as a Script, press Play and
> fix whatever breaks (part names, wheel axes, driving/steering direction, collisions). Don't claim it works
> until you've driven it in Play mode and seen it.
