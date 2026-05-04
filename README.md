# histovis-workers

RabbitMQ consumer microservices for the HistoVis medical image analysis system.

- **consumer-qwen** — Qwen2.5-0.5B GGUF inference via llama-cpp-python (port 8000)
- **consumer-stardist** — H&E nuclei detection via StarDist 2D_versatile_he (port 8001)

## Prerequisites

- Docker and Docker Compose
- The `histovis-network` external Docker network (created by `histovis-monorepo`)
- The Qwen GGUF model file (see below)

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd histovis-workers
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in RABBITMQ_USER and RABBITMQ_PASSWORD
```

### 3. Download the Qwen GGUF model

Place the model file at `consumer-qwen/models/qwen2.5-0.5b-instruct-q5_k_m.gguf`.
Download from [Hugging Face — Qwen2.5-0.5B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF).

```bash
mkdir -p consumer-qwen/models
# example using huggingface-cli:
huggingface-cli download Qwen/Qwen2.5-0.5B-Instruct-GGUF \
    qwen2.5-0.5b-instruct-q5_k_m.gguf \
    --local-dir consumer-qwen/models
```

The model file is gitignored and never bundled into the Docker image; it is mounted read-only at container start.

### 4. Build and start the services

```bash
docker compose build
docker compose up -d
```

**First start note — StarDist model:** `consumer-stardist` calls
`StarDist2D.from_pretrained("2D_versatile_he")` on startup, which downloads the pretrained
model (~100 MB) into the `stardist_cache` named volume. Subsequent starts reuse the cache.
Monitor progress with `docker compose logs -f consumer-stardist`.

### 5. Verify health

```bash
curl http://localhost:8000/health   # {"status":"up","model_ready":true|false}
curl http://localhost:8001/health   # {"status":"up","model_ready":true|false}
```

`model_ready` becomes `true` once the background thread finishes loading the model.

## Architecture

```
histovis-monorepo (external network: histovis-network)
├── analysis-service  :8082   — Spring Boot, sends jobs via RabbitMQ
├── rabbitmq                  — user: histovis / exchange: analysis.exchange
└── minio                     — image storage (presigned URLs in JobMessage.imageUrl)

histovis-workers
├── consumer-qwen     :8000   — subscribes to job.qwen.*  → qwen.queue
└── consumer-stardist :8001   — subscribes to job.stardist.* → stardist.queue
```

RabbitMQ message shape (`JobMessage`):

| field    | type            | notes                              |
|----------|-----------------|------------------------------------|
| jobId    | UUID            |                                    |
| imageUrl | str             | presigned MinIO URL                |
| args     | dict[str, str]  | plugin-specific params, default {} |

The routing key suffix (e.g. `job.qwen.describe_wsi`) becomes the `plugin_code`, which is
looked up in `handlers.yaml` to dispatch to the correct async handler function.

## Volumes

| volume          | mount point      | purpose                           |
|-----------------|------------------|-----------------------------------|
| host bind       | `/app/models`    | Qwen GGUF model (read-only)       |
| `stardist_cache`| `/root/.stardist`| StarDist pretrained model cache   |

## Locking transitive dependencies (consumer-stardist)

`consumer-stardist/requirements.txt` pins direct dependencies only. After a successful
build, capture the full transitive lock with:

```bash
docker compose run --rm consumer-stardist pip freeze > consumer-stardist/requirements.txt
# Remove the "-e" editable line and re-add it at the bottom manually
```

`consumer-qwen/requirements.txt` is already a full pip freeze.

## Useful commands

```bash
# Tail logs
docker compose logs -f consumer-qwen
docker compose logs -f consumer-stardist

# Rebuild a single service after code changes
docker compose build consumer-qwen
docker compose up -d --no-deps consumer-qwen

## License

This project is licensed under the
**Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**.

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

You are free to **use, fork, and modify** this project for non-commercial purposes,
as long as you **credit Ashuin Sharma as the original creator**.

**Commercial use is not permitted** without prior written permission from the author.

See the [LICENSE](./LICENSE) file for full details.

---

## Attribution

If you use or build upon HistoVis in your work, please credit it as follows:

> HistoVis — originally created by **Ashuin Sharma**
> GitHub: https://github.com/hashcr

---

## Commercial Licensing

Interested in using HistoVis in a commercial product or service?
Get in touch to discuss licensing options:

📧 **ashuin.sharma@gmail.com**

---

## Author

**Ashuin Sharma**
📧 ashuin.sharma@gmail.com

---

## Third-Party Licenses

This project makes use of the following open-source libraries:

| Library | License |
|---|---|
| StarDist | BSD-2-Clause |
| aio-pika | Apache 2.0 |
| Spring Boot | Apache 2.0 |
| scikit-image | BSD-3-Clause |
| llama-cpp-python | MIT |
| Ionic/Angular | MIT |

All third-party licenses are compatible with the non-commercial use terms of this project.

# Shell into a running container
docker compose exec consumer-stardist bash
```

---

Author: Ashuin Sharma
