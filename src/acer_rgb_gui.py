import json
import os
import subprocess

from nicegui import app, run, ui

try:
    import webview  # noqa: F401  (only used to detect native-mode availability)
    NATIVE_AVAILABLE = True
except ImportError:
    NATIVE_AVAILABLE = False

CONFIG_DIR = os.path.expanduser("~/.config/argb")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
PROFILES_FILE = os.path.join(CONFIG_DIR, "profiles.json")
APPLY_HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apply_rgb.py")

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

# Which controls apply to each mode, per facer_rgb.py --help.
MODE_CONTROLS = {
    0: {"zones": True, "color": False, "speed": False, "direction": False},   # Static
    1: {"zones": False, "color": True, "speed": True, "direction": False},    # Breath
    2: {"zones": False, "color": False, "speed": True, "direction": False},   # Neon
    3: {"zones": False, "color": False, "speed": True, "direction": True},    # Wave
    4: {"zones": False, "color": True, "speed": True, "direction": False},    # Shifting
    5: {"zones": False, "color": True, "speed": True, "direction": False},    # Zoom
}

DEFAULT_ZONE_COLOR = "#de9aed"
ACCENT = "#bacdf7"
BG = "#131318"
PANEL = "#1c1c24"
SIDEBAR = "#17171d"
SIDEBAR_ACTIVE = "rgba(186, 205, 247, 0.15)"

ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "icon", "pogos.png")

TABS = ["RGB Editor", "Info"]


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
    for candidate in AUTO_DETECT_CANDIDATES:
        path = os.path.expanduser(candidate)
        if os.path.exists(os.path.join(path, "facer_rgb.py")):
            return path
    return None


def hex_to_rgb(hexval):
    h = hexval.lstrip("#")
    return {"r": int(h[0:2], 16), "g": int(h[2:4], 16), "b": int(h[4:6], 16)}


