#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LLAMA_DIR="$SCRIPT_DIR/llama"
MODEL_PATH="$SCRIPT_DIR/models/tinyllama.gguf"

if [[ ! -f "$MODEL_PATH" ]]; then
    echo "Error: Model file not found at $MODEL_PATH"
    exit 1
fi

if [[ ! -f "$LLAMA_DIR/llama-server" ]]; then
    echo "Error: llama-server not found at $LLAMA_DIR/llama-server"
    exit 1
fi

"$LLAMA_DIR/llama-server" \
  -m "$MODEL_PATH" \
  -c 4096 \
  -ngl 999 \
  --host 127.0.0.1 \
  --port 8080 \
  -n 256