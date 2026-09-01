import json
import os
import subprocess
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

try:
    import sv_ttk
    HAVE_SV_TTK = True
except ImportError:
    HAVE_SV_TTK = False

CONFIG_DIR = os.path.expanduser("~/.config/acer-rgb-gui")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
PROFILES_FILE = os.path.join(CONFIG_DIR, "profiles.json")
APPLY_HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apply_rgb.py")

# Candidate locations to auto-detect the module folder before falling back
# to a manual "Browse..." prompt.
AUTO_DETECT_CANDIDATES = [
    "~/acer-predator-turbo-and-rgb-keyboard-linux-module",
    "~/.local/share/acer-predator-turbo-and-rgb-keyboard-linux-module",
    "~/Downloads/acer-predator-turbo-and-rgb-keyboard-linux-module",
    "~/src/acer-predator-turbo-and-rgb-keyboard-linux-module",
]

MODES = {
    "Static Color": 0,
    "Breath": 1,
    "Neon": 2,
    "Wave": 3,
    "Shifting": 4,
    "Zoom": 5,
}

# Which controls are meaningful for each mode index (per facer_rgb.py --help).
MODE_CONTROLS = {
    0: {"zones": True, "color": False, "speed": False, "direction": False},   # Static
    1: {"zones": False, "color": True, "speed": True, "direction": False},    # Breath
    2: {"zones": False, "color": False, "speed": True, "direction": False},   # Neon
    3: {"zones": False, "color": False, "speed": True, "direction": True},    # Wave
    4: {"zones": False, "color": True, "speed": True, "direction": False},    # Shifting
    5: {"zones": False, "color": True, "speed": True, "direction": False},    # Zoom
}

DEFAULT_ZONE_COLORS = ["#de9aed", "#de9aed", "#de9aed", "#de9aed"]
DEFAULT_GLOBAL_COLOR = "#de9aed"

# Fallback palette, only used when sv_ttk isn't installed.
FALLBACK_BG = "#1e1e2e"
FALLBACK_FG = "#cdd6f4"
FALLBACK_ACCENT = "#de9aed"
FALLBACK_PANEL = "#282838"


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


def find_module_path():
    """Look in a few common spots for facer_rgb.py before asking the user."""
    for candidate in AUTO_DETECT_CANDIDATES:
        path = os.path.expanduser(candidate)
        if os.path.exists(os.path.join(path, "facer_rgb.py")):
            return path
    return None


def hex_to_rgb(hexval):
    h = hexval.lstrip("#")
    return {"r": int(h[0:2], 16), "g": int(h[2:4], 16), "b": int(h[4:6], 16)}


