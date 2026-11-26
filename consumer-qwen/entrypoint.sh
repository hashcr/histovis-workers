#!/bin/sh
set -e

MODEL_DIR="/app/models"

download_if_missing() {
    file_name="$1"
    url="$2"
    path="$MODEL_DIR/$file_name"

    if [ ! -f "$path" ]; then
        echo "Downloading $file_name from Hugging Face..."
        curl -fSL --retry 3 --retry-delay 5 -o "${path}.tmp" "$url"
        mv "${path}.tmp" "$path"
        echo "$file_name downloaded successfully."
    else
        echo "$file_name already present — skipping download."
    fi
}

mkdir -p "$MODEL_DIR"

download_if_missing "Qwen3VL-2B-Instruct-Q4_K_M.gguf" \
    "https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct-GGUF/resolve/main/Qwen3VL-2B-Instruct-Q4_K_M.gguf"

download_if_missing "mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf" \
    "https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct-GGUF/resolve/main/mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf"

exec uvicorn main:app --host 0.0.0.0 --port 8000
