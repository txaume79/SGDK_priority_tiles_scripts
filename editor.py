#!/bin/python
# This script opens a gui and batch process png images on a folder to get a tiled tmx file. 
# On the gui you can select any image from the selected folder shown on the left side of the window 
# that will be loaded on the central canvas. Then select one by one tiles (8x8) by clicking on it or just press down the
# left mouse button to select as you run the cursor over them. Can make zoom in and out using
# the wheel. It constantly saves the state on a json so you can get your work where you left it if
# the json is on the same folder. Once that's generated, calls setprioFULLAND01.py that generates
# tmx and pal (pal bin format, barely tested as lately i did not care - legacy code) 

# THE RIGHT FLOW IS:
# $ python editor.py
# $ python prepareprioaseprite palette.pal 
# after that, just take the <original_png_file_name>_map--0.png and use with resources.res and SGDK
# 5 scripts involved and 1 palette needed - just read all the script first lines to get an idea
# editor.py - which should be runned first - it's the GUI
# setprioFULLAND01.py 
# prepareprioaseprite.py
# add_mask_kayer.lua
# prioritypigsy.lua - modified one, not the original
# priority.pal - or named as you wish .pal XD
#
# some day i will make a canonical repo README.md.

import os
import json
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import subprocess
import math

TILE_SIZE = 8
GRID_COLOR = "#00FF00"
SELECT_COLOR = "#8080FF"
STIPPLE_PATTERN = "gray25"
OUTPUT_JSON = "tile_priorities.json"


