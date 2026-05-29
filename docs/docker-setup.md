# Docker Setup — histovis-workers

This document describes the Docker configuration added for `consumer-qwen` and
`consumer-stardist`, including design decisions and a bug fix applied during the setup.

---

## Bug fix: AMQP URL typo

**File:** `consumer-common/consumer_common/settings.py`

The `rabbitmq_url` property returned `"ampq://"` instead of `"amqp://"`. Because
`broker.py` passes this URL directly to `aio_pika.connect_robust()`, both consumers
would have failed to connect to RabbitMQ at runtime with no obvious error message.

```python
# before
f"ampq://{self.rabbitmq_user}:{self.rabbitmq_password}@..."

# after
f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@..."
```

---

## Files created

### `consumer-qwen/Dockerfile`

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY consumer-common/ /consumer-common/
COPY consumer-qwen/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY consumer-qwen/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Key decisions:**

- `build-essential` + `cmake` are required because `llama-cpp-python` compiles C++
  extensions from source during `pip install`.
- `consumer-common/` is copied to `/consumer-common/` before running `pip install`.
  The entry `-e ../consumer-common` in `requirements.txt` resolves relative to
  `WORKDIR /app`, making `../consumer-common` → `/consumer-common`. This means the
  editable install works without any path rewriting.
- Layer order — system deps → pip install → app code — maximises cache reuse: the slow
  `pip install` layer (llama-cpp-python compilation can take several minutes) is only
  invalidated when `requirements.txt` or `consumer-common` changes, not on every code edit.

---

### `consumer-stardist/Dockerfile`

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY consumer-common/ /consumer-common/
COPY consumer-stardist/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY consumer-stardist/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

**Key decisions:**

- No compiler needed — all packages (TensorFlow, stardist, scikit-image) ship prebuilt
  wheels for `linux/amd64` + Python 3.12.
- `libgomp1` provides OpenMP support required by NumPy parallel operations.
- `libglib2.0-0` is needed by some TensorFlow I/O internals on Debian slim.
- Same consumer-common path trick as the Qwen Dockerfile.
- `tensorflow==2.17.0` is the first TF release with official Python 3.12 support. TF 2.16
  introduced Keras 3; stardist 0.9.1 is compatible with it.

---

### `docker-compose.yml`

```yaml
services:
  consumer-qwen:
    build:
      context: .
      dockerfile: consumer-qwen/Dockerfile
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./consumer-qwen/models:/app/models:ro
    networks:
      - histovis-network
    restart: unless-stopped

  consumer-stardist:
    build:
      context: .
      dockerfile: consumer-stardist/Dockerfile
    ports:
      - "8001:8001"
    env_file: .env
    volumes:
      - stardist_cache:/root/.stardist
    networks:
      - histovis-network
    restart: unless-stopped

volumes:
  stardist_cache:

networks:
  histovis-network:
    external: true
```

**Key decisions:**

- `context: .` (repo root) for both services so each Dockerfile can `COPY
  consumer-common/` across the monorepo boundary.
- **Qwen model** — bind-mount `./consumer-qwen/models:/app/models:ro`. The `model_path`
  setting defaults to `"models/qwen2.5-0.5b-instruct-q5_k_m.gguf"`, which resolves to
  `/app/models/…` inside the container. The model file is gitignored and never bundled
  in the image.
- **StarDist model** — named volume `stardist_cache` mounted at `/root/.stardist` (the
  default stardist cache directory when running as root). `model_loader.py` calls
  `StarDist2D.from_pretrained("2D_versatile_he")` on startup, which auto-downloads the
  model (~100 MB) on first run and reuses the cached version on subsequent starts.
- `histovis-network` is declared `external: true` — it is created and owned by the
  `histovis-monorepo` docker-compose stack.
- No `depends_on` for RabbitMQ because it lives in a separate compose stack; the
  `connect_robust` call in `broker.py` handles reconnection automatically.

---

### `consumer-stardist/requirements.txt`

Updated from unpinned package names to pinned direct dependencies:

```
aio-pika==9.6.2
csbdeep==0.8.0
fastapi==0.115.6
httpx==0.28.1
numpy==1.26.4
...
tensorflow==2.17.0
stardist==0.9.1
-e ../consumer-common
```

`numpy==1.26.4` (last 1.x release) is used rather than the 2.x line for compatibility
with stardist's internal NumPy usage patterns.

`consumer-qwen/requirements.txt` was already a full `pip freeze` and was left unchanged.

To lock all transitive dependencies after a successful build:

```bash
docker compose run --rm consumer-stardist pip freeze > consumer-stardist/requirements.txt
# Then manually restore the "-e ../consumer-common" line at the bottom
```

---

### `.dockerignore`

Excludes from the Docker build context:

| Pattern                  | Reason                                                      |
|--------------------------|-------------------------------------------------------------|
| `consumer-qwen/models/`  | GGUF file is ~400 MB; excluding it prevents slow context transfer on every build |
| `.venv-wsl`              | WSL virtual environment, not needed inside containers       |
| `.env`                   | Secrets; injected at runtime via `env_file` in compose      |
| `**/__pycache__`, `*.pyc`| Compiled bytecache, not needed                              |
| `*/logs/`                | Runtime log files                                           |

---

### `.env.example`

Two corrections applied:

| Field                  | Before                             | After                              |
|------------------------|------------------------------------|------------------------------------|
| `ANALYSIS_SERVICE_URL` | `http://analysis-service:8080`     | `http://analysis-service:8082`     |
| `RABBITMQ_USER`        | *(blank)*                          | `histovis`                         |
| `RABBITMQ_PASSWORD`    | *(blank)*                          | `histovis123`                      |

Port 8082 matches both the Spring Boot service configuration in `histovis-monorepo` and
the default value in `BaseConsumerSettings.analysis_service_url`.
