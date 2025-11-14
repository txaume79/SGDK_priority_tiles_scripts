--!/bin/lua
-- prepares a aseprite file to be processed with a modified Pigsy's priority layer lua script ase
-- it is described here https://youtu.be/uvsgg4YbJRk?list=PL1xqkpO_SvY2_rSwHTBIBxXMqmek--GAb
local mask = "RUTA_CAMBIADA_POR_PYTHON"
local palette = "RUTA_CAMBIADA_POR_PYTHON_PAL"
local app = app
app.transaction(function()


local layername = "high_prio"
local sprite = app.activeSprite

local site = app.site
if not sprite or not mask or #mask == 0 then
    print("ERROR: falta sprite o mask ("..tostring(mask)..")")
    app.exit()
end

app.open(mask)



local spr_mask = app.activeSprite
local mask_img = spr_mask.cels[1].image
spr_mask:loadPalette(palette)
sprite:loadPalette(palette)
local new_layer = sprite:newLayer()
new_layer.name = layername
local new_cel = sprite:newCel(new_layer, 1)

new_cel.image = mask_img

sprite:saveAs(sprite.filename)
end)

app.exit()