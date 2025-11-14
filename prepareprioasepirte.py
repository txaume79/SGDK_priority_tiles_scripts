#!/bin/python
# PLEASE NOTE: 
# Prepared to run under WSL2, so change the ASEPRITE_PATH and what's needed on de cmds to run on pure linux console.
# should not be hard for you. 
# what does it do? processes a tmx file with an associated png file to prepare an aseprite file that complies
# with a modified version of Pigsy's lua script and run it, so at the end you get a png with priority tiles
# ready to use with resources.res sgdk 
# So you need a tmx file with 2 layers, main with the full tile description and high_prio layer binary mask
# where 0 is a low prio tile and 1 is high. 
# VEEEEERY IMPORTANT, you need a palette that follows that scheme
# 64 colors where 
# 0 ...15 will be used as PAL0 
# 16...31 as PAL1 
# 32...47 as PAL2
# 48...63 as PAL3
# each of them with 0,16,32,48 as trasparent index
# 64...127 with the same indexed color
# 128...191 with the same - other - indexed color
# fit your 16 color png palettes in one of the PALx rows. If not, this script is useless. Anyway, there's an example
# palette to get a visual approach. 
# That's all - your images will be saved as original_png_file_name_map--0.png - well, it's not my best point getting names and
# so lazy at the end ;) 
# put those files on your resources.res and good luck... i usually load them with VDP_loadTileData and VDP_setTileMapEx as i want just to load
# a portion of a map that contains an animation - not the whole map. 
# do not use TILE_ATTR_FULL or TILE_ATTR as the images should carry all that info.
# SHARE, MODIFY, BLAME AT YOUR SCREEN. 

import os
import sys
from PIL import Image
from lxml import etree



# change it to your needs
ASEPRITE_PATH = '/mnt/c/XXXX/XXXX/XXXX/XXXXXX/Aseprite-v1.3.9.2-x64-Portable/Aseprite-v1.3.9.2-x64/Aseprite.exe'
LUA_SCRIPT = 'add_mask_layer.lua'  # ruta relativa o absoluta si prefieres

def wsl_to_windows_path(path):
    if path.startswith('/mnt/'):
        parts = path.split('/')
        drive = parts[2].upper() + ':'
        return f"{drive}/" + "/".join(parts[3:])
    return path.replace('\\', '/')

def parse_tmx(tmx_path):
    with open(tmx_path, 'r', encoding='utf-8') as f:
        tree = etree.parse(f)
    root = tree.getroot()
    img_source = root.find('.//image').attrib['source']
    width = int(root.attrib['width'])
    height = int(root.attrib['height'])
    tilewidth = int(root.attrib['tilewidth'])
    tileheight = int(root.attrib['tileheight'])
    layers = []
    for layer in root.findall('./layer'):
        data = layer.find('data').text.strip().replace('\n', '')
        arr = [int(d) for d in data.split(',')]
        layers.append({
            "name": layer.attrib["name"],
            "width": int(layer.attrib["width"]),
            "height": int(layer.attrib["height"]),
            "data": arr,
        })
    return img_source, (width, height, tilewidth, tileheight), layers

def create_mask_layer(img, layers, geom):
    width, height, tilewidth, tileheight = geom
    high_prio = layers[1]["data"]
    mask = Image.new('RGBA', img.size, (0,0,0,0))
    for y in range(height):
        for x in range(width):
            idx = y * width + x
            if high_prio[idx] == 1:
                box = (x*tilewidth, y*tileheight, (x+1)*tilewidth, (y+1)*tileheight)
                tile = img.crop(box)
                mask.paste(tile, box)
    return mask

# changes the file to process on the called lua script
def update_lua_vars(lua_file, new_mask_path, new_pal_path):
    with open(lua_file, 'r') as f:
        lines = f.readlines()
    with open(lua_file, 'w') as f:
        for line in lines:
            if line.strip().startswith("local mask ="):
                f.write(f'local mask = "{new_mask_path}"\n')
            elif line.strip().startswith("local palette ="):
                f.write(f'local palette = "{new_pal_path}"\n')
            else:
                f.write(line)

