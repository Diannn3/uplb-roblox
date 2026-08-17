-- WorldGenerator.lua
-- Server-owned deterministic terrain and greybox placement.

local Workspace = game:GetService("Workspace")

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Shared")
local Generated = Shared:WaitForChild("Generated")

local CoordinateTransform = require(Shared:WaitForChild("CoordinateTransform"))
local Scene = require(Generated:WaitForChild("WorldScene"))

local WorldGenerator = {}

local ROOT_NAME = Scene.runtimeContract.regenerationRoot
local GENERATOR_VERSION = Scene.metadata.generatorVersion or "roblox-scene-luau-v0.1"
local TERRAIN_RESOLUTION = Scene.runtimeContract.terrainResolutionStuds or 4
-- 64x64xY remains below Terrain:WriteVoxels' 4,194,304 voxel limit while
-- keeping the disposable POC to a few hundred owned writes instead of one
-- call per 4-stud cell.
local TERRAIN_CHUNK_CELLS = 64
local TERRAIN_MARGIN_M = 60

local FOLDER_NAMES = {
    "Buildings",
    "Roads",
    "Walkways",
    "Water",
    "GreenSpaceDebug",
    "Landmarks",
    "Debug",
    "Metadata",
}

local function setAttributeIfPresent(instance, name, value)
    if value ~= nil then
        instance:SetAttribute(name, value)
    end
end

local function setProvenance(instance, feature, role)
    local provenance = feature.provenance or {}
    instance:SetAttribute("FeatureId", feature.featureId or feature.id or "")
    instance:SetAttribute("CandidateId", feature.candidateId or "")
    instance:SetAttribute("SourceLifecycle", feature.sourceLifecycle or "candidate")
    instance:SetAttribute("WorldgenRole", role or feature.role or "unknown")
    instance:SetAttribute("DetailTier", feature.detailTier or 0)
    instance:SetAttribute("CanonicalRevision", Scene.metadata.canonicalRevision or "")
    instance:SetAttribute("TerrainRevision", Scene.terrain.revision or "")
    instance:SetAttribute("SceneSpecHash", Scene.metadata.sceneSpecHash or "")
    instance:SetAttribute("GeneratorVersion", GENERATOR_VERSION)
    instance:SetAttribute("InputHash", Scene.metadata.inputHash or "")
    instance:SetAttribute("VerificationStatus", provenance.verificationStatus or Scene.status or "unknown")
    setAttributeIfPresent(instance, "SourceGeometryHash", provenance.sourceGeometryHash)
end

local function createFolder(parent, name)
    local folder = Instance.new("Folder")
    folder.Name = name
    folder.Parent = parent
    return folder
end

local function ownedRoot(root)
    return root
        and root:IsA("Folder")
        and root:GetAttribute("GeneratorVersion") == GENERATOR_VERSION
        and root:GetAttribute("WorldgenRole") == "root"
end

local function resetRoot()
    local existing = Workspace:FindFirstChild(ROOT_NAME)
    if existing then
        if not ownedRoot(existing) then
            error("Refusing to replace an unowned Workspace." .. ROOT_NAME)
        end
        existing:Destroy()
    end

    local root = Instance.new("Folder")
    root.Name = ROOT_NAME
    root.Parent = Workspace
    root:SetAttribute("WorldgenRole", "root")
    root:SetAttribute("GeneratorVersion", GENERATOR_VERSION)
    root:SetAttribute("SceneSpecHash", Scene.metadata.sceneSpecHash or "")
    root:SetAttribute("CanonicalRevision", Scene.metadata.canonicalRevision or "")
    root:SetAttribute("TerrainRevision", Scene.terrain.revision or "")
    root:SetAttribute("WorldgenStatus", Scene.status or "unknown")
    root:SetAttribute("VerticalDatum", Scene.terrain.verticalDatum or "unknown")
    root:SetAttribute("WorldBaseElevationM", Scene.terrain.worldBaseElevationM or 0)
    return root
end