class TilePriorityEditor:
    def __init__(self, root, image_folder):
        self.root = root
        self.root.title("Tile Priority Editor")

        self.image_folder = image_folder
        self.current_image = None
        self.current_image_name = None
        self.tile_data = []
        self.json_path = os.path.join(image_folder, OUTPUT_JSON)

        self.zoom = 1.0
        self.is_dragging = False
        self.current_action = None  # "add" o "remove"

        self.load_json()
        self.build_ui()
        self.load_thumbnails()

    # make lines thin/thicker on zoom 
    def _line_width(self):
        return max(1, int(round(self.zoom)))

    # mr.Voorhees stuff
    def load_json(self):
        if os.path.exists(self.json_path):
            with open(self.json_path, "r") as f:
                self.tile_data = json.load(f)
        else:
            self.tile_data = []

    def save_json(self):
        with open(self.json_path, "w") as f:
            json.dump(self.tile_data, f, indent=2)
        print(f"[Guardado automático] {self.json_path}")

    def get_entry_for_image(self, name, width, height):
        path_bin = f"{os.path.splitext(name)[0]}.png"
        for entry in self.tile_data:
            if entry["path"] == path_bin:
                return entry
        entry = {
            "path": path_bin,
            "width": width // TILE_SIZE,
            "height": height // TILE_SIZE,
            "priority_tiles": []
        }
        self.tile_data.append(entry)
        return entry

    # winning award user interface
    def build_ui(self):
        self.frame_left = tk.Frame(self.root)
        self.frame_left.pack(side=tk.LEFT, fill=tk.Y)

    
        btn_generate = tk.Button(
            self.frame_left,
            text="Generate",
            bg="#202020",
            fg="white",
            command=self.generate_bin_tmx
        )
        btn_generate.pack(fill=tk.X, padx=5, pady=5)

        self.frame_center = tk.Frame(self.root)
        self.frame_center.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        self.canvas_list = tk.Canvas(self.frame_left, width=150)
        self.scrollbar = tk.Scrollbar(self.frame_left, orient=tk.VERTICAL, command=self.canvas_list.yview)
        self.scrollable_frame = tk.Frame(self.canvas_list)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas_list.configure(scrollregion=self.canvas_list.bbox("all"))
        )
        self.canvas_list.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas_list.configure(yscrollcommand=self.scrollbar.set)
        self.canvas_list.pack(side=tk.LEFT, fill=tk.Y)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # main Canvas
        self.canvas = tk.Canvas(self.frame_center, bg="black")
        self.canvas.pack(expand=True, fill=tk.BOTH)

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<B3-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_release)
        self.canvas.bind("<MouseWheel>", self.on_zoom)  
        self.canvas.bind("<Button-4>", self.on_zoom)  
        self.canvas.bind("<Button-5>", self.on_zoom)  

    def load_thumbnails(self):
        files = [f for f in os.listdir(self.image_folder) if f.lower().endswith(".png")]
        for fname in sorted(files):
            path = os.path.join(self.image_folder, fname)
            img = Image.open(path)
            img.thumbnail((128, 128))
            img_tk = ImageTk.PhotoImage(img)

            btn = tk.Button(
                self.scrollable_frame,
                image=img_tk,
                text=fname,
                compound="top",
                command=lambda n=fname: self.load_image(n)
            )
            btn.image = img_tk
            btn.pack(pady=5)

    def load_image(self, name):
        path = os.path.join(self.image_folder, name)
        self.current_image_name = name
        self.original_image = Image.open(path)
        self.update_zoom_image()
        self.draw_selected_tiles()

    # Zoom stuff
    def on_zoom(self, event):
        if not self.current_image:
            return
        delta = 0
        if hasattr(event, "delta") and event.delta:
            delta = event.delta
        elif event.num == 4:
            delta = 120
        elif event.num == 5:
            delta = -120

        old_zoom = self.zoom
        if delta > 0:
            self.zoom *= 1.1
        elif delta < 0:
            self.zoom /= 1.1
        self.zoom = max(0.5, min(8.0, self.zoom))

        if abs(self.zoom - old_zoom) > 1e-3:
            self.update_zoom_image()
            self.draw_selected_tiles()

    def update_zoom_image(self):
        w, h = self.original_image.size
        zw, zh = int(round(w * self.zoom)), int(round(h * self.zoom))
        self.current_image = self.original_image.resize((zw, zh), Image.NEAREST)
        self.tk_image = ImageTk.PhotoImage(self.current_image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        self.draw_grid(zw, zh)

    # Mouse Tile selection 
    def on_click(self, event):
        self.is_dragging = True
        self.current_action = "add"
        self.toggle_tile(event.x, event.y, add=True)

    def on_right_click(self, event):
        self.is_dragging = True
        self.current_action = "remove"
        self.toggle_tile(event.x, event.y, add=False)

    def on_drag(self, event):
        if not self.is_dragging:
            return
        add = self.current_action == "add"
        self.toggle_tile(event.x, event.y, add)

    def on_release(self, event):
        self.is_dragging = False
        self.current_action = None

    def toggle_tile(self, px, py, add):
        if not self.current_image:
            return

        tx = int(px // (TILE_SIZE * self.zoom))
        ty = int(py // (TILE_SIZE * self.zoom))

        w, h = self.original_image.size
        entry = self.get_entry_for_image(self.current_image_name, w, h)
        existing = next((t for t in entry["priority_tiles"] if t["x"] == tx and t["y"] == ty), None)

        if add and not existing:
            entry["priority_tiles"].append({"x": tx, "y": ty})
        elif not add and existing:
            entry["priority_tiles"].remove(existing)

        self.save_json()
        self.draw_selected_tiles()

    def draw_grid(self, zw=0, zh=0):
        if not self.current_image:
            return
        if zw == 0 or zh == 0:
            zw, zh = self.current_image.size

        # col/row num from original image
        orig_w, orig_h = self.original_image.size
        cols = orig_w // TILE_SIZE
        rows = orig_h // TILE_SIZE

        step = TILE_SIZE * self.zoom
        lw = self._line_width()

        # grid vertical lines
        for i in range(cols + 1):
            x = int(round(i * step))
            self.canvas.create_line(x, 0, x, zh, fill=GRID_COLOR, width=lw, tags="grid")

        # grid horizontal lines
        for j in range(rows + 1):
            y = int(round(j * step))
            self.canvas.create_line(0, y, zw, y, fill=GRID_COLOR, width=lw, tags="grid")

    def draw_selected_tiles(self):
        if not self.current_image_name:
            return
        self.canvas.delete("selection")

        w, h = self.original_image.size
        entry = self.get_entry_for_image(self.current_image_name, w, h)
        step = TILE_SIZE * self.zoom
        lw = self._line_width()

        for t in entry["priority_tiles"]:
            x0, y0 = t["x"] * step, t["y"] * step
            x1, y1 = x0 + step, y0 + step
            self.canvas.create_rectangle(
                x0, y0, x1, y1,
                outline="red",
                width=lw,
                tags="selection",
                fill=SELECT_COLOR,
                stipple=STIPPLE_PATTERN
            )

   
    def generate_bin_tmx(self):
        json_path = os.path.join(self.image_folder, OUTPUT_JSON)
        # call the tmx maker
        script_path = os.path.join(self.image_folder, "setprioFULLAND01.py")

        if not os.path.exists(script_path):
            tk.messagebox.showerror("Error", f"File not found: {script_path}")
            return

        print(f"Running: {script_path}")
        subprocess.run(["python3", script_path, json_path], cwd=self.image_folder)


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1100x700") # whatever

    folder = filedialog.askdirectory(title="Select PNGs folder...")
    if folder:
        app = TilePriorityEditor(root, folder)
        root.mainloop()
