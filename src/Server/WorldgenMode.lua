-- Explicit world-generation mode gate.
--
-- Production places are expected to contain a baked, validated world. The
-- server must not regenerate a large terrain heightfield on every live boot.
-- Studio/MCP callers set Workspace.UPLBWorldgenMode before invoking a preview
-- or an edit-mode bake.

local Workspace = game:GetService("Workspace")
local RunService = game:GetService("RunService")

local WorldgenMode = {}

WorldgenMode.MODES = {
    EDIT_BAKE = "EDIT_BAKE",
    STUDIO_RUNTIME_PREVIEW = "STUDIO_RUNTIME_PREVIEW",
    VALIDATE_EXISTING = "VALIDATE_EXISTING",
    PRODUCTION_STATIC = "PRODUCTION_STATIC",
}

local function configuredMode()
    local requested = Workspace:GetAttribute("UPLBWorldgenMode")
    if type(requested) == "string" and WorldgenMode.MODES[string.upper(requested)] then
        return string.upper(requested)
    end
    return WorldgenMode.MODES.PRODUCTION_STATIC
end

function WorldgenMode.Get()
    return configuredMode()
end

function WorldgenMode.ShouldGenerate()
    local mode = configuredMode()
    return mode == WorldgenMode.MODES.EDIT_BAKE or (mode == WorldgenMode.MODES.STUDIO_RUNTIME_PREVIEW and RunService:IsStudio())
end

function WorldgenMode.IsStatic()
    local mode = configuredMode()
    return mode == WorldgenMode.MODES.PRODUCTION_STATIC or mode == WorldgenMode.MODES.VALIDATE_EXISTING
end

return WorldgenMode
