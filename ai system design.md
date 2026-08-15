Yes. For your **multimodal AI platform with text, vision, and audio inference**, the questions should move beyond *“does FastAPI work?”* and test whether you can **design, operate, scale, and defend production decisions**.

I would use the following as a **production AI-system-design interview/research checklist**.

---

# 1. Requirements and system boundaries

### Question 1 — Define the system

You have:

```text
                    Clients
                       │
                       ▼
                 API Gateway
              ┌────────┼────────┐
              ▼        ▼        ▼
            Text     Vision    Audio
            Model     Model     Model
```

Before choosing FastAPI, Docker, Kubernetes, or MLflow:

**What are the functional and non-functional requirements of this platform?**

Explicitly define:

* request types
* expected modalities
* synchronous vs asynchronous inference
* maximum payload sizes
* target P50/P95/P99 latency
* throughput
* availability target
* GPU/CPU requirements
* model quality requirements
* cost constraints
* security requirements
* data-retention requirements

**Production principle:** architecture follows requirements, not technology preferences.

---

# 2. Why microservices?

Your platform separates:

```text
gateway
text-service
vision-service
audio-service
```

### Question 2

**Why should these be separate services rather than one multimodal inference server?**

Give quantitative arguments involving:

* independent scaling
* failure isolation
* deployment independence
* dependency conflicts
* GPU memory
* model loading time
* utilization
* release velocity

Then answer the harder question:

> **At what scale would microservices become a liability rather than an advantage?**

---

# 3. Gateway design

Your gateway currently routes requests to different model services.

### Question 3

Design the gateway as a production inference gateway.

Where should you implement:

```text
authentication
authorization
rate limiting
request validation
routing
timeouts
retries
circuit breakers
request IDs
logging
metrics
response normalization
```

Which belong in the gateway and which should **not**?

---

# 4. Synchronous vs asynchronous inference

Text inference may take milliseconds/seconds.

Vision may process large images.

Audio may involve:

```text
upload
→ decoding
→ preprocessing
→ transcription
→ postprocessing
```

### Question 4

**Should all three modalities use synchronous HTTP inference?**

Design an alternative:

```text
Client
  ↓
Gateway
  ↓
Job Queue
  ↓
Worker
  ↓
Model
  ↓
Object Storage
  ↓
Result
```

When would you use:

* synchronous HTTP?
* WebSocket?
* Server-Sent Events?
* message queue?
* polling?
* asynchronous job API?

---

# 5. Model loading

Suppose the vision model requires 8 GB GPU memory.

### Question 5

Should the service load the model:

```text
per request
```

or:

```text
once when the container starts
```

What happens to:

* latency?
* GPU memory?
* concurrency?
* startup time?
* autoscaling?
* model initialization failures?

Design the lifecycle:

```text
Container starts
      ↓
Load configuration
      ↓
Load model
      ↓
Warm model
      ↓
Readiness = true
      ↓
Accept traffic
```

---

# 6. Readiness vs liveness

Suppose:

```text
Pod starts
   ↓
model loading takes 40 seconds
```

but Kubernetes immediately sends traffic.

### Question 6

What should happen?

Design:

```text
liveness probe
readiness probe
startup probe
```

and explain the difference between:

> "The process is alive"

and:

> "The service is capable of serving inference."

This distinction is critical for production model serving.

---

# 7. Failure isolation

Suppose the vision model crashes because GPU memory is exhausted.

### Question 7

Should:

```text
vision-service
```

take down:

```text
gateway
text-service
audio-service
```

How does your architecture prevent cascading failure?

Discuss:

* process isolation
* container isolation
* Kubernetes
* resource limits
* timeouts
* circuit breakers
* bulkheads
* queue isolation

---

# 8. Timeout design

Your gateway has:

```text
HTTP_TIMEOUT_SECONDS = 120
```

### Question 8

**Why 120 seconds?**

What is wrong with:

```text
timeout = 120
```

as a universal timeout?

Design different policies for:

```text
text
vision
audio
```

Consider:

[
T_{timeout} > T_{preprocess}+T_{queue}+T_{inference}+T_{postprocess}
]

but also consider what happens when requests occupy workers for two minutes.

---

# 9. Retry design

### Question 9

Should the gateway automatically retry a failed model request?

Consider:

```text
request
   ↓
vision-service
   ↓
inference succeeds
   ↓
network failure while returning response
```

The gateway sees failure.

If it retries, what happens?

Could you accidentally perform inference twice?

Discuss:

* idempotency
* retryable errors
* exponential backoff
* retry budgets
* request IDs
* duplicate work

---

# 10. GPU scheduling

Now assume:

```text
Text    → GPU
Vision  → GPU
Audio   → GPU
```

You have **one GPU**.

### Question 10

How would you prevent:

```text
vision-service
```

from consuming the entire GPU and starving the other services?

Design:

```text
GPU allocation
GPU memory limits
concurrency limits
request queues
batching
priority
```

Then redesign it for:

