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

# 4. Done
echo "[4/4] Done."
echo ""
echo "========================================"
echo " Installation complete!"
echo "========================================"
echo ""
echo "  Run:     $APP_NAME"
echo "  Or:      ./run.sh"
echo "  Or:      python3 main.py"
echo ""
echo "  Make sure $BIN_DIR is in your PATH."
echo "  You can add it with:  export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
echo "  Tip: the app runs in your current terminal — no new window opens."
