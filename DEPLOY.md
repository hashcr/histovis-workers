# Deploying HistoVis to a new server

This covers a from-scratch deployment of the full HistoVis stack — **histovis-monorepo**
(this repo: postgres, rabbitmq, minio, user/images/analysis-service) and
**histovis-workers** (the separate AI/analysis worker repo: consumer-qwen,
consumer-stardist, consumer-tileserver) — onto a brand-new VM via Coolify.

Both repos now ship a `docker-compose.yaml` (note: `.yaml`, not the older `.yml`)
with working defaults baked in, so the actual deploy step needs almost no manual
configuration. What's below is everything that setup *can't* be baked into a
compose file — Coolify-specific manual steps, and the reasoning behind them.

## 1. Prerequisites

- A VM with at least **4 vCPU / 8GB RAM** recommended (7.6GB was workable for the
  original deployment, including the Qwen3-VL vision model — see "Memory notes"
  below if you're tighter on RAM).
- Open inbound ports: **22** (SSH), **80** and **443** (HTTP/HTTPS — Coolify's proxy
  and all app traffic route through these two only; no other ports need to be
  opened publicly, even though services internally use 5432/5672/8085-8092/9000-9001 —
  those stay on the Docker-internal network and host-only bindings).
- Install Coolify following its own install script/docs on the fresh VM.

## 2. Deploy order

Deploy **histovis-monorepo first**, then **histovis-workers**. Reason: workers'
`docker-compose.yaml` declares the shared `histovis-network` the same way
monorepo's does (name only, not `external: true`) — whichever deploys first
creates it, the second one just attaches to the existing one. Workers' services
also actively depend on monorepo's postgres/rabbitmq/minio being reachable by
hostname over that network, so there's no reason to deploy it first anyway.

For each repo, in Coolify:
1. Create a new **Application** resource, type **Docker Compose**, pointing at
   the repo and branch.
2. Coolify will detect `docker-compose.yaml`. If it instead picks up an old
   `docker-compose.yml` (both may exist during the migration period — see the
   note at the bottom of this file), explicitly set the Docker Compose file
   path/name in the resource's settings.
3. Set the environment variables listed below (copied from the comment block at
   the bottom of each repo's `docker-compose.yaml`).
4. Deploy.

## 3. Required environment variables

### histovis-monorepo
```
PUBLIC_DOMAIN=<the University's actual domain, e.g. histovis.example.edu>
JWT_SECRET=<generate with: openssl rand -hex 32>
POSTGRES_PASSWORD=<pick something, or keep the default for quick testing>
RABBITMQ_USER=histovis
RABBITMQ_PASSWORD=<pick something>
MINIO_ACCESS_KEY=<pick something>
MINIO_SECRET_KEY=<pick something>
```

### histovis-workers
```
PUBLIC_DOMAIN=<same value as above — must match>
RABBITMQ_USER=<same value as monorepo's>
RABBITMQ_PASSWORD=<same value as monorepo's>
MINIO_ACCESS_KEY=<same value as monorepo's>
MINIO_SECRET_KEY=<same value as monorepo's>
```

Everything else has a working default baked into the compose files — you only
need to override other values (ports, bucket name, etc.) if you have a specific
reason to.

**Important**: if you ever change `RABBITMQ_PASSWORD` *after* the rabbitmq
container has already booted once, updating the env var alone does nothing —
the Docker image only applies `RABBITMQ_DEFAULT_PASS` on a brand-new, empty
volume. You'd also need to run
`docker exec <rabbitmq-container> rabbitmqctl change_password histovis <new-password>`
directly, or wipe the `rabbitmq_data` volume and let it re-initialize.

## 4. Manual step: HTTPS domain routing (Coolify doesn't automate this)

Coolify's reverse proxy (Traefik) only auto-connects to networks belonging to
resources Coolify itself created and tracks in its own database — it does **not**
auto-connect to the shared `histovis-network` these compose files declare, since
that network isn't a Coolify-managed resource. This means Traefik labels baked
directly into the compose file would silently not route (Coolify's proxy simply
wouldn't have network access to the container), so this step has to be done
through Coolify's own domain UI instead, which handles that network wiring for
you automatically.

For each of the following services, in Coolify: open the service → **Domains**
→ **Add domain** → set Protocol `https`, Domain to the value below (using your
actual `PUBLIC_DOMAIN`), Port as listed, leave Path blank → Save → redeploy that
app so Traefik picks up the new routing labels and requests a free Let's Encrypt
certificate automatically.

| App | Service | Domain | Port |
|---|---|---|---|
| histovis-monorepo | user-service | `users.PUBLIC_DOMAIN` | 8085 |
| histovis-monorepo | images-service | `images.PUBLIC_DOMAIN` | 8086 |
| histovis-monorepo | analysis-service | `analysis.PUBLIC_DOMAIN` | 8087 |
| histovis-monorepo | minio | `storage.PUBLIC_DOMAIN` | 9000 |
| histovis-workers | consumer-tileserver | `tiles.PUBLIC_DOMAIN` | 8002 |

You'll also need DNS **A records** for each of those five subdomains pointing at
the server's IP address, created wherever `PUBLIC_DOMAIN`'s nameservers are
managed, before Traefik can successfully complete the Let's Encrypt HTTP-01
challenge for each one.

If a certificate doesn't appear to issue after redeploying: it's most commonly
either (a) DNS not propagated yet for that subdomain, or (b) the target service
container is unhealthy — Traefik silently skips routing/cert-requesting for any
container Docker reports as unhealthy. Check the service's own health status in
Coolify first.

## 5. Memory notes (only relevant if you enable the Qwen3-VL vision model)

`consumer-qwen` defaults to Qwen3-VL-2B-Instruct (Q4_K_M quantization + Q8_0
mmproj), which reserves ~448MB of RAM just for its KV cache (`n_ctx=4096` in
`consumer-qwen/model_loader.py`) on top of ~1.5GB of model weights — roughly
2.7GB total for that one container once warmed up. On a memory-constrained VM,
consider adding swap as a safety margin:

```bash
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf
sysctl -p /etc/sysctl.d/99-swappiness.conf
```

Also worth periodically reclaiming disk space used by old Docker image layers
and build cache (grows fast with repeated redeploys) — either via Coolify's own
**Server → Cleanup** action, or manually: `docker builder prune -af && docker image prune -af`.

## 6. About the `.yml` → `.yaml` migration

Both repos still have their original `docker-compose.yml` (no baked-in
defaults, relies on a real `.env` file, was hand-patched directly on the
existing production server over time rather than in git) alongside the new
`docker-compose.yaml` described here. The `.yml` files are being kept
temporarily since they're what's actually running in production right now —
once the `.yaml` files have been validated on a real deployment, the `.yml`
ones should be removed to avoid the two drifting apart or Coolify picking up
the wrong one by accident.