local function makePart(parent, name, size, cframe, material, color, feature, role)
    local part = Instance.new("Part")
    part.Name = name
    part.Anchored = true
    part.Size = size
    part.CFrame = cframe
    part.Material = material
    part.Color = color
    part.TopSurface = Enum.SurfaceType.Smooth
    part.BottomSurface = Enum.SurfaceType.Smooth
    part.Parent = parent
    setProvenance(part, feature, role)
    return part
end

local function featureFolder(root, feature)
    if feature.role == "road" then
        return root.Roads
    elseif feature.role == "walkway" then
        return root.Walkways
    elseif feature.role == "water" then
        return root.Water
    elseif feature.role == "green-space" then
        return root.GreenSpaceDebug
    elseif feature.role == "hero" then
        return root.Landmarks
    elseif feature.role == "context-building" then
        return root.Buildings
    end
    return root.Debug
end

local function localPointToStuds(point, fallbackElevationM)
    local eastM = tonumber(point[1]) or 0
    local northM = tonumber(point[2]) or 0
    local elevationM = tonumber(point[3]) or fallbackElevationM or 0
    return CoordinateTransform.LocalToStuds(eastM, northM, elevationM)
end

local function placeFootprint(root, feature)
    local bounds = feature.runtime and feature.runtime.footprintBoundsLocalMeters
    local placement = feature.placement or {}
    local eastM = tonumber(placement.eastM) or 0
    local northM = tonumber(placement.northM) or 0
    local half = feature.role == "hero" and 4 or 2
    local minEast = bounds and tonumber(bounds.minEastM) or eastM - half
    local maxEast = bounds and tonumber(bounds.maxEastM) or eastM + half
    local minNorth = bounds and tonumber(bounds.minNorthM) or northM - half
    local maxNorth = bounds and tonumber(bounds.maxNorthM) or northM + half
    if math.abs(maxEast - minEast) < 0.01 then
        minEast, maxEast = eastM - half, eastM + half
    end
    if math.abs(maxNorth - minNorth) < 0.01 then
        minNorth, maxNorth = northM - half, northM + half
    end

    local width = math.max(CoordinateTransform.MetersToStuds(maxEast - minEast), 2)
    local depth = math.max(CoordinateTransform.MetersToStuds(maxNorth - minNorth), 2)
    local heightM = tonumber(feature.heightM) or 0
    local height = math.max(CoordinateTransform.MetersToStuds(heightM), 0.35)
    local baseM = tonumber(placement.relativeElevationM) or tonumber(placement.baseElevationM) or 0
    local center = CoordinateTransform.LocalToStuds((minEast + maxEast) / 2, (minNorth + maxNorth) / 2, baseM + heightM / 2)

    local material = Enum.Material.Concrete
    local color = Color3.fromRGB(150, 150, 155)
    if feature.role == "green-space" then
        material = Enum.Material.Grass
        color = Color3.fromRGB(75, 125, 74)
        height = math.max(height, 0.12)
    elseif feature.role == "hero" then
        material = Enum.Material.Brick
        color = Color3.fromRGB(194, 153, 86)
    elseif feature.role == "context-building" then
        color = Color3.fromRGB(125, 135, 150)
    end

    local part = makePart(featureFolder(root, feature), feature.id or feature.featureId, Vector3.new(width, height, depth), CFrame.new(center), material, color, feature, feature.role)
    part:SetAttribute("BaseElevationM", baseM)
    part:SetAttribute("FootprintMinEastM", minEast)
    part:SetAttribute("FootprintMaxEastM", maxEast)
    part:SetAttribute("FootprintMinNorthM", minNorth)
    part:SetAttribute("FootprintMaxNorthM", maxNorth)
    return 1
end

