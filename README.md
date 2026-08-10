# Toy Multimodal Platform

A production-oriented reference platform with one FastAPI gateway and three independently deployable inference services:

- **Text:** Qwen/Qwen2.5-1.5B-Instruct
- **Vision:** HuggingFaceTB/SmolVLM-500M-Instruct
- **Audio:** openai/whisper-tiny

The platform is intentionally small, but the delivery path is production-shaped:

- FastAPI gateway
- Separate model services
- Docker multi-stage builds
- Non-root containers
- Health/readiness endpoints
- Pydantic request validation
- Structured JSON logging
- Unit/integration tests
- Ruff + mypy + Bandit
- GitHub Actions CI
- Container image scanning with Trivy
- GHCR image publishing
- Kubernetes deployment
- Rolling updates
- Resource requests/limits
- Secret/config separation
- NetworkPolicy
- HPA
- PodDisruptionBudget
- Kubernetes probes

## Architecture

```text
                         Internet / Client
                                |
                                v
                      +-------------------+
                      | FastAPI Gateway   |
                      | /v1/text          |
                      | /v1/vision        |
                      | /v1/audio         |
                      +---------+---------+
                                |
              +-----------------+-----------------+
              |                 |                 |
              v                 v                 v
       +-------------+   +-------------+   +-------------+
       | text-service|   |vision-service|  |audio-service|
       | Qwen 1.5B   |   | SmolVLM     |   | Whisper tiny|
       +-------------+   +-------------+   +-------------+
```

## Repository

```text
.
├── .github/workflows/ci-cd.yml
├── gateway/
├── services/
│   ├── text/
│   ├── vision/
│   └── audio/
├── deploy/k8s/
├── tests/
├── Dockerfile.gateway
├── docker-compose.yml
├── Makefile
└── pyproject.toml
```

## Local development

Requirements:

- Docker
- Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Gateway:

```text
http://localhost:8000
```

Health:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

Text:

```bash
curl -X POST http://localhost:8000/v1/text \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain attention in one paragraph.","max_new_tokens":128}'
```

Vision:

```bash
curl -X POST http://localhost:8000/v1/vision \
  -F "file=@image.jpg" \
  -F "prompt=Describe this image."
```

Audio:

```bash
curl -X POST http://localhost:8000/v1/audio \
  -F "file=@audio.wav"
```

## CI/CD flow

Every pull request:

1. Ruff format check
2. Ruff lint
3. mypy
4. Bandit
5. pytest
6. Docker builds
7. Trivy filesystem/image security checks

Every push to `main`:

1. Run all CI checks
2. Build immutable Docker images
3. Tag images with Git SHA
4. Push to GitHub Container Registry
5. Deploy manifests to Kubernetes
6. Wait for rollout
7. Fail the deployment if rollout fails

The deployment uses the Git SHA rather than `latest`, so rollback is deterministic.

## Required GitHub secrets

For Kubernetes deployment:

- `KUBE_CONFIG_B64` — base64 encoded kubeconfig

For a private GHCR registry, configure the cluster's `imagePullSecrets`.

## Production hardening before real traffic

This repository is production-shaped, not production-complete. Before exposing it to untrusted Internet traffic, add:

- API authentication/authorization
- TLS termination
- rate limiting
- request quotas
- distributed tracing
- metrics backend
- centralized log aggregation
- model artifact/cache strategy
- GPU scheduling
- persistent model cache
- image signing/verification
- admission policies
- external secrets manager
- network egress policy
- backup/DR strategy
- load testing
- canary/blue-green deployment
- model evaluation gates
- PII/abuse filtering
- dependency/image CVE policy
