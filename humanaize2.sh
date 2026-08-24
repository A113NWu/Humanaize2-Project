#!/bin/bash
# Humanaize 2.0 Agent Launcher

# Get the directory where the script is located
# Use readlink to resolve symlinks correctly
SCRIPT_PATH="${BASH_SOURCE[0]}"
while [ -L "$SCRIPT_PATH" ]; do
    SCRIPT_PATH="$(readlink -f "$SCRIPT_PATH")"
done
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"

# Determine if running from source or installed
# Check if we're in the project root (has src/ directory)
if [ -d "$SCRIPT_DIR/src" ]; then
    # Running from source code
    echo "[INFO] Running from source code directory"
    MAIN_DIR="$SCRIPT_DIR"
    export PYTHONPATH="$MAIN_DIR:$MAIN_DIR/src:$MAIN_DIR/src/core:$PYTHONPATH"
else
    # Running from installed location
    echo "[INFO] Running from installed location"
    MAIN_DIR="/usr/share/humanaize2"
    export PYTHONPATH="$MAIN_DIR:$MAIN_DIR/src:$MAIN_DIR/src/core:$PYTHONPATH"
fi

# Model configuration
# Prefer the project’s actual `model/` directory, but accept legacy `models/` setups too.
MODEL_DIR="$MAIN_DIR/model"
if [ ! -d "$MODEL_DIR" ] && [ -d "$MAIN_DIR/models" ]; then
    MODEL_DIR="$MAIN_DIR/models"
fi
mkdir -p "$MODEL_DIR"
MODEL_FILE="$MODEL_DIR/tinyllama.gguf"
MODEL_URL="https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed."
    echo "Please install Python 3.8 or higher."
    exit 1
fi

# Function to download TinyLlama model
download_model() {
    echo "[INFO] Downloading TinyLlama model..."
    
    # Create models directory if it doesn't exist
    mkdir -p "$MODEL_DIR"
    
    # Check if model already exists
    if [ -f "$MODEL_FILE" ]; then
        echo "[INFO] Model file already exists at $MODEL_FILE"
        echo "[INFO] File size: $(du -h "$MODEL_FILE" | cut -f1)"
        read -p "Do you want to re-download it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "[INFO] Using existing model file."
            return 0
        fi
    fi
    
    # Check if wget or curl is available
    if command -v wget &> /dev/null; then
        echo "[INFO] Using wget to download model..."
        echo "[INFO] This may take a few minutes depending on your connection..."
        if wget -O "$MODEL_FILE" "$MODEL_URL" --show-progress 2>&1; then
            if [ -s "$MODEL_FILE" ]; then
                echo "[SUCCESS] Model downloaded successfully to $MODEL_FILE"
                echo "[INFO] Model size: $(du -h "$MODEL_FILE" | cut -f1)"
            else
                echo "[ERROR] Downloaded file is empty or corrupted."
                rm -f "$MODEL_FILE"
                echo "[ERROR] Please check your internet connection and try again."
                return 1
            fi
        else
            echo "[ERROR] Download failed."
            rm -f "$MODEL_FILE"
            echo "[ERROR] Please check your internet connection and try again."
            return 1
        fi
    elif command -v curl &> /dev/null; then
        echo "[INFO] Using curl to download model..."
        echo "[INFO] This may take a few minutes depending on your connection..."
        if curl -L -o "$MODEL_FILE" "$MODEL_URL" --progress-bar; then
            if [ -s "$MODEL_FILE" ]; then
                echo "[SUCCESS] Model downloaded successfully to $MODEL_FILE"
                echo "[INFO] Model size: $(du -h "$MODEL_FILE" | cut -f1)"
            else
                echo "[ERROR] Downloaded file is empty or corrupted."
                rm -f "$MODEL_FILE"
                echo "[ERROR] Please check your internet connection and try again."
                return 1
            fi
        else
            echo "[ERROR] Download failed."
            rm -f "$MODEL_FILE"
            echo "[ERROR] Please check your internet connection and try again."
            return 1
        fi
    else
        echo "[ERROR] Neither wget nor curl is installed."
        echo "Please install wget or curl to download the model."
        echo ""
        echo "On Ubuntu/Debian: sudo apt-get install wget"
        echo "On Fedora/RHEL:   sudo dnf install wget"
        echo "On Arch Linux:    sudo pacman -S wget"
        exit 1
    fi
}

# Check for download-model command
if [ "$1" = "download-model" ]; then
    download_model
    exit 0
fi

# Run the main script with all arguments
echo "[INFO] Starting Humanaize 2.0..."
exec python3 "$MAIN_DIR/src/core/main.py" "$@"
