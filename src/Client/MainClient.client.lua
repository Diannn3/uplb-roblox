-- MainClient.client.lua
-- Entry point for all client-side logic in the UPLB Roblox project

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Shared")
local Constants = require(Shared:WaitForChild("Constants"))

print("UPLB Client initialized! Welcome to " .. Constants.PROJECT_NAME)
