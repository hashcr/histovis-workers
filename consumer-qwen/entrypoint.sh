#!/bin/sh
set -e

MODEL_DIR="/app/models"
MODEL_FILE="qwen2.5-0.5b-instruct-q5_k_m.gguf"
MODEL_PATH="$MODEL_DIR/$MODEL_FILE"
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/$MODEL_FILE"

mkdir -p "$MODEL_DIR"

if [ ! -f "$MODEL_PATH" ]; then
    echo "Model not found at $MODEL_PATH — downloading from Hugging Face..."
    curl -fSL --retry 3 --retry-delay 5 -o "${MODEL_PATH}.tmp" "$MODEL_URL"
    mv "${MODEL_PATH}.tmp" "$MODEL_PATH"
    echo "Model downloaded successfully."
else
    echo "Model already present at $MODEL_PATH — skipping download."
fi

exec uvicorn main:app --host 0.0.0.0 --port 8000
