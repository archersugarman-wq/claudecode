--!strict
-- CarAssembly: turns the imported SportsCar model into a drivable vehicle.
-- NOT TESTED IN STUDIO (written without access to Studio). Expect to tweak the constants below.
--
-- Setup
--   1. Studio: File > Import 3D > roblox_export/SportsCar.fbx, import as a Model (keep textures on).
--      Expected children: Body, CabinGlass, CabinFrame, Details, Interior, Wheel_FL/FR/RL/RR.
--   2. Rename the Model to "SportsCar" and put it in Workspace, sitting upright, not rotated.
--   3. Put THIS file in ServerScriptService as a Script (RunContext = Legacy or Server) and press Play.
--
-- The car faces -Z (VehicleSeat forward), right side is +X. The FBX is 1 stud = 0.28 m, so the car is
-- ~16 studs long. A Roblox avatar is ~5 studs tall and the cabin is only ~2.8 studs high at that
-- size, so CAR_SCALE enlarges the whole car; lower it if you want the original proportions.

local RunService = game:GetService("RunService")

local CAR_SCALE = 1.6        -- uniform scale applied to the imported model
local MAX_SPEED = 90         -- studs/s at full throttle
local MOTOR_TORQUE = 6e5
local MAX_STEER_DEG = 28
local DRIVE_SIGN = 1         -- flip to -1 if the car drives backwards on W
local STEER_SIGN = 1         -- flip to -1 if steering is mirrored

local STUD = 1 / 0.28
local WHEEL_R_BLENDER = 0.345 * STUD   -- studs before CAR_SCALE
local WHEEL_W_BLENDER = 1.02

local model = workspace:WaitForChild("SportsCar") :: Model
local function find(name: string): BasePart
	local p = model:FindFirstChild(name, true)
	assert(p and p:IsA("BasePart"), "SportsCar is missing part " .. name)
	return p :: BasePart
end

local body = find("Body")
model.PrimaryPart = body
if CAR_SCALE ~= 1 then
	model:ScaleTo(CAR_SCALE)
end
local wheelR = WHEEL_R_BLENDER * CAR_SCALE
local wheelW = WHEEL_W_BLENDER * CAR_SCALE

-- ---------------------------------------------------------------- parts & materials
local wheelNames = { "Wheel_FL", "Wheel_FR", "Wheel_RL", "Wheel_RR" }
local wheelSet: { [string]: boolean } = {}
for _, n in wheelNames do
	wheelSet[n] = true
end

for _, d in model:GetDescendants() do
	if d:IsA("BasePart") then
		d.Anchored = false
		d.CanCollide = false
		d.CanTouch = false
		d.CanQuery = true
		d.Massless = true
	end
end
body.Massless = false
body.CanCollide = true
body.CollisionFidelity = Enum.CollisionFidelity.Hull
body.CustomPhysicalProperties = PhysicalProperties.new(0.35, 0.4, 0.1, 1, 1)

local glass = find("CabinGlass")
glass.Material = Enum.Material.Glass
glass.Transparency = 0.55
glass.Reflectance = 0.1
glass.CastShadow = false

local function weld(a: BasePart, b: BasePart)
	local w = Instance.new("WeldConstraint")
	w.Part0 = a
	w.Part1 = b
	w.Parent = b
end

for _, n in { "CabinGlass", "CabinFrame", "Details", "Interior" } do
	weld(body, find(n))
end

-- ---------------------------------------------------------------- seat
-- Blender (x fwd, y left, z up) metres -> Roblox offset from the car origin, in studs
local function fromBlender(x: number, y: number, z: number): Vector3
	return Vector3.new(-y, z, -x) * STUD * CAR_SCALE
end

-- car origin (Blender 0,0,0 at ground level): centroid of the four wheel centres, dropped by one wheel radius
local sum = Vector3.zero
for _, n in wheelNames do
	sum += find(n).Position
end
local origin = sum / 4 - Vector3.new(0, wheelR, 0)

