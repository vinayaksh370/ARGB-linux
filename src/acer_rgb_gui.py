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

        # profile editing state — kept fully separate from profile_select's
        # visual value so that editing settings never has to fight with the
        # dropdown's on_change handler.
        self.editing_profile_name = None
        self.profile_dirty = False
        self.update_profile_btn = None

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

        with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-4"):
            self._build_mode_card()
            self.zones_section()
            self.anim_section()
            self._build_profiles_card()
            self._build_apply_row()

    def _build_header(self):
        with ui.header().classes(
            "items-center justify-between px-6 py-3 border-b border-white/10 shadow-lg"
        ).style(f"background-color: {PANEL}"):
            ui.image("assets/icon/pogos.png").classes("w-8 h-8 rounded")
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

    # ---- dirty tracking (replaces the old profile_select-clearing approach) ----

    def _mark_dirty(self):
        if self._loading_profile:
            return
        self.profile_dirty = True
        self._refresh_update_button()

    def _refresh_update_button(self):
        if self.update_profile_btn is None:
            return
        if self.editing_profile_name:
            suffix = " *" if self.profile_dirty else ""
            self.update_profile_btn.text = f"Update{suffix}"
            self.update_profile_btn.set_visibility(True)
        else:
            self.update_profile_btn.set_visibility(False)

    def _on_mode_change(self, e):
        self.mode = e.value
        self._mark_dirty()
        self.zones_section.refresh()
        self.anim_section.refresh()

    def _on_brightness_change(self, e):
        self.brightness = int(e.value)
        self._mark_dirty()

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
        self._mark_dirty()
        self.zones_section.refresh()

    def _set_all_zone_colors(self, e):
        self.zone_colors = [e.value] * 4
        self._mark_dirty()
        if self.same_circle is not None:
            self.same_circle.style(f"background-color: {e.value}")

    def _set_zone_color(self, i, value):
        self.zone_colors[i] = value
        self._mark_dirty()
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
        self._mark_dirty()
        if self.global_circle is not None:
            self.global_circle.style(f"background-color: {e.value}")

    def _on_speed_change(self, e):
        self.speed = int(e.value)
        self._mark_dirty()

    def _on_direction_change(self, e):
        self.direction = e.value
        self._mark_dirty()

    def _build_profiles_card(self):
        with ui.card().classes("w-full").style(f"background-color: {PANEL}"):
            ui.label("Profiles").classes("text-sm font-semibold opacity-70")
            with ui.row().classes("w-full items-center gap-2"):
                self.profile_select = ui.select(
                    options=list(self.profiles.keys()), on_change=self._on_profile_selected
                ).classes("flex-1").props("outlined dense")
                ui.button("Save As...", on_click=self._save_profile_dialog).props("flat")
                self.update_profile_btn = ui.button("Update", on_click=self._update_profile).props("flat")
                self.update_profile_btn.set_visibility(False)
                ui.button("Delete", on_click=self._delete_profile).props("flat color=negative")

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

    async def _save_profile_dialog(self):
        with ui.dialog() as dialog, ui.card():
            ui.label("Profile name")
            name_input = ui.input().classes("w-full")
            with ui.row().classes("justify-end w-full"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Save", on_click=lambda: dialog.submit(name_input.value))
        name = await dialog
        if not name:
            return
        self.profiles[name] = self._current_settings()
        save_json(PROFILES_FILE, self.profiles)
        self.profile_select.options = list(self.profiles.keys())
        self.profile_select.value = name
        self.profile_select.update()
        ui.notify(f"Saved profile '{name}'.", type="positive")

    def _on_profile_selected(self, e):
        name = e.value
        if name is None:
            self.editing_profile_name = None
            self.profile_dirty = False
            self._refresh_update_button()
            return
        settings = self.profiles.get(name)
        if not settings:
            return
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
        self.editing_profile_name = name
        self.profile_dirty = False
        self._refresh_update_button()
        ui.notify(f"Loaded profile '{name}'.")

    def _update_profile(self):
        name = self.editing_profile_name
        if not name or name not in self.profiles:
            return
        self.profiles[name] = self._current_settings()
        save_json(PROFILES_FILE, self.profiles)
        self.profile_dirty = False
        self._refresh_update_button()
        ui.notify(f"Updated profile '{name}'.", type="positive")

    def _delete_profile(self):
        name = self.profile_select.value
        if name in self.profiles:
            del self.profiles[name]
            save_json(PROFILES_FILE, self.profiles)
            self.profile_select.options = list(self.profiles.keys())
            self.profile_select.value = None
            self.profile_select.update()
            ui.notify(f"Deleted profile '{name}'.")

    def _build_apply_row(self):
        ui.button("Apply", on_click=self.apply).classes("w-full").props("color=primary size=lg")

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
        window_size=(620, 780) if NATIVE_AVAILABLE else None,
        reload=False,
        show=True,
        dark=True,
        favicon="assets/icon/pogos.png"
    )