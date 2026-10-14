--!strict
-- CarAssembly: turns the imported SportsCar model into a drivable vehicle.
-- Tested in Studio: W/A/S/D drive, steer and reverse. Walk up and press E ("Drive") to get in, Space to get out;
-- the driver sees a mph speedometer.
--
-- Setup
--   1. Studio: File > Import 3D > roblox_export/SportsCar.fbx, import as a Model (name SportsCar).
--      Expected children: Body, CabinGlass, CabinFrame, Details, Interior, Wheel_FL/FR/RL/RR.
--   2. The import arrives 100x too big and facing +Z. In the Command Bar run:
--        local m = workspace.SportsCar; m:ScaleTo(0.01); m:PivotTo(CFrame.new(0, 0.5, 0) * CFrame.Angles(0, math.pi, 0))
--      (pivot is at ground level under the wheel centroid, so this sits it on a flat floor facing -Z).
--   3. Put THIS file in ServerScriptService as a Script (RunContext = Legacy or Server) and press Play.
--
-- The car faces -Z (VehicleSeat forward), right side is +X. The FBX is 1 stud = 0.28 m, so the car is
-- ~16 studs long. A Roblox avatar is ~5 studs tall and the cabin is only ~2.8 studs high at that
-- size, so CAR_SCALE enlarges the whole car; lower it if you want the original proportions.

local RunService = game:GetService("RunService")

local CAR_SCALE = 1.6        -- uniform scale applied to the imported model
local MAX_SPEED = 90         -- studs/s at full throttle
local MOTOR_TORQUE = 3e4
local MAX_STEER_DEG = 28
local DRIVE_SIGN = -1        -- verified in Studio: -1 makes W drive forward (-Z)
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
	model:ScaleTo(model:GetScale() * CAR_SCALE)
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
-- CollisionFidelity is not writable from scripts; set it on Body in Studio (edit mode) instead
body.CustomPhysicalProperties = PhysicalProperties.new(0.35, 0.4, 0.1, 1, 1)

local glass = find("CabinGlass")
-- dark tinted glass, like the Blender render (the FBX glass has no texture)
glass.Material = Enum.Material.Glass
glass.Color = Color3.fromRGB(28, 34, 40)
glass.Transparency = 0.35
glass.Reflectance = 0.15
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

-- car frame from the wheels, so it is right whichever way the model is turned:
-- origin = Blender 0,0,0 (centroid of the wheel centres, dropped by one wheel radius), X = right, Y = up, look = forward.
-- (The Body part's own rotation can't be used: the import flips it, which sat the driver facing backwards.)
local sum = Vector3.zero
for _, n in wheelNames do
	sum += find(n).Position
end
local origin = sum / 4 - Vector3.new(0, wheelR, 0)
local right = ((find("Wheel_FR").Position + find("Wheel_RR").Position) - (find("Wheel_FL").Position + find("Wheel_RL").Position)).Unit
local carCF = CFrame.fromMatrix(origin, right, Vector3.yAxis)

local seat = Instance.new("VehicleSeat")
seat.Name = "DriverSeat"
seat.Size = Vector3.new(2, 0.5, 2) * CAR_SCALE
seat.Transparency = 1
seat.CanCollide = false
seat.Massless = true
seat.MaxSpeed = 0 -- we drive the wheels ourselves
seat.Torque = 0
seat.TurnSpeed = 0
seat.HeadsUpDisplay = false -- replaced by the speedometer below
-- 0.40 m: on the seat cushion, which export_roblox.py lowers 10 cm so a seated avatar's head clears the roof
seat.CFrame = carCF * CFrame.new(fromBlender(-0.28, 0.37, 0.40))
seat.Parent = model
weld(body, seat)

-- the seat is buried inside the body, so touching it never seats anyone: use a prompt (Space gets out as usual)
local prompt = Instance.new("ProximityPrompt")
prompt.ActionText = "Drive"
prompt.ObjectText = "Sports Car"
prompt.KeyboardKeyCode = Enum.KeyCode.E
prompt.MaxActivationDistance = 14 * CAR_SCALE / 1.6
prompt.RequiresLineOfSight = false
prompt.Parent = seat
prompt.Triggered:Connect(function(player: Player)
	local humanoid = player.Character and player.Character:FindFirstChildOfClass("Humanoid")
	if humanoid and humanoid.Health > 0 and not seat.Occupant then
		seat:Sit(humanoid)
	end
end)
seat:GetPropertyChangedSignal("Occupant"):Connect(function()
	prompt.Enabled = seat.Occupant == nil
end)

