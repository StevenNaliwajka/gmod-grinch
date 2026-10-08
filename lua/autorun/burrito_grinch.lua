-- Burrito Grinch (Ultimatum): the dancing Grinch in a leather jacket and jeans,
-- from PilotRedSun's "The Grinch's Ultimatum" (1:30), as a player model.
local NAME  = "Burrito Grinch (Ultimatum)"
local MODEL = "models/player/burrito/grinch_ultimatum.mdl"
local HANDS = "models/weapons/burrito/c_arms_grinch.mdl"

player_manager.AddValidModel(NAME, MODEL)
list.Set("PlayerOptionsModel", NAME, MODEL)
if file.Exists(HANDS, "GAME") then
    player_manager.AddValidHands(NAME, HANDS, 0, "00000000")
end

if SERVER then
    -- clients of a server that installed this from git get the Lua, not the content
    resource.AddFile(MODEL)
    if file.Exists(HANDS, "GAME") then resource.AddFile(HANDS) end
    for _, f in ipairs(file.Find("materials/models/player/burrito/grinch_ultimatum/*.vmt", "GAME")) do
        resource.AddFile("materials/models/player/burrito/grinch_ultimatum/" .. f)
    end
    resource.AddFile("materials/spawnicons/models/player/burrito/grinch_ultimatum.png")
end
