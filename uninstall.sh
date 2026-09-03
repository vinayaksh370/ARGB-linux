#!/usr/bin/env bash
set -e

DESKTOP_FILE="$HOME/.local/share/applications/argb.desktop"
CONFIG_DIR="$HOME/.config/argb"

rm -f "$DESKTOP_FILE"
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true

echo "Uninstalled ARGB."

if [ -d "$CONFIG_DIR" ]; then
    read -p "Delete saved config and profiles at $CONFIG_DIR? [y/N] " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        rm -rf "$CONFIG_DIR"
        echo "Removed $CONFIG_DIR"
    fi
fi