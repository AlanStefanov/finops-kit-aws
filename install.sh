#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="finops-kit"
BIN_DIR="$HOME/.local/bin"

echo "========================================"
echo " FinOpsKit for AWS - Installer"
echo "========================================"

# 1. Copy AWS credentials if not present
if [ ! -f "$DIR/.aws/credentials" ]; then
    echo "[1/4] Copying AWS credentials..."
    mkdir -p "$DIR/.aws"
    if [ -f "$HOME/.aws/credentials" ]; then
        cp "$HOME/.aws/credentials" "$DIR/.aws/"
        chmod 600 "$DIR/.aws/credentials"
        echo "       Credentials copied from ~/.aws/credentials"
    else
        echo "       [WARN] No ~/.aws/credentials found."
        echo "       You'll need to configure AWS CLI first: aws configure"
    fi
    if [ -f "$HOME/.aws/config" ]; then
        cp "$HOME/.aws/config" "$DIR/.aws/"
        echo "       Config copied from ~/.aws/config"
    fi
else
    echo "[1/4] AWS credentials already present, skipping."
fi

# 2. Install Python dependencies
echo "[2/4] Installing Python dependencies..."
pip3 install -r "$DIR/requirements.txt" --break-system-packages 2>/dev/null \
    || pip3 install -r "$DIR/requirements.txt" --user 2>/dev/null \
    || {
        python3 -m venv "$DIR/venv"
        "$DIR/venv/bin/pip" install -r "$DIR/requirements.txt"
        VENV=1
    }
echo "       Done."

# 3. Create launcher script
echo "[3/4] Creating launcher script..."
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/$APP_NAME" << 'LAUNCHER'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"

# Try project-level venv first
if [ -f "$DIR/venv/bin/python" ]; then
    PYTHON="$DIR/venv/bin/python"
else
    PYTHON="python3"
fi

cd "$DIR"
exec $PYTHON main.py "$@"
LAUNCHER

# Fix the path in the launcher: it should point to the project dir
PROJECT_DIR="$DIR"
cat > "$BIN_DIR/$APP_NAME" << LAUNCHER
#!/usr/bin/env bash
PROJECT_DIR="$PROJECT_DIR"
if [ -f "\$PROJECT_DIR/venv/bin/python" ]; then
    PYTHON="\$PROJECT_DIR/venv/bin/python"
else
    PYTHON="python3"
fi
cd "\$PROJECT_DIR"
exec \$PYTHON main.py "\$@"
LAUNCHER

chmod +x "$BIN_DIR/$APP_NAME"
echo "       Launcher created: $BIN_DIR/$APP_NAME"

# 4. Create desktop opener (opens in a new terminal window)
echo "[4/4] Creating desktop opener..."
cat > "$BIN_DIR/${APP_NAME}-window" << WINDOW
#!/usr/bin/env bash
PROJECT_DIR="$PROJECT_DIR"

# Detect terminal emulator (alacritty preferred)
if command -v alacritty &>/dev/null; then
    exec alacritty -e bash -c "cd '$PROJECT_DIR' && $BIN_DIR/$APP_NAME; exec bash"
elif command -v gnome-terminal &>/dev/null; then
    exec gnome-terminal -- bash -c "cd '$PROJECT_DIR' && $BIN_DIR/$APP_NAME; exec bash"
elif command -v xterm &>/dev/null; then
    exec xterm -e bash -c "cd '$PROJECT_DIR' && $BIN_DIR/$APP_NAME; exec bash"
elif command -v konsole &>/dev/null; then
    exec konsole --hold -e bash -c "cd '$PROJECT_DIR' && $BIN_DIR/$APP_NAME"
elif command -v xfce4-terminal &>/dev/null; then
    exec xfce4-terminal --hold -e bash -c "cd '$PROJECT_DIR' && $BIN_DIR/$APP_NAME"
else
    echo "No terminal emulator found. Running inline..."
    cd "$PROJECT_DIR" && $BIN_DIR/$APP_NAME
fi
WINDOW
chmod +x "$BIN_DIR/${APP_NAME}-window"

echo ""
echo "========================================"
echo " Installation complete!"
echo "========================================"
echo ""
echo "  Run in terminal:     $APP_NAME"
echo "  Open in window:      ${APP_NAME}-window"
echo ""
echo "  Make sure $BIN_DIR is in your PATH."
echo "  You can add it with:  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""

# Auto-open window if not in a pipe
if [ -t 1 ]; then
    read -p "Open app now? [Y/n] " -r REPLY
    REPLY="${REPLY:-y}"
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        exec "$BIN_DIR/${APP_NAME}-window"
    fi
fi
