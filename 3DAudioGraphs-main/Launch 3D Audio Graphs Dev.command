#!/bin/bash

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$REPO_DIR/frontend"
NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
NODE_VERSION_FILE="$REPO_DIR/.nvmrc"

pause_on_failure() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        echo
        echo "Launcher exited with code $exit_code."
        echo "Press Enter to close this window."
        read -r
    fi
}

trap pause_on_failure EXIT

if [[ ! -d "$FRONTEND_DIR" ]]; then
    echo "Could not find the frontend directory at: $FRONTEND_DIR"
    exit 1
fi

if [[ -f "$NVM_DIR/nvm.sh" ]]; then
    # shellcheck disable=SC1090
    . "$NVM_DIR/nvm.sh"
    if [[ -f "$NODE_VERSION_FILE" ]]; then
        NODE_VERSION="$(tr -d '[:space:]' < "$NODE_VERSION_FILE")"
        if [[ -n "$NODE_VERSION" ]]; then
            nvm use "$NODE_VERSION" >/dev/null
        fi
    fi
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "npm is not available. Install Node.js 24 first."
    exit 1
fi

cd "$FRONTEND_DIR"

if [[ ! -d node_modules ]]; then
    echo "Installing frontend dependencies..."
    npm install
fi

echo "Launching 3D Audio Graphs dev app..."
echo "Working directory: $FRONTEND_DIR"
echo

npm run electron:dev