local function placeRoute(root, feature)
    local geometry = feature.geometry or {}
    local points = geometry.centerlineCoordinatesLocalMeters3D or {}
    if #points < 2 then
        return 0
    end
    local widthM = tonumber(feature.widthM) or (feature.role == "road" and 4 or 2.5)
    local thicknessM = feature.role == "road" and 0.28 or (feature.role == "water" and 0.2 or 0.14)
    local folder = featureFolder(root, feature)
    local count = 0
    for index = 1, #points - 1 do
        local startPoint = localPointToStuds(points[index], feature.placement and feature.placement.relativeElevationM)
        local endPoint = localPointToStuds(points[index + 1], feature.placement and feature.placement.relativeElevationM)
        local direction = endPoint - startPoint
        local length = direction.Magnitude
        if length > 0.05 then
            local midpoint = (startPoint + endPoint) / 2
            local cframe = CFrame.lookAt(midpoint, endPoint, Vector3.yAxis)
            local material = feature.role == "road" and Enum.Material.Asphalt or Enum.Material.Concrete
            local color = feature.role == "road" and Color3.fromRGB(58, 61, 67) or Color3.fromRGB(176, 164, 137)
            local canCollide = feature.role ~= "water"
            if feature.role == "water" then
                material = Enum.Material.Water
                color = Color3.fromRGB(54, 130, 180)
            end
            local segment = makePart(folder, string.format("%s_Segment_%04d", feature.id or feature.featureId, index), Vector3.new(CoordinateTransform.MetersToStuds(widthM), CoordinateTransform.MetersToStuds(thicknessM), length), cframe, material, color, feature, feature.role)
            segment.CanCollide = canCollide
            segment.Transparency = feature.role == "water" and 0.35 or 0
            segment:SetAttribute("ParentFeatureId", feature.featureId or feature.id)
            segment:SetAttribute("SegmentIndex", index)
            count += 1
        end
    end
    return count
end

local function terrainBounds()
    local terrain = Scene.terrain
    local minEast, maxEast = math.huge, -math.huge
    local minNorth, maxNorth = math.huge, -math.huge
    for _, feature in ipairs(Scene.objects or {}) do
        local bounds = feature.runtime and feature.runtime.footprintBoundsLocalMeters
        if bounds then
            minEast = math.min(minEast, tonumber(bounds.minEastM) or minEast)
            maxEast = math.max(maxEast, tonumber(bounds.maxEastM) or maxEast)
            minNorth = math.min(minNorth, tonumber(bounds.minNorthM) or minNorth)
            maxNorth = math.max(maxNorth, tonumber(bounds.maxNorthM) or maxNorth)
        end
    end
    local originEast = tonumber(terrain.originEastM) or 0
    local originNorth = tonumber(terrain.originNorthM) or 0
    local spacing = tonumber(terrain.samplingResolutionM) or 30
    local columns = tonumber(terrain.columns) or 0
    local rows = tonumber(terrain.rows) or 0
    local terrainMaxEast = originEast + math.max(columns - 1, 0) * spacing
    local terrainMaxNorth = originNorth + math.max(rows - 1, 0) * spacing
    minEast = math.max(originEast, minEast - TERRAIN_MARGIN_M)
    maxEast = math.min(terrainMaxEast, maxEast + TERRAIN_MARGIN_M)
    minNorth = math.max(originNorth, minNorth - TERRAIN_MARGIN_M)
    maxNorth = math.min(terrainMaxNorth, maxNorth + TERRAIN_MARGIN_M)
    return minEast, maxEast, minNorth, maxNorth
end

local function sampleTerrain(eastM, northM)
    local terrain = Scene.terrain
    local values = terrain.values or {}
    local rows = tonumber(terrain.rows) or 0
    local columns = tonumber(terrain.columns) or 0
    local spacing = tonumber(terrain.samplingResolutionM) or 30
    local originEast = tonumber(terrain.originEastM) or 0
    local originNorth = tonumber(terrain.originNorthM) or 0
    if rows < 2 or columns < 2 then
        return 0
    end
    local col = math.clamp((eastM - originEast) / spacing, 0, columns - 1)
    local row = math.clamp((northM - originNorth) / spacing, 0, rows - 1)
    local c0 = math.floor(col) + 1
    local r0 = math.floor(row) + 1
    local c1 = math.min(c0 + 1, columns)
    local r1 = math.min(r0 + 1, rows)
    local tx, ty = col - math.floor(col), row - math.floor(row)
    local v00 = tonumber(values[r0][c0]) or 0
    local v10 = tonumber(values[r0][c1]) or v00
    local v01 = tonumber(values[r1][c0]) or v00
    local v11 = tonumber(values[r1][c1]) or v01
    local top = v00 + (v10 - v00) * tx
    local bottom = v01 + (v11 - v01) * tx
    return top + (bottom - top) * ty