```text
4 GPUs
```

and explain whether you would use:

```text
one model per GPU
```

or:

```text
multiple models per GPU
```

and why.

---

# 11. Dynamic batching

Suppose you receive:

```text
100 text requests/second
```

### Question 11

Should every request trigger one GPU inference?

Compare:

```text
request → inference
request → inference
request → inference
```

with:

```text
requests
   ↓
batch queue
   ↓
dynamic batching
   ↓
GPU
```

Analyze the tradeoff between:

[
\text{throughput}
\leftrightarrow
\text{latency}
]

How would you choose:

* maximum batch size?
* maximum batching delay?
* queue timeout?

---

# 12. Model versioning

Suppose:

```text
Qwen-v1
```

is currently serving production.

You want:

```text
Qwen-v2
```

### Question 12

How do you deploy v2 without taking production offline?

Design:

```text
v1 ──────────────── production
v2 ── testing
```

then:

```text
v1 90%
v2 10%
```

and eventually:

```text
v2 100%
```

What happens if v2's latency or quality becomes unacceptable?

Design:

**canary deployment + rollback.**

---

# 13. Model quality is part of production reliability

A model can be operationally healthy but scientifically broken.

Suppose:

```text
HTTP 200
latency = 100 ms
CPU = 30%
GPU = 50%
```

but model accuracy dropped from:

```text
92% → 71%
```

### Question 13

**Is the system healthy?**

Design a production evaluation pipeline that detects:

* accuracy regression
* hallucination regression
* segmentation quality regression
* transcription quality regression
* safety regression

This is where **ML evaluation meets DevOps**.

---

# 14. MLflow's actual role

You previously asked whether MLflow was missing from this platform.

Now answer this:

### Question 14

Where exactly should MLflow sit?

Should it manage:

```text
Docker images?
model artifacts?
experiments?
metrics?
model versions?
deployment state?
```

Design:

```text
Training/Evaluation
       ↓
     MLflow
       ↓
 Model Registry
       ↓
Approved Model
       ↓
CI/CD
       ↓
Deployment
```

Then explain why **Docker image versioning and model versioning are different problems**.

---

# 15. Model registry vs container registry

Suppose:

```text
Docker image:
vision-service:1.7
```

contains:

```text
SmolVLM
```

### Question 15

Why isn't Docker/GHCR sufficient as your model registry?

Compare:

```text
Container Registry
        vs
Model Registry
```

in terms of:

* model artifacts
* metrics
* lineage
* experiment metadata
* model stages
* evaluation
* reproducibility

---

# 16. Observability

A user reports:

> "Vision inference became slow."

### Question 16

What metrics do you need to diagnose the problem?

Design observability across:

```text
Gateway
   ↓
Network
   ↓
Vision service
   ↓
Preprocessing
   ↓
GPU queue
   ↓
Model inference
   ↓
Postprocessing
```

Measure:

* request rate
* error rate
* P50
* P95
* P99
* queue latency
* preprocessing latency
* inference latency
* GPU utilization
* GPU memory
* CPU
* RAM
* batch size
* tokens/sec

---

# 17. Distributed tracing

Suppose one request generates:

```text
Gateway
   ↓
Vision
   ↓
Model
```

### Question 17

How do you determine whether the 5-second latency came from:

```text
gateway = 50 ms
network = 20 ms
preprocessing = 1 sec
queue = 2 sec
GPU inference = 1.9 sec
```

Design distributed tracing.

What identifier should travel through the entire request?

---

# 18. Rate limiting

Imagine one client sends:

```text
10,000 image requests/second
```

### Question 18

What prevents that client from destroying your service?

Design rate limiting at:

```text
user level
API-key level
IP level
model level
GPU level
```

Should text and vision have the same rate limit?

Why or why not?

---

# 19. Backpressure

Suppose:

```text
Incoming:
1,000 requests/sec

GPU capacity:
100 requests/sec
```

### Question 19

What should happen to the other 900 requests?

Possible strategies:

```text
queue
reject
429
503
shed low-priority traffic
```

Design a backpressure mechanism.

This is one of the most important production principles for inference systems.

---

# 20. Autoscaling

### Question 20

What metric should trigger scaling?

Is this sufficient?

```text
CPU > 70%
```

Probably not for GPU inference.

Compare:

```text
CPU utilization
GPU utilization
request rate
queue depth
P95 latency
in-flight requests
```

Then design an autoscaling policy.

---

# 21. Cold starts

Suppose a new vision pod takes:

```text
45 seconds
```

to download/load the model.

### Question 21

What happens when Kubernetes scales from:

```text
2 → 4 replicas
```

during a traffic spike?

How would you reduce the cold-start impact?

Consider:

* persistent model cache
* pre-pulled images
* warm replicas
* model storage
* startup probes
* minimum replicas
* model initialization optimization

---

# 22. Storage architecture

Your current system has:

```text
hf-cache:/models/cache
```

### Question 22

Is a Docker named volume sufficient for a production multi-node Kubernetes deployment?

