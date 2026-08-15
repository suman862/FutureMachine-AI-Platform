For the **`toy-multimodal-platform`** you currently have in VS Code, run it in layers rather than jumping directly to Kubernetes.

### 1. Open the project

From WSL:

```bash
cd /mnt/c/Users/Administrator/morninglearn/toy-multimodal-platform
```

Verify:

```bash
ls
```

You should see:

```text
docker-compose.yml
Dockerfile.gateway
gateway/
services/
tests/
deploy/
Jenkinsfile
```

### 2. Check Docker

```bash
docker --version
docker compose version
docker info
```

If `docker info` works, Docker Desktop is accessible from WSL.

### 3. Validate the Compose configuration

Before starting anything:

```bash
docker compose config
```

If there are no errors, build:

```bash
docker compose build
```

Then start:

```bash
docker compose up
```

Or run in the background:

```bash
docker compose up -d
```

### 4. Check containers

```bash
docker compose ps
```

You should eventually have something conceptually like:

```text
gateway
text-service
vision-service
audio-service
```

If you have already added MLflow:

```text
gateway
text-service
vision-service
audio-service
mlflow
postgres
minio
```

### 5. Test the gateway

First inspect the gateway API:

```text
http://localhost:8000/docs
```

FastAPI's Swagger UI should appear.

Also try:

```bash
curl http://localhost:8000/health
```

or, depending on the routes in your current code:

```bash
curl http://localhost:8000/health/live
```

### 6. Test individual services

Check the routes actually defined in:

```text
services/text/app.py
services/vision/app.py
services/audio/app.py
```

You can also inspect the gateway automatically through:

```text
http://localhost:8000/docs
```

---

## Then run the Kubernetes version

Once Docker Compose works, **don't immediately start debugging Kubernetes**.

First verify:

```text
Client
  ↓
FastAPI
  ↓
Text/Vision/Audio
```

works locally.

Then:

```bash
kubectl version --client
```

If you're using Minikube:

```bash
minikube start
```

Check:

```bash
kubectl get nodes
```

Then deploy:

```bash
kubectl apply -k deploy/k8s
```

Check:

```bash
kubectl get pods -n multimodal
```

and:

```bash
kubectl get services -n multimodal
```

Watch the pods:

```bash
kubectl get pods -n multimodal -w
```

### Your learning sequence should be

```text
                 Your Project
                      │
                      ▼
              Docker Compose
                      │
             ┌────────┴────────┐
             ▼                 ▼
          Gateway           Services
             │
             └── Text/Vision/Audio
                      │
                   TEST
                      │
                      ▼
                 Kubernetes
                      │
                      ▼
                   Jenkins
                      │
                      ▼
                    MLflow
                      │
                      ▼
              Model lifecycle
```

**Don't start with Jenkins.** First make the application work manually. Then containerize it. Then deploy it to Kubernetes. Then automate the exact steps with Jenkins.

If you paste the output of:

```bash
docker compose config
```

I can tell you whether the **current repository is actually ready to run**, including any problems in the Compose/MLflow configuration.