# ---- main app ---------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Acer RGB Control")
        self.minsize(460, 420)
        self.resizable(True, True)

        self.config_data = load_json(CONFIG_FILE, {"module_path": ""})
        self.profiles = load_json(PROFILES_FILE, {})

        if not self.config_data.get("module_path"):
            detected = find_module_path()
            if detected:
                self.config_data["module_path"] = detected
                save_json(CONFIG_FILE, self.config_data)

        self.zone_colors = list(DEFAULT_ZONE_COLORS)
        self.global_color = DEFAULT_GLOBAL_COLOR
        self._toast_job = None

        self._apply_theme()
        self._build_ui()
        self._on_mode_change()
        self._center_on_screen()

    # ---- theming ----

    def _apply_theme(self):
        if HAVE_SV_TTK:
            sv_ttk.set_theme("dark")
            style = ttk.Style(self)
            self.bg = style.lookup("TFrame", "background") or "#1c1c1c"
            self.configure(bg=self.bg)
        else:
            style = ttk.Style(self)
            style.theme_use("clam")
            style.configure("TFrame", background=FALLBACK_BG)
            style.configure("TLabel", background=FALLBACK_BG, foreground=FALLBACK_FG)
            style.configure("TButton", background=FALLBACK_PANEL, foreground=FALLBACK_FG, padding=6)
            style.map("TButton", background=[("active", FALLBACK_ACCENT)])
            style.configure("TCombobox", fieldbackground=FALLBACK_PANEL, background=FALLBACK_PANEL)
            style.configure("TLabelframe", background=FALLBACK_BG, foreground=FALLBACK_FG)
            style.configure("TLabelframe.Label", background=FALLBACK_BG, foreground=FALLBACK_FG)
            self.bg = FALLBACK_BG
            self.configure(bg=self.bg)

        style = ttk.Style(self)
        style.configure("Header.TLabel", font=("Sans", 14, "bold"))
        style.configure("Sub.TLabel", font=("Sans", 9))

    def _center_on_screen(self):
        self.update_idletasks()
        w = max(self.winfo_width(), 520)
        h = max(self.winfo_height(), 480)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ---- ui construction ----

    def _build_ui(self):
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(header, text="Acer Keyboard RGB", style="Header.TLabel").pack(anchor="w")
        self.path_var = tk.StringVar(value=self._module_path_display())
        path_row = ttk.Frame(header)
        path_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(path_row, textvariable=self.path_var, style="Sub.TLabel").pack(side=tk.LEFT)
        ttk.Button(path_row, text="Change folder...", command=self.browse_module_path).pack(side=tk.RIGHT)

        # Mode + brightness (always visible)
        general = ttk.LabelFrame(outer, text="Mode & Brightness", padding=12)
        general.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        general.columnconfigure(1, weight=1)

        ttk.Label(general, text="Mode").grid(row=0, column=0, sticky="w", pady=4)
        self.mode_var = tk.StringVar(value="Static Color")
        mode_box = ttk.Combobox(
            general, textvariable=self.mode_var, values=list(MODES.keys()),
            state="readonly",
        )
        mode_box.grid(row=0, column=1, columnspan=2, sticky="ew", pady=4)
        mode_box.bind("<<ComboboxSelected>>", lambda e: self._on_mode_change())

        ttk.Label(general, text="Brightness").grid(row=1, column=0, sticky="w", pady=4)
        self.brightness = tk.IntVar(value=100)
        ttk.Scale(general, from_=0, to=100, variable=self.brightness, orient=tk.HORIZONTAL).grid(
            row=1, column=1, columnspan=2, sticky="ew", pady=4
        )

        # Static zones section
        self.zones_frame = ttk.LabelFrame(outer, text="Zone Colors (click a segment)", padding=12)
        self.zones_frame.columnconfigure(0, weight=1)
        self.zone_canvas = tk.Canvas(
            self.zones_frame, height=64, highlightthickness=0, bg=self.bg,
        )
        self.zone_canvas.grid(row=0, column=0, sticky="ew")
        self.zone_canvas.bind("<Configure>", lambda e: self._draw_zones())
        self.zone_canvas.bind("<Button-1>", self._on_zone_click)

        # Color + animation section
        self.anim_frame = ttk.LabelFrame(outer, text="Color & Animation", padding=12)
        self.anim_frame.columnconfigure(1, weight=1)

        self.color_row = ttk.Frame(self.anim_frame)
        ttk.Label(self.color_row, text="Color").pack(side=tk.LEFT)
        self.global_swatch = tk.Button(
            self.color_row, width=6, height=1, bg=self.global_color, relief=tk.FLAT,
            cursor="hand2", command=self.pick_global_color,
        )
        self.global_swatch.pack(side=tk.LEFT, padx=(10, 0))

        self.speed_row = ttk.Frame(self.anim_frame)
        ttk.Label(self.speed_row, text="Speed").pack(side=tk.LEFT)
        self.speed = tk.IntVar(value=4)
        ttk.Scale(self.speed_row, from_=0, to=9, variable=self.speed, orient=tk.HORIZONTAL, length=180).pack(
            side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True
        )

        self.direction_row = ttk.Frame(self.anim_frame)
        ttk.Label(self.direction_row, text="Direction").pack(side=tk.LEFT)
        self.direction = tk.IntVar(value=1)
        ttk.Radiobutton(self.direction_row, text="Right \u2192 Left", variable=self.direction, value=1).pack(
            side=tk.LEFT, padx=(10, 0)
        )
        ttk.Radiobutton(self.direction_row, text="Left \u2192 Right", variable=self.direction, value=2).pack(
            side=tk.LEFT, padx=(10, 0)
        )

        self.color_row.grid(row=0, column=0, sticky="w", pady=4)
        self.speed_row.grid(row=1, column=0, sticky="ew", pady=4)
        self.direction_row.grid(row=2, column=0, sticky="w", pady=4)

        # Profiles
        profiles_frame = ttk.LabelFrame(outer, text="Profiles", padding=12)
        profiles_frame.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        profiles_frame.columnconfigure(0, weight=1)

        self.profile_var = tk.StringVar()
        self.profile_box = ttk.Combobox(
            profiles_frame, textvariable=self.profile_var, values=list(self.profiles.keys()),
            state="readonly",
        )
        self.profile_box.grid(row=0, column=0, sticky="ew")
        self.profile_box.bind("<<ComboboxSelected>>", lambda e: self.load_profile())

        btns = ttk.Frame(profiles_frame)
        btns.grid(row=0, column=1, padx=(10, 0))
        ttk.Button(btns, text="Save As...", command=self.save_profile).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Delete", command=self.delete_profile).pack(side=tk.LEFT, padx=2)

        # Apply + status
        bottom = ttk.Frame(outer)
        bottom.grid(row=5, column=0, sticky="ew", pady=(16, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Button(bottom, text="Apply", command=self.apply).grid(row=0, column=0, sticky="ew", ipady=4)

        self.status_var = tk.StringVar(value="")
        self.status = ttk.Label(outer, textvariable=self.status_var, style="Sub.TLabel")
        self.status.grid(row=6, column=0, sticky="w", pady=(8, 0))

        outer.rowconfigure(3, weight=0)

    def _module_path_display(self):
        path = self.config_data.get("module_path", "")
        return path if path else "Module folder not set"

    # ---- mode-driven show/hide ----

    def _on_mode_change(self):
        mode_idx = MODES[self.mode_var.get()]
        controls = MODE_CONTROLS[mode_idx]

        if controls["zones"]:
            self.zones_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
            self.zone_canvas.after(10, self._draw_zones)
        else:
            self.zones_frame.grid_remove()

        show_anim = controls["color"] or controls["speed"] or controls["direction"]
        if show_anim:
            self.anim_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        else:
            self.anim_frame.grid_remove()
            return

        if controls["color"]:
            self.color_row.grid()
        else:
            self.color_row.grid_remove()

        if controls["speed"]:
            self.speed_row.grid()
        else:
            self.speed_row.grid_remove()

        if controls["direction"]:
            self.direction_row.grid()
        else:
            self.direction_row.grid_remove()

    # ---- zone color bar ----

    def _draw_zones(self):
        self.zone_canvas.delete("all")
        width = self.zone_canvas.winfo_width() or 400
        height = self.zone_canvas.winfo_height() or 64
        n = len(self.zone_colors)
        seg_w = width / n
        for i, color in enumerate(self.zone_colors):
            x0 = i * seg_w
            x1 = x0 + seg_w - (4 if i < n - 1 else 0)
            self.zone_canvas.create_rectangle(x0, 0, x1, height, fill=color, outline="")
            self.zone_canvas.create_text(
                (x0 + x1) / 2, height / 2, text=str(i + 1), fill="#000000"
            )

    def _on_zone_click(self, event):
        width = self.zone_canvas.winfo_width() or 400
        n = len(self.zone_colors)
        seg_w = width / n
        idx = min(int(event.x // seg_w), n - 1)
        _, hexval = colorchooser.askcolor(color=self.zone_colors[idx], title=f"Zone {idx + 1} color")
        if hexval:
            self.zone_colors[idx] = hexval
            self._draw_zones()

    # ---- module path ----

    def browse_module_path(self):
        chosen = filedialog.askdirectory(title="Select acer-predator-turbo-and-rgb-keyboard-linux-module folder")
        if chosen:
            self.config_data["module_path"] = chosen
            save_json(CONFIG_FILE, self.config_data)
            self.path_var.set(self._module_path_display())

    def facer_script_path(self):
        path = self.config_data.get("module_path", "")
        return os.path.join(path, "facer_rgb.py")

    # ---- color ----

    def pick_global_color(self):
        _, hexval = colorchooser.askcolor(color=self.global_color, title="Pick color")
        if hexval:
            self.global_color = hexval
            self.global_swatch.configure(bg=hexval)

    # ---- profiles ----

    def current_settings(self):
        return {
            "zone_colors": list(self.zone_colors),
            "global_color": self.global_color,
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
        self._show_status(f"Saved profile '{name}'.")

    def load_profile(self):
        name = self.profile_var.get()
        settings = self.profiles.get(name)
        if not settings:
            return
        self.zone_colors = settings.get("zone_colors", list(DEFAULT_ZONE_COLORS))
        self.global_color = settings.get("global_color", DEFAULT_GLOBAL_COLOR)
        self.global_swatch.configure(bg=self.global_color)
        self.mode_var.set(settings.get("mode", "Static Color"))
        self.brightness.set(settings.get("brightness", 100))
        self.speed.set(settings.get("speed", 4))
        self.direction.set(settings.get("direction", 1))
        self._on_mode_change()
        self._draw_zones()
        self._show_status(f"Loaded profile '{name}'.")

    def delete_profile(self):
        name = self.profile_var.get()
        if name in self.profiles:
            del self.profiles[name]
            save_json(PROFILES_FILE, self.profiles)
            self.profile_box.configure(values=list(self.profiles.keys()))
            self.profile_var.set("")
            self._show_status(f"Deleted profile '{name}'.")

    # ---- status toast ----

    def _show_status(self, text, persist=False):
        self.status_var.set(text)
        if self._toast_job:
            self.after_cancel(self._toast_job)
            self._toast_job = None
        if not persist:
            self._toast_job = self.after(3500, lambda: self.status_var.set(""))

    # ---- apply ----

    def apply(self):
        script = self.facer_script_path()
        if not self.config_data.get("module_path") or not os.path.exists(script):
            messagebox.showerror(
                "Module folder not set",
                "Please select the acer-predator-turbo-and-rgb-keyboard-linux-module folder first.",
            )
            return

        mode_name = self.mode_var.get()
        mode_idx = MODES[mode_name]
        controls = MODE_CONTROLS[mode_idx]

        cfg = {
            "facer_script": script,
            "mode": mode_idx,
            "brightness": self.brightness.get(),
            "speed": self.speed.get(),
            "direction": self.direction.get(),
        }

        if controls["zones"]:
            cfg["zones"] = [
                {"zone": i + 1, **hex_to_rgb(color)} for i, color in enumerate(self.zone_colors)
            ]
        if controls["color"]:
            cfg["color"] = hex_to_rgb(self.global_color)

        payload = json.dumps(cfg)
        self._show_status("Waiting for authentication...", persist=True)
        self.update_idletasks()

        try:
            result = subprocess.run(
                ["pkexec", "python3", APPLY_HELPER, payload],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                self._show_status("Applied successfully.")
            else:
                self._show_status(f"Failed: {result.stderr.strip()[:300]}", persist=True)
        except FileNotFoundError:
            messagebox.showerror("Error", "pkexec not found. Install polkit to use the Apply button.")


if __name__ == "__main__":
    App().mainloop()