local seat = Instance.new("VehicleSeat")
seat.Name = "DriverSeat"
seat.Size = Vector3.new(2, 0.5, 2) * CAR_SCALE
seat.Transparency = 1
seat.CanCollide = false
seat.Massless = true
seat.MaxSpeed = 0 -- we drive the wheels ourselves
seat.Torque = 0
seat.TurnSpeed = 0
seat.CFrame = CFrame.new(origin + fromBlender(-0.28, 0.37, 0.50)) * body.CFrame.Rotation
seat.Parent = model
weld(body, seat)

-- ---------------------------------------------------------------- wheels
type Wheel = { motor: HingeConstraint, servo: HingeConstraint? }
local wheels: { Wheel } = {}

local function attachment(parent: BasePart, worldPos: Vector3, rot: CFrame): Attachment
	local a = Instance.new("Attachment")
	a.CFrame = (parent.CFrame:Inverse() * CFrame.new(worldPos)) * rot
	a.Parent = parent
	return a
end

for _, n in wheelNames do
	local mesh = find(n)
	local pos = mesh.Position
	local front = string.sub(n, 7, 7) == "F"

	-- invisible cylinder that actually touches the road (Roblox cylinders spin about their X axis)
	local col = Instance.new("Part")
	col.Name = n .. "_Collider"
	col.Shape = Enum.PartType.Cylinder
	col.Size = Vector3.new(wheelW, wheelR * 2, wheelR * 2)
	col.CFrame = CFrame.new(pos)
	col.Transparency = 1
	col.CanCollide = true
	col.CustomPhysicalProperties = PhysicalProperties.new(0.7, 1.4, 0.05, 1, 1)
	col.Parent = model
	weld(col, mesh)

	local alongX = CFrame.identity
	local alongY = CFrame.Angles(0, 0, math.rad(90)) -- maps the attachment X axis (hinge axis) onto world Y

	if front then
		local knuckle = Instance.new("Part")
		knuckle.Name = n .. "_Knuckle"
		knuckle.Size = Vector3.one * 0.4
		knuckle.CFrame = CFrame.new(pos)
		knuckle.Transparency = 1
		knuckle.CanCollide = false
		knuckle.Massless = false
		knuckle.CustomPhysicalProperties = PhysicalProperties.new(0.1, 0, 0, 1, 1)
		knuckle.Parent = model

		local servo = Instance.new("HingeConstraint")
		servo.ActuatorType = Enum.ActuatorType.Servo
		servo.Attachment0 = attachment(body, pos, alongY)
		servo.Attachment1 = attachment(knuckle, pos, alongY)
		servo.ServoMaxTorque = 1e7
		servo.AngularSpeed = 6
		servo.LimitsEnabled = true
		servo.LowerAngle = -MAX_STEER_DEG
		servo.UpperAngle = MAX_STEER_DEG
		servo.Parent = body

		local motor = Instance.new("HingeConstraint")
		motor.ActuatorType = Enum.ActuatorType.Motor
		motor.Attachment0 = attachment(knuckle, pos, alongX)
		motor.Attachment1 = attachment(col, pos, alongX)
		motor.MotorMaxTorque = MOTOR_TORQUE
		motor.MotorMaxAcceleration = 400
		motor.Parent = col
		table.insert(wheels, { motor = motor, servo = servo })
	else
		local motor = Instance.new("HingeConstraint")
		motor.ActuatorType = Enum.ActuatorType.Motor
		motor.Attachment0 = attachment(body, pos, alongX)
		motor.Attachment1 = attachment(col, pos, alongX)
		motor.MotorMaxTorque = MOTOR_TORQUE
		motor.MotorMaxAcceleration = 400
		motor.Parent = col
		table.insert(wheels, { motor = motor, servo = nil })
	end
end

-- ---------------------------------------------------------------- driving
RunService.Heartbeat:Connect(function()
	local throttle = seat.ThrottleFloat
	local steer = seat.SteerFloat
	local w = DRIVE_SIGN * throttle * MAX_SPEED / wheelR
	for _, wh in wheels do
		wh.motor.AngularVelocity = w
		if wh.servo then
			wh.servo.TargetAngle = STEER_SIGN * -steer * MAX_STEER_DEG
		end
	end
end)
