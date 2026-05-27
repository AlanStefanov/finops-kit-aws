#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# ── Open in the system's default terminal ────────────────────
# Priority: x-terminal-emulator (Debian/Ubuntu default),
#           then common terminals by popularity.
# If nothing works, run inline.

if command -v x-terminal-emulator &>/dev/null; then
    exec x-terminal-emulator -e python3 main.py
elif command -v gnome-terminal &>/dev/null; then
    exec gnome-terminal -- python3 main.py
elif command -v alacritty &>/dev/null; then
    exec alacritty -e python3 main.py
elif command -v kitty &>/dev/null; then
    exec kitty python3 main.py
elif command -v konsole &>/dev/null; then
    exec konsole --hold -e python3 main.py
elif command -v xfce4-terminal &>/dev/null; then
    exec xfce4-terminal --hold -e python3 main.py
elif command -v xterm &>/dev/null; then
    exec xterm -e python3 main.py
else
    echo "No terminal emulator detected."
    echo "Run directly with: python3 main.py"
    exit 1
fi
