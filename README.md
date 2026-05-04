# HistoVis AI

> Python AI worker services for HistoVis — a medical image analysis platform for whole slide image (WSI) processing.
> Built as part of an academic thesis project.

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
![Status: Mostly Complete](https://img.shields.io/badge/status-mostly%20complete-green)

---

## Overview

HistoVis AI contains the Python microservices responsible for AI-powered analysis of histopathology whole slide images. Workers consume jobs from RabbitMQ, run inference, and report results back to the Spring Boot backend.

**Services:**
- `consumer-stardist` — Cell detection and counting using StarDist for H&E and IHC images
- `consumer-llama` — Natural language description of WSI images using a quantized LLM (Mistral 7B GGUF)
- `consumer-common` — Shared internal package (RabbitMQ client, result notifier, config base)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Messaging | aio-pika (RabbitMQ async consumer) |
| H&E cell detection | StarDist (`2D_versatile_he` pretrained model) |
| IHC nucleus counting | StarDist + scikit-image (`rgb2hed` DAB deconvolution) |
| LLM inference | llama-cpp-python (in-process, GGUF quantized models) |
| HTTP callbacks | httpx (async) |
| Config | pydantic-settings |
| Infrastructure | Docker Compose |

---

## Architecture

```
RabbitMQ (analysis.exchange)
   │
   ├── job.stardist.#  →  consumer-stardist
   │                         ├── Loads StarDist model at startup
   │                         ├── Runs inference via asyncio.run_in_executor
   │                         └── POSTs result to analysis-service
   │
   └── job.llama.#     →  consumer-llama
                             ├── Loads GGUF model at startup
                             ├── Runs inference via asyncio.run_in_executor
                             └── POSTs result to analysis-service
```

**RabbitMQ config:**
- Exchange: `analysis.exchange` (topic)
- Routing keys: `job.<model>.<task>.<target>` (e.g. `job.stardist.detect.he`)
- Result routing: `job.results.completed` / `job.results.failed` → `results.queue`
- Prefetch: `prefetch_count=1` for fair dispatch across scaled instances

---

## Prerequisites

- Python 3.11+
- Docker + Docker Compose
- RabbitMQ running (shared `histovis-network`)
- Model files (see below)

---

## Model Setup

### StarDist
The `2D_versatile_he` pretrained model is downloaded automatically by StarDist on first run and cached at:
```
~/.keras/datasets/
```
No manual download required.

### Mistral 7B GGUF (for consumer-llama)
Download the quantized model manually and place it in the `models/` directory:

```bash
# Example: Q4_K_M quantization
wget https://huggingface.co/TheBloke/Mistral-7B-v0.1-GGUF/resolve/main/mistral-7b-v0.1.Q4_K_M.gguf \
  -O models/mistral-7b-v0.1.Q4_K_M.gguf
```

Mount the `models/` directory as a volume — models are never bundled into Docker images.

---

## Getting Started

```bash
# Clone the repo
git clone https://github.com/hashcr/histovis-ai.git
cd histovis-ai

# Create the shared Docker network (if not already created)
docker network create histovis-network

# Start all workers
docker compose up --build

# Or run individually
docker compose up --build consumer-stardist
docker compose up --build consumer-llama
```

---

## Environment Configuration

Each service reads config from environment variables via `pydantic-settings`:

```env
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
ANALYSIS_SERVICE_URL=http://analysis-service:8080
```

> ⚠️ Never commit real credentials. Use `.env` files or secrets management.

---

## Related Repositories

| Repo | Description |
|---|---|
| [histovis-app](https://github.com/hashcr/histovis-app) | Ionic/Angular frontend |
| [histovis-monorepo](https://github.com/hashcr/histovis-monorepo) | Java Spring Boot backend (analysis-service, API gateway) |

---

## Academic References

- **StarDist:** Schmidt et al., MICCAI 2018; Weigert et al., Nature Methods 2022
- **DAB Color Deconvolution:** Ruifrok & Johnston, Analytical and Quantitative Cytology and Histology, 2001

---

## License

This project is licensed under **CC BY-NC 4.0**.
See the [LICENSE](./LICENSE) file for details.

Commercial use requires written permission from the author.

---

## Author

**Ashuin Sharma**
📧 ashuin.sharma@gmail.com
