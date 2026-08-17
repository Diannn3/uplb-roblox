-- MainServer.server.lua
-- Entry point for all server-side logic in the UPLB Roblox project

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")
local Shared = ReplicatedStorage:WaitForChild("Shared")
local Constants = require(Shared:WaitForChild("Constants"))
local WorldGenerator = require(script.Parent:WaitForChild("WorldGenerator"))

print("UPLB Server initialized! Running " .. Constants.PROJECT_NAME)
WorldGenerator.Generate()

-- The generated terrain sits above the blank-place default spawn.  Move each
-- character to the owned Oblation spawn after the authoritative world exists.
local function placeCharacter(character)
    local spawn = workspace.GeneratedVerticalSlice_v01.Debug:FindFirstChild("GeneratedSpawnLocation")
    if spawn and character then
        character:PivotTo(CFrame.new(spawn.Position + Vector3.new(0, 4, 0)))
    end
end

local function bindPlayer(player)
    player.CharacterAdded:Connect(function(character)
        task.delay(1, placeCharacter, character)
    end)
    task.spawn(function()
        for _ = 1, 50 do
            if player.Character then
                task.wait(1)
                placeCharacter(player.Character)
                return
            end
            task.wait(0.1)
        end
    end)
end

Players.PlayerAdded:Connect(bindPlayer)
for _, player in ipairs(Players:GetPlayers()) do
    bindPlayer(player)
end

-- Studio can finish attaching the test character after PlayerAdded has
-- already fired.  Keep a short bounded reconciliation loop so the first
-- client still lands on the generated terrain without an unbounded heartbeat.
task.spawn(function()
    for _ = 1, 20 do
        for _, player in ipairs(Players:GetPlayers()) do
            if player.Character then
                placeCharacter(player.Character)
            end
        end
        task.wait(0.5)
    end
end)
