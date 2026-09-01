import json
import os
import subprocess
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

CONFIG_DIR = os.path.expanduser("~/.config/acer-rgb-gui")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
PROFILES_FILE = os.path.join(CONFIG_DIR, "profiles.json")
APPLY_HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apply_rgb.py")

MODES = {
    "Solid Color": 0,
    "Breath": 1,
    "Neon": 2,
    "Wave": 3,
    "Shifting": 4,
    "Zoom": 5,
}

BG = "#1e1e2e"
FG = "#cdd6f4"
ACCENT = "#de9aed"
PANEL = "#282838"


# ---- persistence helpers ---------------------------------------------------

def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ---- main app ---------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Acer RGB Control")
        self.configure(bg=BG)
        self.resizable(False, False)

        self.config_data = load_json(CONFIG_FILE, {"module_path": ""})
        self.profiles = load_json(PROFILES_FILE, {})

        self.color = "#de9aed"

        self._build_style()
        self._build_ui()

    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG, font=("Sans", 10))
        style.configure("Header.TLabel", font=("Sans", 13, "bold"))
        style.configure("TButton", background=PANEL, foreground=FG, padding=6)
        style.map("TButton", background=[("active", ACCENT)])
        style.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=FG)

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        ttk.Label(self, text="Acer Keyboard RGB", style="Header.TLabel").grid(
            row=0, column=0, columnspan=3, **pad
        )

        # Module path row
        ttk.Label(self, text="Module folder").grid(row=1, column=0, sticky="w", **pad)
        self.path_var = tk.StringVar(value=self.config_data.get("module_path", "") or "(not set)")
        ttk.Label(self, textvariable=self.path_var, wraplength=260).grid(
            row=1, column=1, sticky="w", **pad
        )
        ttk.Button(self, text="Browse...", command=self.browse_module_path).grid(
            row=1, column=2, **pad
        )

        # Color swatch
        ttk.Label(self, text="Color").grid(row=2, column=0, sticky="w", **pad)
        self.swatch = tk.Button(
            self, width=10, height=2, bg=self.color, relief=tk.FLAT,
            cursor="hand2", command=self.pick_color,
        )
        self.swatch.grid(row=2, column=1, sticky="w", **pad)

        # Mode dropdown
        ttk.Label(self, text="Mode").grid(row=3, column=0, sticky="w", **pad)
        self.mode_var = tk.StringVar(value="Solid Color")
        ttk.Combobox(
            self, textvariable=self.mode_var, values=list(MODES.keys()),
            state="readonly", width=18,
        ).grid(row=3, column=1, sticky="w", **pad)

        # Brightness
        ttk.Label(self, text="Brightness").grid(row=4, column=0, sticky="w", **pad)
        self.brightness = tk.IntVar(value=100)
        ttk.Scale(self, from_=0, to=100, variable=self.brightness, orient=tk.HORIZONTAL, length=180).grid(
            row=4, column=1, columnspan=2, sticky="w", **pad
        )

        # Speed (animated modes)
        ttk.Label(self, text="Speed (effects)").grid(row=5, column=0, sticky="w", **pad)
        self.speed = tk.IntVar(value=4)
        ttk.Scale(self, from_=0, to=9, variable=self.speed, orient=tk.HORIZONTAL, length=180).grid(
            row=5, column=1, columnspan=2, sticky="w", **pad
        )

        # Direction (wave only)
        ttk.Label(self, text="Direction (wave)").grid(row=6, column=0, sticky="w", **pad)
        self.direction = tk.IntVar(value=1)
        dir_frame = ttk.Frame(self)
        dir_frame.grid(row=6, column=1, columnspan=2, sticky="w", **pad)
        ttk.Radiobutton(dir_frame, text="R→L", variable=self.direction, value=1).pack(side=tk.LEFT)
        ttk.Radiobutton(dir_frame, text="L→R", variable=self.direction, value=2).pack(side=tk.LEFT)

        # Profiles row
        ttk.Label(self, text="Profile").grid(row=7, column=0, sticky="w", **pad)
        self.profile_var = tk.StringVar()
        self.profile_box = ttk.Combobox(
            self, textvariable=self.profile_var, values=list(self.profiles.keys()),
            state="readonly", width=18,
        )
        self.profile_box.grid(row=7, column=1, sticky="w", **pad)
        self.profile_box.bind("<<ComboboxSelected>>", lambda e: self.load_profile())

        profile_btns = ttk.Frame(self)
        profile_btns.grid(row=8, column=0, columnspan=3, **pad)
        ttk.Button(profile_btns, text="Save As...", command=self.save_profile).pack(side=tk.LEFT, padx=4)
        ttk.Button(profile_btns, text="Delete", command=self.delete_profile).pack(side=tk.LEFT, padx=4)

        # Apply
        ttk.Button(self, text="Apply", command=self.apply).grid(row=9, column=0, columnspan=3, pady=14)
        self.status = ttk.Label(self, text="", wraplength=360)
        self.status.grid(row=10, column=0, columnspan=3, **pad)

    # ---- module path ----

    def browse_module_path(self):
        chosen = filedialog.askdirectory(title="Select acer-predator-turbo-and-rgb-keyboard-linux-module folder")
        if chosen:
            self.config_data["module_path"] = chosen
            save_json(CONFIG_FILE, self.config_data)
            self.path_var.set(chosen)

    def facer_script_path(self):
        path = self.config_data.get("module_path", "")
        return os.path.join(path, "facer_rgb.py")

    # ---- color ----

    def pick_color(self):
        rgb, hexval = colorchooser.askcolor(color=self.color, title="Pick color")
        if hexval:
            self.color = hexval
            self.swatch.configure(bg=hexval)

    def color_rgb(self):
        h = self.color.lstrip("#")
        return {"r": int(h[0:2], 16), "g": int(h[2:4], 16), "b": int(h[4:6], 16)}

    # ---- profiles ----

    def current_settings(self):
        return {
            "color": self.color,
            "mode": self.mode_var.get(),
            "brightness": self.brightness.get(),
            "speed": self.speed.get(),
            "direction": self.direction.get(),
        }

    def save_profile(self):
        name = simpledialog.askstring("Save Profile", "Profile name:")
        if not name:
            return
        self.profiles[name] = self.current_settings()
        save_json(PROFILES_FILE, self.profiles)
        self.profile_box.configure(values=list(self.profiles.keys()))
        self.profile_var.set(name)
        self.status.configure(text=f"Saved profile '{name}'.")

    def load_profile(self):
        name = self.profile_var.get()
        settings = self.profiles.get(name)
        if not settings:
            return
        self.color = settings["color"]
        self.swatch.configure(bg=self.color)
        self.mode_var.set(settings["mode"])
        self.brightness.set(settings["brightness"])
        self.speed.set(settings["speed"])
        self.direction.set(settings["direction"])
        self.status.configure(text=f"Loaded profile '{name}'.")

    def delete_profile(self):
        name = self.profile_var.get()
        if name in self.profiles:
            del self.profiles[name]
            save_json(PROFILES_FILE, self.profiles)
            self.profile_box.configure(values=list(self.profiles.keys()))
            self.profile_var.set("")
            self.status.configure(text=f"Deleted profile '{name}'.")

    # ---- apply ----

    def apply(self):
        script = self.facer_script_path()
        if not self.config_data.get("module_path") or not os.path.exists(script):
            messagebox.showerror(
                "Module folder not set",
                "Please click 'Browse...' and select the acer-predator-turbo-and-rgb-keyboard-linux-module folder first.",
            )
            return

        mode_name = self.mode_var.get()
        mode_idx = MODES[mode_name]

        cfg = {
            "facer_script": script,
            "mode": mode_idx,
            "brightness": self.brightness.get(),
            "speed": self.speed.get(),
            "direction": self.direction.get(),
        }

        if mode_idx == 0:
            rgb = self.color_rgb()
            cfg["zones"] = [{"zone": z, **rgb} for z in (1, 2, 3, 4)]
        else:
            cfg["color"] = self.color_rgb()

        payload = json.dumps(cfg)
        self.status.configure(text="Waiting for password...")
        self.update_idletasks()

        try:
            result = subprocess.run(
                ["pkexec", "python3", APPLY_HELPER, payload],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                self.status.configure(text="Applied successfully.")
            else:
                self.status.configure(text=f"Failed: {result.stderr.strip()[:300]}")
        except FileNotFoundError:
            messagebox.showerror("Error", "pkexec not found. Install polkit to use the Apply button.")


if __name__ == "__main__":
    App().mainloop()