What happens when:

```text
Pod A
```

runs on:

```text
Node 1
```

and gets rescheduled to:

```text
Node 2
```

Where is the model cache?

Now design:

```text
Object Storage
      ↓
Model Artifact
      ↓
Node-local cache
      ↓
GPU inference
```

---

# 23. Security

Your API is exposed publicly.

### Question 23

How do you secure:

```text
POST /text
POST /vision
POST /audio
```

Design:

```text
TLS
authentication
authorization
API keys/JWT
rate limiting
payload validation
file-type validation
maximum upload size
sandboxing
secret management
network policies
```

Then ask:

> Why should the model services themselves not necessarily be publicly accessible?

---

# 24. Image/audio input security

Vision and audio accept potentially untrusted files.

### Question 24

What happens if a user uploads:

```text
10 GB image
corrupted JPEG
malicious file
20-hour audio
zip bomb
```

How do you protect:

```text
memory
CPU
GPU
disk
processing time
```

Design input validation and resource controls.

---

# 25. Graceful degradation

Suppose:

```text
Vision service = DOWN
```

but:

```text
Text = healthy
Audio = healthy
```

### Question 25

Should the entire API return:

```text
503 Service Unavailable
```

or should:

```text
/text → works
/audio → works
/vision → 503
```

Design the failure semantics.

---

# 26. Deployment strategy

You have:

```text
GitHub
   ↓
Jenkins
   ↓
Docker
   ↓
GHCR
   ↓
Kubernetes
```

### Question 26

Design the complete production CI/CD pipeline:

```text
commit
 ↓
lint
 ↓
unit tests
 ↓
integration tests
 ↓
security scanning
 ↓
build image
 ↓
image scanning
 ↓
push registry
 ↓
model evaluation gate
 ↓
deploy staging
 ↓
smoke tests
 ↓
canary
 ↓
production
 ↓
monitor
 ↓
rollback
```

Which steps must happen **before production deployment**, and which can happen asynchronously?

---

# 27. Rollback

Suppose deployment v2 causes:

```text
P95 latency +80%
```

### Question 27

How does your system automatically detect the regression?

How does it rollback?

What exactly gets rolled back?

```text
Docker image?
Kubernetes Deployment?
Model version?
Configuration?
Everything?
```

This is a deceptively important question.

---

# 28. Cost engineering

Suppose:

```text
Vision GPU utilization = 15%
Audio GPU utilization = 20%
Text GPU utilization = 90%
```

### Question 28

Would you simply add more GPUs?

Or would you first investigate:

* batching
* quantization
* concurrency
* model size
* request routing
* GPU sharing
* CPU inference
* caching

Design a cost-per-request metric:

[
C_{\text{request}}
==================

\frac{C_{\text{GPU}}+C_{\text{CPU}}+C_{\text{storage}}+C_{\text{network}}}
{\text{successful requests}}
]

---

# 29. Capacity planning

Suppose you expect:

```text
10M requests/month
```

with:

```text
40% text
35% vision
25% audio
```

### Question 29

How many replicas and GPUs do you need?

Don't guess.

Define:

[
\lambda = \text{arrival rate}
]

[
\mu = \text{service rate}
]

and reason about:

```text
capacity
utilization
queueing
headroom
```

Then design a load-testing experiment to validate the theoretical estimate.

---

# 30. The ultimate architecture question

Now forget the existing implementation.

You are told:

> **Build a production multimodal inference platform serving text, vision, and audio models to 100,000 users, with 99.9% availability, P95 latency below 2 seconds, automatic model rollout/rollback, GPU-aware autoscaling, model evaluation gates, and complete observability.**

Design the architecture from scratch.

You must specify:

```text
                    ┌───────────────┐
                    │    Clients    │
                    └───────┬───────┘
                            │
                     CDN / WAF / LB
                            │
                            ▼
                    ┌───────────────┐
                    │ API Gateway   │
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
           Text API      Vision API     Audio API
              │             │             │
              ▼             ▼             ▼
           Queue/        Queue/        Queue/
           Batcher       Batcher       Batcher
              │             │             │
              ▼             ▼             ▼
            GPU           GPU           GPU
            pool          pool          pool
              │             │             │
              └─────────────┼─────────────┘
                            │
                     Observability
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
           Metrics        Logs          Traces
                            
                     Model Lifecycle
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
          Evaluation      MLflow       Registry
              │             │             │
              └─────────────┼─────────────┘
                            ▼
                          CI/CD
```

Then defend **every box and every arrow**.

That is the level at which this project stops being merely:

> **"I built a FastAPI + Docker + Kubernetes project."**

and becomes:

> **"I designed an AI inference platform and can reason about its reliability, scalability, model lifecycle, GPU economics, and failure modes."**

For your learning, I would **not answer all 30 at once**. Treat them as progressively harder system-design drills: **1–10 = architecture fundamentals, 11–20 = distributed inference, 21–30 = production/SRE + ML platform engineering.**
