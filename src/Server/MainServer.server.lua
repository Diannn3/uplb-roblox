-- MainServer.server.lua
-- Entry point for all server-side logic in the UPLB Roblox project

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Shared")
local Constants = require(Shared:WaitForChild("Constants"))

print("UPLB Server initialized! Running " .. Constants.PROJECT_NAME)