-- ---------------------------------------------------------------- speedometer
-- shown only to the driver; 1 stud = 0.28 m (Roblox's usual avatar scale) for the mph figure
local MPH_PER_STUD_S = 0.28 * 2.23694
local speedLabel: TextLabel? = nil

local function removeSpeedometer()
	if speedLabel then
		(speedLabel.Parent :: Instance):Destroy()
		speedLabel = nil
	end
end

seat:GetPropertyChangedSignal("Occupant"):Connect(function()
	removeSpeedometer()
	local humanoid = seat.Occupant
	local player = humanoid and game:GetService("Players"):GetPlayerFromCharacter(humanoid.Parent)
	if not player then
		return
	end
	local gui = Instance.new("ScreenGui")
	gui.Name = "SportsCarSpeedometer"
	gui.ResetOnSpawn = false
	local label = Instance.new("TextLabel")
	label.AnchorPoint = Vector2.new(0.5, 1)
	label.Position = UDim2.new(0.5, 0, 1, -24)
	label.Size = UDim2.fromOffset(220, 56)
	label.BackgroundColor3 = Color3.fromRGB(18, 20, 24)
	label.BackgroundTransparency = 0.25
	label.TextColor3 = Color3.new(1, 1, 1)
	label.Font = Enum.Font.GothamBold
	label.TextSize = 30
	label.Text = "0 mph"
	label.Parent = gui
	Instance.new("UICorner", label).CornerRadius = UDim.new(0, 10)
	gui.Parent = player:WaitForChild("PlayerGui")
	speedLabel = label
end)

-- ---------------------------------------------------------------- wheels
type Wheel = { motor: HingeConstraint, servo: HingeConstraint? }
local wheels: { Wheel } = {}

local function attachment(parent: BasePart, worldPos: Vector3, rot: CFrame): Attachment
	local a = Instance.new("Attachment")
	-- rot is a WORLD orientation: Body is rotated 180 degrees in the world, so a part-local rot would flip hinge axes
	a.CFrame = parent.CFrame:Inverse() * (CFrame.new(worldPos) * rot)
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
	col.CustomPhysicalProperties = PhysicalProperties.new(0.4, 1.4, 0.05, 1, 1)
	col.Parent = model
	weld(col, mesh)
	-- hinged parts still collide with each other: without this the wheel cylinders fight the body hull
	local nc = Instance.new("NoCollisionConstraint")
	nc.Part0 = body
	nc.Part1 = col
	nc.Parent = col

	local alongX = CFrame.identity
	local alongY = CFrame.Angles(0, 0, math.rad(90)) -- maps the attachment X axis (hinge axis) onto world Y

	if front then
		local knuckle = Instance.new("Part")
		knuckle.Name = n .. "_Knuckle"
		knuckle.Size = Vector3.one * 1
		knuckle.CFrame = CFrame.new(pos)
		knuckle.Transparency = 1
		knuckle.CanCollide = false
		knuckle.Massless = false
		knuckle.CustomPhysicalProperties = PhysicalProperties.new(2, 0, 0, 1, 1)
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
		motor.MotorMaxAcceleration = 60
		motor.Parent = col
		table.insert(wheels, { motor = motor, servo = servo })
	else
		local motor = Instance.new("HingeConstraint")
		motor.ActuatorType = Enum.ActuatorType.Motor
		motor.Attachment0 = attachment(body, pos, alongX)
		motor.Attachment1 = attachment(col, pos, alongX)
		motor.MotorMaxTorque = MOTOR_TORQUE
		motor.MotorMaxAcceleration = 60
		motor.Parent = col
		table.insert(wheels, { motor = motor, servo = nil })
	end
end

-- ---------------------------------------------------------------- driving
RunService.Heartbeat:Connect(function()
	local throttle = seat.ThrottleFloat
	local steer = seat.SteerFloat
	local w = DRIVE_SIGN * throttle * MAX_SPEED / wheelR
	-- full lock at speed spins the car, so the steering lock shrinks as speed rises
	local speed = body.AssemblyLinearVelocity.Magnitude
	local lock = MAX_STEER_DEG * math.clamp(1 - 0.8 * speed / MAX_SPEED, 0.2, 1)
	for _, wh in wheels do
		wh.motor.AngularVelocity = w
		if wh.servo then
			wh.servo.TargetAngle = STEER_SIGN * -steer * lock
		end
	end
	if speedLabel then
		speedLabel.Text = string.format("%d mph", math.floor(speed * MPH_PER_STUD_S + 0.5))
	end
end)