end

local function writeTerrain()
    local terrain = Workspace.Terrain
    local minEast, maxEast, minNorth, maxNorth = terrainBounds()
    local scale = CoordinateTransform.MetersPerStud
    local minX = math.floor(CoordinateTransform.MetersToStuds(minEast) / TERRAIN_RESOLUTION) * TERRAIN_RESOLUTION
    local maxX = math.ceil(CoordinateTransform.MetersToStuds(maxEast) / TERRAIN_RESOLUTION) * TERRAIN_RESOLUTION
    local minZ = math.floor(CoordinateTransform.MetersToStuds(-maxNorth) / TERRAIN_RESOLUTION) * TERRAIN_RESOLUTION
    local maxZ = math.ceil(CoordinateTransform.MetersToStuds(-minNorth) / TERRAIN_RESOLUTION) * TERRAIN_RESOLUTION
    local minRelative = tonumber(Scene.terrain.relativeMinElevationM) or 0
    local maxRelative = tonumber(Scene.terrain.relativeMaxElevationM) or minRelative + 1
    local minY = math.floor(CoordinateTransform.MetersToStuds(minRelative - 4) / TERRAIN_RESOLUTION) * TERRAIN_RESOLUTION
    local maxY = math.ceil(CoordinateTransform.MetersToStuds(maxRelative + 2) / TERRAIN_RESOLUTION) * TERRAIN_RESOLUTION
    local yCells = math.max(1, math.floor((maxY - minY) / TERRAIN_RESOLUTION))
    local xCells = math.max(1, math.floor((maxX - minX) / TERRAIN_RESOLUTION))
    local zCells = math.max(1, math.floor((maxZ - minZ) / TERRAIN_RESOLUTION))
    local chunks = 0

    for xOffset = 0, xCells - 1, TERRAIN_CHUNK_CELLS do
        local xCount = math.min(TERRAIN_CHUNK_CELLS, xCells - xOffset)
        for zOffset = 0, zCells - 1, TERRAIN_CHUNK_CELLS do
            local zCount = math.min(TERRAIN_CHUNK_CELLS, zCells - zOffset)
            local materials, occupancies = {}, {}
            for x = 1, xCount do
                materials[x], occupancies[x] = {}, {}
                local worldX = minX + (xOffset + x - 0.5) * TERRAIN_RESOLUTION
                local eastM = CoordinateTransform.StudsToMeters(worldX)
                for y = 1, yCells do
                    materials[x][y], occupancies[x][y] = {}, {}
                    local cellBottom = minY + (y - 1) * TERRAIN_RESOLUTION
                    local relativeGroundStuds = CoordinateTransform.MetersToStuds(sampleTerrain(eastM, CoordinateTransform.StudsToMeters(-(minZ + (zOffset + 0.5) * TERRAIN_RESOLUTION))))
                    for z = 1, zCount do
                        local northM = CoordinateTransform.StudsToMeters(-(minZ + (zOffset + z - 0.5) * TERRAIN_RESOLUTION))
                        relativeGroundStuds = CoordinateTransform.MetersToStuds(sampleTerrain(eastM, northM))
                        local occupancy = math.clamp((relativeGroundStuds - cellBottom) / TERRAIN_RESOLUTION, 0, 1)
                        materials[x][y][z] = occupancy > 0 and Enum.Material.Grass or Enum.Material.Air
                        occupancies[x][y][z] = occupancy
                    end
                end
            end
            local region = Region3.new(
                Vector3.new(minX + xOffset * TERRAIN_RESOLUTION, minY, minZ + zOffset * TERRAIN_RESOLUTION),
                Vector3.new(minX + (xOffset + xCount) * TERRAIN_RESOLUTION, maxY, minZ + (zOffset + zCount) * TERRAIN_RESOLUTION)
            ):ExpandToGrid(TERRAIN_RESOLUTION)
            terrain:WriteVoxels(region, TERRAIN_RESOLUTION, materials, occupancies)
            chunks += 1
            task.wait()
        end
    end

    return {
        chunks = chunks,
        minX = minX,
        maxX = maxX,
        minZ = minZ,
        maxZ = maxZ,
        minY = minY,
        maxY = maxY,
        xCells = xCells,
        yCells = yCells,
        zCells = zCells,
    }
