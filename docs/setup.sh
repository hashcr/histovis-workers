#!/usr/bin/env bash
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
REPO_URL="https://github.com/hashcr/histovis-workers"
INSTALL_DIR="/opt/histovis-workers"
QWEN_MODEL_DIR="$INSTALL_DIR/consumer-qwen/models"
QWEN_MODEL_FILE="qwen2.5-0.5b-instruct-q5_k_m.gguf"
QWEN_MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/$QWEN_MODEL_FILE"

# ── 1. Docker ─────────────────────────────────────────────────────────────────
if command -v docker &>/dev/null; then
  echo "==> Docker already installed, skipping."
else
  echo "==> Installing Docker..."
  curl -fsSL https://get.docker.com | sh
fi

# ── 2. Clone or update repo ───────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "==> Repo already cloned, pulling latest..."
  git -C "$INSTALL_DIR" pull
else
  echo "==> Cloning repository..."
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

# ── 3. Validate .env ──────────────────────────────────────────────────────────
if [ ! -f "$INSTALL_DIR/.env" ]; then
  echo ""
  echo "ERROR: $INSTALL_DIR/.env not found."
  echo "  Copy .env.example to $INSTALL_DIR/.env and fill in production values, then re-run."
  echo ""
  exit 1
fi
echo "==> .env found."

# ── 4. Qwen model ─────────────────────────────────────────────────────────────
mkdir -p "$QWEN_MODEL_DIR"
if [ -f "$QWEN_MODEL_DIR/$QWEN_MODEL_FILE" ]; then
  echo "==> Qwen model already present, skipping download."
else
  echo "==> Downloading Qwen model (~400 MB)..."
  curl -L --progress-bar -o "$QWEN_MODEL_DIR/$QWEN_MODEL_FILE" "$QWEN_MODEL_URL"
fi

# ── 5. Docker network ─────────────────────────────────────────────────────────
if docker network inspect histovis-network &>/dev/null; then
  echo "==> Docker network histovis-network already exists, skipping."
else
  echo "==> Creating Docker network histovis-network..."
  docker network create histovis-network
fi

# ── 6. Start services ─────────────────────────────────────────────────────────
echo "==> Starting services..."
docker compose --project-directory "$INSTALL_DIR" up -d --build

echo ""
echo "==> Done. Services are starting up."
echo "    Check status with: docker compose --project-directory $INSTALL_DIR ps"
