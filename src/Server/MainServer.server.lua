-- MainServer.server.lua
-- Entry point for all server-side logic in the UPLB Roblox project

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")
local Shared = ReplicatedStorage:WaitForChild("Shared")
local Constants = require(Shared:WaitForChild("Constants"))
local WorldGenerator = require(script.Parent:WaitForChild("WorldGenerator"))
local WorldgenMode = require(script.Parent:WaitForChild("WorldgenMode"))

print("UPLB Server initialized! Running " .. Constants.PROJECT_NAME)
local mode = WorldgenMode.Get()
if WorldgenMode.ShouldGenerate() then
    print("UPLB world-generation mode: " .. mode)
    WorldGenerator.Generate()
else
    print("UPLB world-generation mode: " .. mode .. " (using existing baked world)")
end

-- The generated terrain sits above the blank-place default spawn.  Move each
-- character to the owned Oblation spawn after the authoritative world exists.
local function placeCharacterOnce(player, character)
    if not character or character:GetAttribute("UPLBSpawnPlaced") then
        return
    end
    local root = workspace:FindFirstChild("GeneratedVerticalSlice_v01")
    local debugFolder = root and root:FindFirstChild("Debug")
    local spawn = debugFolder and debugFolder:FindFirstChild("GeneratedSpawnLocation")
    if not spawn then
        return
    end
    local rootPart = character:FindFirstChild("HumanoidRootPart") or character:WaitForChild("HumanoidRootPart", 5)
    if not rootPart then
        return
    end
    character:PivotTo(CFrame.new(spawn.Position + Vector3.new(0, 4, 0)))
    character:SetAttribute("UPLBSpawnPlaced", true)
    player:SetAttribute("UPLBSpawnPlacementStatus", "placed")
end

local function bindPlayer(player)
    player.CharacterAdded:Connect(function(character)
        task.defer(placeCharacterOnce, player, character)
    end)
    if player.Character then
        task.defer(placeCharacterOnce, player, player.Character)
    end
end

Players.PlayerAdded:Connect(bindPlayer)
for _, player in ipairs(Players:GetPlayers()) do
    bindPlayer(player)
end
