#!/bin/bash
# Install a .desktop launcher on Linux.
# Run from anywhere: bash GUI/install_linux_shortcut.sh
# Places a shortcut on the Desktop and in the application menu.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ICON_PATH="${SCRIPT_DIR}/DesktopIcon.png"
DESKTOP_FILE="${SCRIPT_DIR}/BioacousticsRhythmPipeline.desktop"

# Find Python
PYTHON=""
for p in \
    "$HOME/anaconda3/envs/rhythm_env/bin/python" \
    "$HOME/miniconda3/envs/rhythm_env/bin/python" \
    "/opt/anaconda3/envs/rhythm_env/bin/python"; do
    if [ -x "$p" ]; then
        PYTHON="$p"
        break
    fi
done
[ -z "$PYTHON" ] && PYTHON="$(which python3 2>/dev/null || echo python3)"

# Write .desktop file with correct absolute paths
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Bioacoustics Rhythm Pipeline
Comment=Configure and run the bioacoustics rhythm analysis pipeline
Exec=${PYTHON} ${SCRIPT_DIR}/pipeline_gui.py
Path=${PROJECT_DIR}
Icon=${ICON_PATH}
Terminal=false
Categories=Science;Education;
EOF

chmod +x "$DESKTOP_FILE"

# Copy to Desktop
DESKTOP_DIR="${HOME}/Desktop"
if [ -d "$DESKTOP_DIR" ]; then
    cp "$DESKTOP_FILE" "$DESKTOP_DIR/"
    echo "Shortcut placed on Desktop: ${DESKTOP_DIR}/BioacousticsRhythmPipeline.desktop"
fi

# Copy to applications menu
APPS_DIR="${HOME}/.local/share/applications"
mkdir -p "$APPS_DIR"
cp "$DESKTOP_FILE" "$APPS_DIR/"
echo "Shortcut added to applications menu: ${APPS_DIR}/BioacousticsRhythmPipeline.desktop"
echo "Done."