class ArgbApp:
    def __init__(self):
        self.config_data = load_json(CONFIG_FILE, {"module_path": ""})
        self.profiles = load_json(PROFILES_FILE, {})

        if not self.config_data.get("module_path"):
            detected = find_module_path()
            if detected:
                self.config_data["module_path"] = detected
                save_json(CONFIG_FILE, self.config_data)

        self.mode = "Static Color"
        self.brightness = 100
        self.speed = 4
        self.direction = 1
        self.same_color = True
        self.zone_colors = [DEFAULT_ZONE_COLOR] * 4
        self.global_color = DEFAULT_ZONE_COLOR

        self.path_label = None
        self.profile_select = None
        self.mode_select = None
        self.brightness_slider = None
        self._loading_profile = False
        self.same_circle = None
        self.zone_circles = []
        self.global_circle = None

        # Tracks which saved profile the current field text originated from,
        # so that editing the name in place and clicking Save renames it
        # (removes the old key) instead of creating a duplicate entry.
        self.loaded_profile_name = None

        self.active_tab = "RGB Editor"
        self.sidebar_buttons = {}

    # ---- derived state ----

    def controls(self):
        return MODE_CONTROLS[MODES[self.mode]]

    def facer_script_path(self):
        return os.path.join(self.config_data.get("module_path", ""), "facer_rgb.py")

    # ---- ui ----

    def build(self):
        ui.colors(primary=ACCENT, dark=BG, dark_page=BG)
        ui.dark_mode().enable()
        ui.query("body").style(f"background-color: {BG}")

        self._build_header()
        self._build_profile_bar()

        with ui.row().classes("w-full gap-0 items-stretch").style("min-height: calc(100vh - 112px)"):
            self._build_sidebar()
            with ui.column().classes("flex-1 p-6 gap-4 max-w-2xl"):
                self.main_panel()

    def _build_header(self):
        with ui.header().classes(
            "items-center justify-between px-6 py-3 border-b border-white/10 shadow-lg"
        ).style(f"background-color: {PANEL}"):
            with ui.row().classes("items-center gap-3"):
                ui.image(ICON_PATH).classes("w-8 h-8 rounded")
                ui.label("ARGB").classes("text-2xl font-bold tracking-wide")
            with ui.row().classes("items-center gap-3"):
                self.path_label = ui.label(self._module_path_display()).classes(
                    "text-xs opacity-60 max-w-xs truncate"
                )
                ui.button("Change folder", on_click=self.browse_module_path).props(
                    "flat dense color=white"
                )

    def _module_path_display(self):
        path = self.config_data.get("module_path", "")
        return path if path else "Module folder not set"

    def _build_profile_bar(self):
        with ui.row().classes(
            "w-full items-center gap-3 px-6 py-2 border-b border-white/10"
        ).style(f"background-color: {PANEL}"):
            ui.label("Profile:").classes("text-sm opacity-70")
            self.profile_select = ui.select(
                options=list(self.profiles.keys()), with_input=True, on_change=self._on_profile_change
            ).classes("w-56").props(
                "outlined dense use-input fill-input hide-selected input-debounce=0 "
                'new-value-mode="add-unique"'
            )
            ui.button("Apply", on_click=self.apply).props("unelevated color=primary dense")
            ui.button("Save", on_click=self.save_profile).props("flat dense")
            ui.button("Delete", on_click=self.delete_profile).props("flat dense color=negative")

    def _build_sidebar(self):
        with ui.column().classes("gap-1 p-3 w-48 border-r border-white/10").style(
            f"background-color: {SIDEBAR}"
        ):
            for tab in TABS:
                btn = ui.button(tab, on_click=lambda t=tab: self._select_tab(t)).props(
                    "flat align=left no-caps"
                ).classes("w-full justify-start")
                self.sidebar_buttons[tab] = btn
            self._refresh_sidebar_styles()

    def _refresh_sidebar_styles(self):
        for tab, btn in self.sidebar_buttons.items():
            if tab == self.active_tab:
                btn.style(f"background-color: {SIDEBAR_ACTIVE}; color: {ACCENT}; border-radius: 8px;")
            else:
                btn.style("background-color: transparent; color: inherit; border-radius: 8px;")

    def _select_tab(self, tab):
        self.active_tab = tab
        self._refresh_sidebar_styles()
        self.main_panel.refresh()

    @ui.refreshable
    def main_panel(self):
        if self.active_tab == "RGB Editor":
            self._build_mode_card()
            self.zones_section()
            self.anim_section()
        else:
            self._build_info_panel()

    def _build_info_panel(self):
        with ui.card().classes("w-full").style(f"background-color: {PANEL}"):
            ui.label("Info").classes("text-sm font-semibold opacity-70")
            ui.label(
                "Add usage notes, troubleshooting tips, or anything else here."
            ).classes("text-sm opacity-50 mt-2")

    def _build_mode_card(self):
        with ui.card().classes("w-full").style(f"background-color: {PANEL}"):
            ui.label("Mode & Brightness").classes("text-sm font-semibold opacity-70")
            self.mode_select = ui.select(
                options=list(MODES.keys()), value=self.mode, on_change=self._on_mode_change
            ).classes("w-full").props("outlined dense")
            ui.label("Brightness").classes("text-xs opacity-60 mt-2")
            self.brightness_slider = ui.slider(
                min=0, max=100, value=self.brightness, on_change=self._on_brightness_change
            ).props("label-always")

    def _on_mode_change(self, e):
        self.mode = e.value
        self.zones_section.refresh()
        self.anim_section.refresh()

    def _on_brightness_change(self, e):
        self.brightness = int(e.value)

    @ui.refreshable
    def zones_section(self):
        if not self.controls()["zones"]:
            return
        with ui.card().classes("w-full").style(f"background-color: {PANEL}"):
            with ui.row().classes("items-center justify-between w-full"):
                ui.label("Zone Colors").classes("text-sm font-semibold opacity-70")
                ui.switch(
                    "Same color for all zones",
                    value=self.same_color,
                    on_change=self._on_same_color_toggle,
                )
            if self.same_color:
                with ui.row().classes("items-center gap-2 w-full"):
                    self.same_circle = self._zone_circle(self.zone_colors[0])
                    ui.color_input(
                        "All zones", value=self.zone_colors[0], on_change=self._set_all_zone_colors
                    ).classes("flex-1")
            else:
                self.zone_circles = []
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    for i in range(4):
                        with ui.row().classes("items-center gap-2 flex-1 min-w-[120px]"):
                            circle = self._zone_circle(self.zone_colors[i])
                            self.zone_circles.append(circle)
                            ui.color_input(
                                f"Zone {i + 1}",
                                value=self.zone_colors[i],
                                on_change=lambda e, i=i: self._set_zone_color(i, e.value),
                            ).classes("flex-1")

    def _on_same_color_toggle(self, e):
        self.same_color = e.value
        if self.same_color:
            self.zone_colors = [self.zone_colors[0]] * 4
        self.zones_section.refresh()

    def _set_all_zone_colors(self, e):
        self.zone_colors = [e.value] * 4
        if self.same_circle is not None:
            self.same_circle.style(f"background-color: {e.value}")

    def _set_zone_color(self, i, value):
        self.zone_colors[i] = value
        if i < len(self.zone_circles):
            self.zone_circles[i].style(f"background-color: {value}")

    @ui.refreshable
    def anim_section(self):
        controls = self.controls()
        if not (controls["color"] or controls["speed"] or controls["direction"]):
            return
        with ui.card().classes("w-full gap-3").style(f"background-color: {PANEL}"):
            ui.label("Color & Animation").classes("text-sm font-semibold opacity-70")
            if controls["color"]:
                with ui.row().classes("items-center gap-2 w-full"):
                    self.global_circle = self._zone_circle(self.global_color)
                    ui.color_input(
                        "Color", value=self.global_color, on_change=self._set_global_color
                    ).classes("flex-1")
            if controls["speed"]:
                ui.label("Speed").classes("text-xs opacity-60")
                ui.slider(min=0, max=9, value=self.speed, on_change=self._on_speed_change).props(
                    "label-always"
                )
            if controls["direction"]:
                ui.label("Direction").classes("text-xs opacity-60")
                ui.toggle(
                    {1: "Right \u2192 Left", 2: "Left \u2192 Right"},
                    value=self.direction,
                    on_change=self._on_direction_change,
                )

    def _set_global_color(self, e):
        self.global_color = e.value
        if self.global_circle is not None:
            self.global_circle.style(f"background-color: {e.value}")

    def _on_speed_change(self, e):
        self.speed = int(e.value)

    def _on_direction_change(self, e):
        self.direction = e.value

    # ---- profiles ----

    def _current_settings(self):
        return {
            "zone_colors": list(self.zone_colors),
            "global_color": self.global_color,
            "same_color": self.same_color,
            "mode": self.mode,
            "brightness": self.brightness,
            "speed": self.speed,
            "direction": self.direction,
        }

    def _zone_circle(self, color):
        return ui.element("div").style(
            f"width: 20px; height: 20px; border-radius: 50%; background-color: {color}; "
            "border: 1px solid rgba(255,255,255,0.3); flex-shrink: 0;"
        )

    def _on_profile_change(self, e):
        name = e.value
        # Only treat this as "loading a profile" if it's an existing, DIFFERENT
        # saved name. Free typing (renaming in place) shouldn't reload settings
        # or lose track of which profile we started editing from.
        if name and name in self.profiles and name != self.loaded_profile_name:
            settings = self.profiles[name]
            self._loading_profile = True
            try:
                self.zone_colors = settings.get("zone_colors", [DEFAULT_ZONE_COLOR] * 4)
                self.global_color = settings.get("global_color", DEFAULT_ZONE_COLOR)
                self.same_color = settings.get("same_color", True)
                self.mode = settings.get("mode", "Static Color")
                self.brightness = settings.get("brightness", 100)
                self.speed = settings.get("speed", 4)
                self.direction = settings.get("direction", 1)
                self.mode_select.value = self.mode
                self.brightness_slider.value = self.brightness
                self.zones_section.refresh()
                self.anim_section.refresh()
            finally:
                self._loading_profile = False
            self.loaded_profile_name = name
            ui.notify(f"Loaded profile '{name}'.")

    def save_profile(self):
        name = (self.profile_select.value or "").strip()
        if not name:
            ui.notify("Type a profile name first.", type="negative")
            return
        # Renaming: if the field started from a different existing profile,
        # remove the old entry so we don't leave a duplicate behind.
        if self.loaded_profile_name and self.loaded_profile_name != name and self.loaded_profile_name in self.profiles:
            del self.profiles[self.loaded_profile_name]
        self.profiles[name] = self._current_settings()
        save_json(PROFILES_FILE, self.profiles)
        self.loaded_profile_name = name
        self.profile_select.options = list(self.profiles.keys())
        self.profile_select.value = name
        self.profile_select.update()
        ui.notify(f"Saved profile '{name}'.", type="positive")

    def delete_profile(self):
        name = (self.profile_select.value or "").strip()
        if name not in self.profiles and self.loaded_profile_name in self.profiles:
            name = self.loaded_profile_name
        if name in self.profiles:
            del self.profiles[name]
            save_json(PROFILES_FILE, self.profiles)
            self.profile_select.options = list(self.profiles.keys())
            self.profile_select.value = None
            self.profile_select.update()
            self.loaded_profile_name = None
            ui.notify(f"Deleted profile '{name}'.")
        else:
            ui.notify("No matching profile to delete.", type="negative")

    async def apply(self):
        script = self.facer_script_path()
        if not self.config_data.get("module_path") or not os.path.exists(script):
            ui.notify(
                "Select the acer-predator-turbo-and-rgb-keyboard-linux-module folder first.",
                type="negative",
            )
            return

        mode_idx = MODES[self.mode]
        controls = self.controls()

        cfg = {
            "facer_script": script,
            "mode": mode_idx,
            "brightness": self.brightness,
            "speed": self.speed,
            "direction": self.direction,
        }
        if controls["zones"]:
            cfg["zones"] = [
                {"zone": i + 1, **hex_to_rgb(color)} for i, color in enumerate(self.zone_colors)
            ]
        if controls["color"]:
            cfg["color"] = hex_to_rgb(self.global_color)

        payload = json.dumps(cfg)
        waiting = ui.notification(
            "Waiting for authentication...", type="ongoing", spinner=True, timeout=None
        )

        try:
            result = await run.io_bound(
                subprocess.run,
                ["pkexec", "python3", APPLY_HELPER, payload],
                capture_output=True,
                text=True,
            )
            waiting.dismiss()
            if result.returncode == 0:
                ui.notify("Applied successfully.", type="positive")
            else:
                ui.notify(f"Failed: {result.stderr.strip()[:300]}", type="negative")
        except FileNotFoundError:
            waiting.dismiss()
            ui.notify("pkexec not found. Install polkit to use Apply.", type="negative")

    # ---- module path ----

    async def browse_module_path(self):
        if NATIVE_AVAILABLE and app.native.main_window:
            folder_type = webview.FileDialog.FOLDER if hasattr(webview, "FileDialog") else webview.FOLDER_DIALOG
            result = await app.native.main_window.create_file_dialog(dialog_type=folder_type)
            if result:
                self._set_module_path(result[0])
            return

        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Module folder path")
            path_input = ui.input(value=self.config_data.get("module_path", "")).classes("w-full")
            with ui.row().classes("justify-between w-full"):
                ui.button(
                    "Auto-detect", on_click=lambda: path_input.set_value(find_module_path() or "")
                ).props("flat")
                with ui.row().classes("gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Save", on_click=lambda: dialog.submit(path_input.value))
        path = await dialog
        if path:
            self._set_module_path(path)

    def _set_module_path(self, path):
        self.config_data["module_path"] = path
        save_json(CONFIG_FILE, self.config_data)
        self.path_label.set_text(self._module_path_display())


argb = ArgbApp()
argb.build()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="ARGB",
        native=NATIVE_AVAILABLE,
        window_size=(900, 720) if NATIVE_AVAILABLE else None,
        reload=False,
        show=True,
        dark=True,
        favicon=ICON_PATH,
    )