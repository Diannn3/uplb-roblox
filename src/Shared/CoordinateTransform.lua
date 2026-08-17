-- CoordinateTransform.lua
-- Shared local-metre <-> Roblox-stud contract.

local CoordinateTransform = {}

CoordinateTransform.MetersPerStud = 0.28

function CoordinateTransform.MetersToStuds(meters)
    return meters / CoordinateTransform.MetersPerStud
end

function CoordinateTransform.StudsToMeters(studs)
    return studs * CoordinateTransform.MetersPerStud
end

function CoordinateTransform.LocalToStuds(eastM, northM, elevationM)
    -- Canonical local north maps to Roblox -Z; elevation is relative to the
    -- approved world base datum, never an absolute WGS84/EGM96 value.
    return Vector3.new(
        CoordinateTransform.MetersToStuds(eastM),
        CoordinateTransform.MetersToStuds(elevationM),
        CoordinateTransform.MetersToStuds(-northM)
    )
end

function CoordinateTransform.StudsToLocal(position)
    return {
        eastM = CoordinateTransform.StudsToMeters(position.X),
        northM = CoordinateTransform.StudsToMeters(-position.Z),
        elevationM = CoordinateTransform.StudsToMeters(position.Y),
    }
end

return CoordinateTransform