end

local function writeMetadata(root, terrainReport, counts)
    local metadata = root.Metadata
    local values = {
        SceneSpecHash = Scene.metadata.sceneSpecHash or "",
        CanonicalRevision = Scene.metadata.canonicalRevision or "",
        InputHash = Scene.metadata.inputHash or "",
        TerrainRevision = Scene.terrain.revision or "",
        GeneratorVersion = GENERATOR_VERSION,
        WorldgenStatus = Scene.status or "unknown",
        VerticalDatum = Scene.terrain.verticalDatum or "unknown",
        TerrainChunks = tostring(terrainReport.chunks),
        ObjectCount = tostring(counts.objects),
        RouteSegmentCount = tostring(counts.routeSegments),
    }
    for name, value in pairs(values) do
        local item = Instance.new("StringValue")
        item.Name = name
        item.Value = value
        item.Parent = metadata
    end
end

local function writeSpawn(root)
    local spawn = Instance.new("SpawnLocation")
    spawn.Name = "GeneratedSpawnLocation"
    spawn.Anchored = true
    spawn.Neutral = true
    spawn.Size = Vector3.new(10, 1, 10)
    local placement = CoordinateTransform.LocalToStuds(0, 0, 9.266667)
    spawn.Position = placement + Vector3.new(0, 3, 0)
    spawn.Material = Enum.Material.Neon
    spawn.Color = Color3.fromRGB(120, 180, 255)
    spawn.Transparency = 0.35
    spawn.Parent = root.Debug
    setProvenance(spawn, {
        featureId = "uplb:spawn:oblation",
        candidateId = "uplb:spawn:oblation",
        sourceLifecycle = "generated",
        detailTier = 0,
        provenance = { verificationStatus = "generated" },
    }, "spawn")
    spawn:SetAttribute("SpawnEastM", 0)
    spawn:SetAttribute("SpawnNorthM", 0)
    spawn:SetAttribute("SpawnElevationM", 9.266667)
    return spawn
end

function WorldGenerator.Generate()
    local root = resetRoot()
    for _, name in ipairs(FOLDER_NAMES) do
        createFolder(root, name)
    end

    local terrainReport = writeTerrain()
    local counts = { objects = 0, routeSegments = 0 }
    for _, feature in ipairs(Scene.objects or {}) do
        local role = feature.role
        if role == "road" or role == "walkway" or role == "water" then
            counts.routeSegments += placeRoute(root, feature)
        else
            counts.objects += placeFootprint(root, feature)
        end
    end
    writeSpawn(root)
    writeMetadata(root, terrainReport, counts)

    local report = {
        status = "pass",
        worldgenStatus = Scene.status or "unknown",
        root = ROOT_NAME,
        objectCount = counts.objects,
        routeSegmentCount = counts.routeSegments,
        terrainChunks = terrainReport.chunks,
        terrainCells = { x = terrainReport.xCells, y = terrainReport.yCells, z = terrainReport.zCells },
    }
    print(string.format("UPLB world generated: %d objects, %d route segments, %d terrain chunks (%s)", report.objectCount, report.routeSegmentCount, report.terrainChunks, report.worldgenStatus))
    return report
end

return WorldGenerator
