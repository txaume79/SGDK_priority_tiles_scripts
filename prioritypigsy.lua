-- !/bin/lua
-- modified pigy's lua script described here https://youtu.be/uvsgg4YbJRk?list=PL1xqkpO_SvY2_rSwHTBIBxXMqmek--GAb
-- that fixes the need to select the prio layer before running, can be runned from shell and fixed some bugs that
-- i found that forced me to run more than once the original script. CREDITS TO MASTER PIGSY. 

local spr = app.activeSprite
if not spr then return end

--  Find "high_prio"
local target_layer = nil
for i, layer in ipairs(spr.layers) do
  if layer.name == "high_prio" then
    target_layer = layer
    break
  end
end
if not target_layer then
  app.alert('"high_prio" named layer not found, giving up...')
  return
end

-- Pigsy knows... 
for _, frame in ipairs(spr.frames) do
  local cel = target_layer:cel(frame.frameNumber)
  if cel and cel.image then
    local img = cel.image
    local cx0, cy0 = cel.position.x, cel.position.y
    local cx1 = cx0 + cel.bounds.width
    local cy1 = cy0 + cel.bounds.height

    for tx = cx0, cx1-1, 8 do
      for ty = cy0, cy1-1, 8 do
        local present = false
        for x = tx, tx+7 do
          for y = ty, ty+7 do
            if x >= cx0 and y >= cy0 and x < cx1 and y < cy1 then
              if img:getPixel(x-cx0, y-cy0) > 0 then
                present = true
                break
              end
            end
          end
          if present then break end
        end
        if present then
          for x = tx, tx+7 do
            for y = ty, ty+7 do
              if x >= cx0 and y >= cy0 and x < cx1 and y < cy1 then
                local px = img:getPixel(x-cx0, y-cy0)
                if px < 64 then
                  img:putPixel(x-cx0, y-cy0, px + 128)
                end
              end
            end
          end
        end
      end
    end
  end
end

-- Merge frame 1 layers -- if you have more, will not be processed... i guess
app.command.MergeDownLayer{}

-- Force indexed mode, just in case
if spr.colorMode ~= ColorMode.INDEXED then
  app.command.ChangePixelFormat{ format="indexed" }
end

-- Export indexed png 
local filename = app.params["filename"] or spr.filename
local output = filename:gsub("%.aseprite$", ".png")

app.command.SaveFile {
  ui=false,
  recent=false,
  filename=output,
  filenameFormat='{path}/{title}-{layer}-{frame}.png',
}

