#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
ICON_PATH="$SCRIPT_DIR/assets/icon/pogos.png"
APP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$APP_DIR/argb.desktop"

echo "== ARGB installer =="
echo "Detected install location: $SCRIPT_DIR"

# --- dependency checks -------------------------------------------------
missing=()
command -v python3 >/dev/null 2>&1 || missing+=("python3")
python3 -c "import nicegui" >/dev/null 2>&1 || missing+=("nicegui (pip install nicegui)")
command -v pkexec >/dev/null 2>&1 || missing+=("pkexec (polkit)")

if [ ${#missing[@]} -ne 0 ]; then
    echo ""
    echo "Missing dependencies:"
    for m in "${missing[@]}"; do echo "  - $m"; done
    echo ""
    echo "On Arch/CachyOS:"
    echo "  sudo pacman -S python polkit"
    echo "  pip install nicegui --break-system-packages"
    echo ""
    echo "Continuing anyway, but the app may not run until these are installed."
fi

# optional: native window mode
if ! python3 -c "import webview" >/dev/null 2>&1; then
    echo ""
    echo "NOTE: pywebview isn't installed, so ARGB will open in your browser"
    echo "instead of a native window. For a native window:"
    echo "  pip install pywebview --break-system-packages"
    echo "  sudo pacman -S webkit2gtk-4.1 python-gobject gtk3"
fi

# check for a running polkit auth agent
if ! pgrep -f "polkit.*agent" >/dev/null 2>&1 && ! pgrep -f "polkit-gnome" >/dev/null 2>&1 && ! pgrep -f "polkit-kde" >/dev/null 2>&1; then
    echo ""
    echo "NOTE: No polkit authentication agent appears to be running."
    echo "Without one, the Apply button's password prompt won't show up."
    echo "On Hyprland, add something like this to your config:"
    echo "  exec-once = /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1"
fi

# --- permissions ---------------------------------------------------------
chmod +x "$SRC_DIR/acer_rgb_gui.py"
chmod +x "$SRC_DIR/apply_rgb.py"

# --- desktop entry ---------------------------------------------------------
mkdir -p "$APP_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=ARGB
Comment=Control 4-zone RGB keyboard lighting on Acer Nitro/Predator laptops
Exec=python3 "$SRC_DIR/acer_rgb_gui.py"
Icon=$ICON_PATH
Terminal=false
Categories=Utility;HardwareSettings;Settings;
StartupNotify=true
EOF

command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true

echo ""
echo "Installed. Search for 'ARGB' in your app launcher."
echo ""
echo "Set your module folder via 'Change folder...' if auto-detect doesn't find it."