# restore the same lines from above
def restore_lua_vars(lua_file):
    with open(lua_file, 'r') as f:
        lines = f.readlines()
    with open(lua_file, 'w') as f:
        for line in lines:
            if line.strip().startswith("local mask ="):
                f.write('local mask = "RUTA_CAMBIADA_POR_PYTHON"\n')
            elif line.strip().startswith("local palette ="):
                f.write('local palette = "RUTA_CAMBIADA_POR_PYTHON_PAL"\n')
            else:
                f.write(line)

def main():
    if len(sys.argv) != 2:
        print("Usw: python prepareprioaseprite.py <palette.pal>")
        sys.exit(1)
    pal_path_wsl = os.path.abspath(sys.argv[1])
    pal_path_win = wsl_to_windows_path(pal_path_wsl)
    aseprite_path_linux = ASEPRITE_PATH
    lua_script_path = os.path.abspath(LUA_SCRIPT)
    lua_script_win = wsl_to_windows_path(lua_script_path)

    for fname in os.listdir('.'):
        if fname.endswith('.tmx'):
            print(f"> Processing {fname}")
            try:
                img_src, geom, layers = parse_tmx(fname)
            except Exception as e:
                print(f"Read error: {fname}: {e}")
                continue

            if not os.path.isfile(img_src):
                print(f"Tmx referred PNG missing: {img_src}!")
                continue

            img = Image.open(img_src).convert('RGBA')
            fg_tmp_wsl = os.path.abspath(f'_fg_{fname}.png')
            fg_tmp_win = wsl_to_windows_path(fg_tmp_wsl)
            mask_tmp_wsl = os.path.abspath(f'_mask_{fname}.png')
            mask_tmp_win = wsl_to_windows_path(mask_tmp_wsl)

            img.save(fg_tmp_wsl)
            mask = create_mask_layer(img, layers, geom)
            mask.save(mask_tmp_wsl)

            out_ase_wsl = os.path.abspath(os.path.splitext(fname)[0] + ".aseprite")
            out_ase_win = wsl_to_windows_path(out_ase_wsl)

            # Create base ase file
            cmd1 = f'"{aseprite_path_linux}" -b "{fg_tmp_win}" --save-as "{out_ase_win}" --palette "{pal_path_win}"'
            res1 = os.system(cmd1)
            if res1 != 0:
                print("Lua Aseprite CLI script failed step 1!")
                continue

            # edit local mask = ... line on lua before running it
            update_lua_vars(lua_script_path, mask_tmp_win, pal_path_win)

            cmd2 = (
                f'"{aseprite_path_linux}" -b "{out_ase_win}" '
                f'--script "{lua_script_win}" '
            )
           
            res2 = os.system(cmd2)
            if res2 != 0:
                print("Lua Aseprite CLI script failed step 2!")

            cmd3 = (f'"{aseprite_path_linux}" -b "{out_ase_win}" '
                    f'--color-mode indexed  --save-as  "{out_ase_win}"')    
            res3 = os.system(cmd3)
            if res3 != 0:
                print("Lua Aseprite CLI script failed step 3!")

            restore_lua_vars(lua_script_path)
            print(f"  -> {out_ase_win} both layers made.")
            print(f"  [PNG TEMP] {fg_tmp_win}")
            print(f"  [PNG TEMP] {mask_tmp_win}")
            print("launching priority tile aseprite script")
            cmd4 = (f'"{aseprite_path_linux}" -b "{out_ase_win}" '
                    f'--script prioritypigsy.lua')    
            res4 = os.system(cmd4)
            if res4 != 0:
                print("Lua Aseprite CLI script failed step 4!")

if __name__ == "__main__":
    main()
