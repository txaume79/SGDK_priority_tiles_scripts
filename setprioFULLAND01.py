#!/usr/bin/env python3
# For each tile_priority.json entry it will make:
# - <base>.pal       (16 colors, BGR555, 2 bytes each)
# - <base>_map.tmx   (Tiled TMX no compression; 2 layers: main (tile ref entries) + high_prio(0 and 1))
# - tile_priorities.json on the same path as the images and the script
# anyway, is meant to be launched from editor.py

import json
import os
import struct
import xml.etree.ElementTree as ET
from PIL import Image

TILE_SIZE = 8
PRIORITY_MASK = 0x8000

def rgb888_to_bgr555(rgb):
    r, g, b = rgb
    r5 = (r >> 3) & 0x1F
    g5 = (g >> 3) & 0x1F
    b5 = (b >> 3) & 0x1F
    return (b5 << 10) | (g5 << 5) | r5

def get_tile_pixels(img, tx, ty):
    pxs = []
    for yy in range(TILE_SIZE):
        for xx in range(TILE_SIZE):
            px = img.getpixel((tx * TILE_SIZE + xx, ty * TILE_SIZE + yy))
            if isinstance(px, tuple):
                r, g, b = px[0], px[1], px[2]
                idx = int((r + g + b) / 3) >> 4
            else:
                idx = int(px) & 0x0F
            pxs.append(idx & 0x0F)
    return pxs

def tile_to_4bpp_bytes(tile_pixels):
    out = bytearray()
    for i in range(0, 64, 2):
        out.append(((tile_pixels[i] & 0x0F) << 4) | (tile_pixels[i + 1] & 0x0F))
    return bytes(out)

def save_palette_file(img, pal_path):
    if img.mode != "P":
        img_p = img.convert("P", palette=Image.ADAPTIVE, colors=16)
    else:
        img_p = img
    palette = img_p.getpalette()
    if not palette:
        raise RuntimeError("No available palette on current image. Cannot convert.")
    palette_rgb = []
    for i in range(0, min(len(palette), 48), 3):
        palette_rgb.append((palette[i], palette[i + 1], palette[i + 2]))
    while len(palette_rgb) < 16:
        palette_rgb.append((0, 0, 0))
    with open(pal_path, "wb") as f:
        for rgb in palette_rgb[:16]:
            val = rgb888_to_bgr555(rgb)
            f.write(struct.pack("<H", val))

def process_entry(entry):
    path = entry["path"]
    width_tiles = int(entry["width"])
    height_tiles = int(entry["height"])
    coords = {(int(t["x"]), int(t["y"])) for t in entry.get("priority_tiles", [])}

    if not os.path.exists(path):
        print(f"[SKIP] '{path}' does not exist")
        return

    print(f"[+] Processing: {path} ({width_tiles} x {height_tiles} tiles)")

    img = Image.open(path)
    w_px, h_px = img.size
    expected_w = width_tiles * TILE_SIZE
    expected_h = height_tiles * TILE_SIZE
    if w_px != expected_w or h_px != expected_h:
        raise ValueError(f"Wrong pixel dimensions on {path}: "
                         f"waiting for {expected_w}x{expected_h}, found: {w_px}x{h_px}")

    # Guardar paleta .pal
    base, _ = os.path.splitext(path)
    pal_path = f"{base}.pal"
    save_palette_file(img, pal_path)
    print(f"    Paleta -> {pal_path}")

    img_p = img.convert("P", palette=Image.ADAPTIVE, colors=16)
    tiles_bin = bytearray()
    map_values = []

    tile_index = 1
    for ty in range(height_tiles):
        for tx in range(width_tiles):
            pixels = get_tile_pixels(img_p, tx, ty)
            tiles_bin += tile_to_4bpp_bytes(pixels)
            val = tile_index & 0x7FFF
            if (tx, ty) in coords:
                val |= PRIORITY_MASK
            map_values.append(val)
            tile_index += 1
            
    # LEGACY - DID NOT WORK AS EXPECTED... GIVING UP - JUST HERE TO REMEMBER WHAT NOT TO DO 
    #tiles_path = f"{base}_tiles.bin"
    #with open(tiles_path, "wb") as f:
    #    f.write(tiles_bin)
    #print(f"    Tileset -> {tiles_path}  (tiles: {tile_index - 1})")

    #map_path = f"{base}_map.bin"
    #with open(map_path, "wb") as f:
    #    for v in map_values:
    #        f.write(struct.pack("<H", v))
    #print(f"    Tilemap -> {map_path}")

    # layer 1 "main" y layer 2 "high_prio" (bin mask)
    tmx_path = f"{base}_map.tmx"
    map_attrib = {
        "version": "1.9",
        "tiledversion": "1.9.2",
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "width": str(width_tiles),
        "height": str(height_tiles),
        "tilewidth": str(TILE_SIZE),
        "tileheight": str(TILE_SIZE),
        "infinite": "0"
    }
    root = ET.Element("map", map_attrib)

    tileset = ET.SubElement(root, "tileset", {
        "firstgid": "1",
        "name": os.path.basename(base) + "_tiles",
        "tilewidth": str(TILE_SIZE),
        "tileheight": str(TILE_SIZE),
        "tilecount": str(width_tiles * height_tiles),
        "columns": str(width_tiles)
    })
    image_source = os.path.basename(path)
    ET.SubElement(tileset, "image", {"source": image_source, "width": str(w_px), "height": str(h_px)})

    # layer 1: main (full tilemap) 
    rows_main = []
    for y in range(height_tiles):
        row = []
        for x in range(width_tiles):
            gid = y * width_tiles + x + 1
            row.append(str(gid))
        rows_main.append(",".join(row))

    # layer 2: high_prio (bin mask: 1 = high priority, 0 = low) 
    rows_high_prio = []
    for y in range(height_tiles):
        row = []
        for x in range(width_tiles):
            idx = y * width_tiles + x
            val = map_values[idx]
            if val & PRIORITY_MASK:
                row.append("1")
            else:
                row.append("0")
        rows_high_prio.append(",".join(row))

    layer_main = ET.SubElement(root, "layer", {"id": "1", "name": "main", "width": str(width_tiles), "height": str(height_tiles)})
    data_main = ET.SubElement(layer_main, "data", {"encoding": "csv"})
    data_main.text = "\n" + ",\n".join(rows_main) + "\n"

    layer_high_prio = ET.SubElement(root, "layer", {"id": "2", "name": "high_prio", "width": str(width_tiles), "height": str(height_tiles)})
    data_high_prio = ET.SubElement(layer_high_prio, "data", {"encoding": "csv"})
    data_high_prio.text = "\n" + ",\n".join(rows_high_prio) + "\n"

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(tmx_path, encoding="utf-8", xml_declaration=True)
    print(f"    TMX -> {tmx_path}")

def main():
    jpath = "tile_priorities.json"
    if not os.path.exists(jpath):
        raise FileNotFoundError("tile_priorities.json not in path.")
    with open(jpath, "r", encoding="utf-8") as f:
        entries = json.load(f)
    for e in entries:
        process_entry(e)
    print("\nDone")

if __name__ == "__main__":
    main()
