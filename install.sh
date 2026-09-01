set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$APP_DIR/an-kb-color-picker.desktop"

echo "== Acer-KB-Color-Picker-Linux installer =="
echo "Detected install location: $SCRIPT_DIR"

# --- dependency checks -------------------------------------------------
missing=()

command -v python3 >/dev/null 2>&1 || missing+=("python3")
python3 -c "import tkinter" >/dev/null 2>&1 || missing+=("python3-tkinter (tk)")
command -v pkexec >/dev/null 2>&1 || missing+=("pkexec (polkit)")

if [ ${#missing[@]} -ne 0 ]; then
    echo ""
    echo "Missing dependencies:"
    for m in "${missing[@]}"; do echo "  - $m"; done
    echo ""
    echo "On Arch/CachyOS you can install what's needed with:"
    echo "  sudo pacman -S python tk polkit"
    echo ""
    echo "Continuing anyway, but the app may not run until these are installed."
fi

# check for a running polkit auth agent (common gap on bare Hyprland setups)
if ! pgrep -f "polkit.*agent" >/dev/null 2>&1 && ! pgrep -f "polkit-gnome" >/dev/null 2>&1 && ! pgrep -f "polkit-kde" >/dev/null 2>&1; then
    echo ""
    echo "NOTE: No polkit authentication agent appears to be running."
    echo "Without one, the Apply button's password prompt won't show up."
    echo "On Hyprland, add something like this to your config:"
    echo "  exec-once = /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1"
    echo "(or polkit-kde-agent, depending on what you have installed)"
fi

# --- permissions ---------------------------------------------------------
chmod +x "$SCRIPT_DIR/acer_rgb_gui.py"
chmod +x "$SCRIPT_DIR/apply_rgb.py"

# --- desktop entry ---------------------------------------------------------
mkdir -p "$APP_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=AN KB Color Picker
Comment=Control 4-zone RGB keyboard lighting on Acer Nitro/Predator laptops
Exec=python3 "$SCRIPT_DIR/acer_rgb_gui.py"
Icon=input-keyboard
Terminal=false
Categories=Utility;HardwareSettings;Settings;
StartupNotify=true
EOF

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true

echo ""
echo "Installed. Search for 'AN KB Color Picker' in your app launcher."
echo ""
echo "First run: click 'Browse...' and point it at your"
echo "acer-predator-turbo-and-rgb-keyboard-linux-module folder"
echo "(https://github.com/JafarAkhondali/acer-predator-turbo-and-rgb-keyboard-linux-module)"
echo "if you haven't installed that module yet, install it first — this app"
echo "controls it, it doesn't replace it."