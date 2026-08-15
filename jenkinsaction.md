Here's a concrete, ordered action plan — each item has the fix, a code sketch, and where to actually learn the concept behind it (not just copy-paste).

---

## Action 1: Add a model evaluation gate (highest priority)

**Where:** New stage between `Container Security Scan` and `Push Images`.

**What it does:** Runs a small labeled eval set against each newly built model container (or the model artifact itself), compares metrics against the currently-deployed baseline, fails the build if quality regresses.

```groovy
stage('Model Evaluation Gate') {
    when { branch 'main' }
    steps {
        sh '''
            . .venv/bin/activate

            python scripts/evaluate_model.py \
                --model-tag ${IMAGE_TAG} \
                --eval-set data/eval/vision_eval_set.jsonl \
                --baseline-metrics-uri mlflow://production/vision/metrics \
                --min-accuracy 0.90 \
                --max-regression-pct 2.0 \
                --output eval_report.json

            python scripts/check_eval_gate.py --report eval_report.json
        '''
    }
    post {
        always {
            archiveArtifacts artifacts: 'eval_report.json'
        }
    }
}
```

`check_eval_gate.py` just exits non-zero if metrics don't clear threshold — Jenkins stage fails naturally, pipeline stops, nothing bad reaches `Push Images`.

**Learn:**
- **MLflow docs → "Model Registry" + "Evaluate"** (mlflow.org/docs, search "mlflow.evaluate") — read the quickstart, then actually run `mlflow.evaluate()` against a toy sklearn/HF model locally. Don't skip running it — the API only makes sense once you see the metrics JSON it produces.
- **Google's "Rules of ML Engineering," Rule #37 ("measure the delta between models")** — short, free, no signup. Explains *why* gates compare to baseline, not absolute thresholds.
- Practical order: (1) get MLflow tracking a toy model locally, (2) get the registry storing two versions, (3) write a 20-line script that pulls both versions' metrics and diffs them. That script *is* your gate.

---

## Action 2: Staging environment before production

**Where:** Split `Deploy to Kubernetes` into `Deploy to Staging` → `Staging Smoke Test` → `Deploy to Production (canary)`.

```groovy
stage('Deploy to Staging') {
    when { branch 'main' }
    steps {
        sh 'kubectl apply -k deploy/k8s/overlays/staging'
    }
}
stage('Staging Smoke Test') {
    when { branch 'main' }
    steps {
        sh './scripts/smoke_test.sh staging'
    }
}
```

This requires **Kustomize overlays** (base + staging + production), not one flat `deploy/k8s` folder.

**Learn:**
- **kubernetes.io docs → "Kustomize"** (official tutorial) — do the tutorial exactly once, building a `base/` + `overlays/staging` + `overlays/production` directory yourself with a toy nginx deployment before touching your real manifests. This single exercise fixes both this gap and the `sed` problem in Action 6.

---

## Action 3: Canary rollout + automatic rollback on metrics

**Where:** Replace the plain `Deploy to Kubernetes` stage for production with a canary strategy.

This is the point where hand-rolled `kubectl apply` genuinely isn't enough — you need a controller that watches metrics and decides promote/abort. Two honest paths:

- **Simple version (no new tool):** deploy v2 as a *separate* Deployment (`vision-service-canary`) behind a Service that splits traffic via two Deployments + a weighted Ingress/Service mesh rule, then a Jenkins stage that queries Prometheus after a bake period and either scales canary to 100% or scales it to 0 and fails.
- **Real version (what production teams use):** **Argo Rollouts**. You define an `AnalysisTemplate` that queries Prometheus (e.g., p95 latency, error rate) and a `Rollout` resource replaces your `Deployment`. Argo Rollouts does the traffic-splitting and auto-abort for you.

```yaml
# Rollout (replaces Deployment) — abbreviated
spec:
  strategy:
    canary:
      steps:
        - setWeight: 10
        - pause: {duration: 5m}
        - analysis:
            templates:
              - templateName: latency-check
        - setWeight: 100
```

**Learn:**
- **Argo Rollouts official docs → "Getting Started"** (argo-rollouts.readthedocs.io) — install it on a local kind/minikube cluster, run their bundled demo app example (they have a canary demo with a synthetic metrics provider). Do this before touching your own services.
- **Prometheus docs → "Querying basics" (PromQL)** — you need this regardless, since `AnalysisTemplate` is just a PromQL query with a threshold. Learn `histogram_quantile()` for p95/p99 specifically — it's the one query you'll use constantly.

---

## Action 4: Explicit rollback in `post { failure }`

**Where:** `post` block.

```groovy
post {
    failure {
        script {
            if (env.BRANCH_NAME == 'main' && env.DEPLOY_STARTED == 'true') {
                sh '''
                    kubectl rollout undo deployment/gateway -n multimodal || true
                    kubectl rollout undo deployment/text-service -n multimodal || true
                    kubectl rollout undo deployment/vision-service -n multimodal || true
                    kubectl rollout undo deployment/audio-service -n multimodal || true
                '''
            }
        }
    }
}
```

Set `env.DEPLOY_STARTED = 'true'` as the first line of `Deploy to Kubernetes` so rollback only fires if a deploy actually began (not on a lint failure).

**Learn:**
- No new tool needed here — just read `kubectl rollout undo -h` and `kubectl rollout history deployment/X` output once on a real cluster so you understand what "rollback" actually reverts (it's the Deployment's pod template — image tag + env vars — not your Kubernetes YAML files, not your git repo, and not the model artifact unless the image tag encodes the model version). This distinction is exactly your own Question 27 — worth internalizing hands-on, not just reading.

---

## Action 5: Real smoke tests (per modality, not just `/health/live`)

```groovy
stage('Smoke Test') {
    when { branch 'main' }
    steps {
        sh '''
            kubectl run jenkins-smoke-test -n multimodal --rm -i --restart=Never \
                --image=curlimages/curl:8.15.0 -- sh -c "
                curl --fail --max-time 30 http://gateway:8000/health/live &&
                curl --fail --max-time 30 -X POST http://gateway:8000/text \
                    -H 'Content-Type: application/json' \
                    -d '{\\"prompt\\":\\"ping\\"}' &&
                curl --fail --max-time 60 -X POST http://gateway:8000/vision \
                    -F 'image=@/fixtures/tiny_test.jpg' &&
                curl --fail --max-time 60 -X POST http://gateway:8000/audio \
                    -F 'audio=@/fixtures/tiny_test.wav'
            "
        '''
    }
}
```

You'll need a small `fixtures` ConfigMap/image with tiny sample inputs mounted in.

**Learn:** No dedicated resource needed — this is just applying the "synthetic monitoring" idea from your checklist Q16/Q17 to CI. If you want vocabulary: search **"synthetic transaction monitoring"**, a term used in observability docs (Datadog/New Relic have good short explainer blog posts, free to read without account).

---

## Action 6: Kustomize instead of `sed` for image tags

Once you've done the Kustomize tutorial (Action 2), replace:

```groovy
sh "sed -i ... deploy/k8s/gateway.yaml"
```

with:

```groovy
sh '''
    cd deploy/k8s/overlays/production
    kustomize edit set image ${REGISTRY}/${IMAGE_PREFIX}-gateway=${REGISTRY}/${IMAGE_PREFIX}-gateway:${IMAGE_TAG}
    kustomize edit set image ${REGISTRY}/${IMAGE_PREFIX}-vision=${REGISTRY}/${IMAGE_PREFIX}-vision:${IMAGE_TAG}
'''
```

Same learning resource as Action 2 — this is literally one command taught in that same tutorial (`kustomize edit set image`).

---

## Action 7: Credential hygiene

**Fix:** explicitly clean the kubeconfig, don't rely only on `cleanWs()`:

```groovy
always {
    sh '''
        docker logout ${REGISTRY} || true
        rm -f ~/.kube/config || true
        rm -rf .venv || true
    '''
    cleanWs()
}
```

Also prefer **`withKubeConfig` Jenkins plugin step** over manually `cp`-ing a credential file to `~/.kube/config`, so Jenkins manages the scope/cleanup itself.

**Learn:**
- **Jenkins official docs → "Kubernetes CLI Plugin" (`withKubeConfig`)** — plugin page has a working example, five minutes to read and apply.

---

## Action 8: Dependency vulnerability scan (SCA), separate from bandit

```groovy
stage('Dependency Vulnerability Scan') {
    steps {
        sh '''
            . .venv/bin/activate
            pip-audit
        '''
    }
}
```

**Learn:** `pip-audit` GitHub README — it's short, the tool is basically self-explanatory, just add it as a stage after `Install Dependencies`.

---

## Action 9: Integration tests before build

```groovy
stage('Integration Tests') {
    steps {
        sh '''
            docker compose -f docker-compose.test.yaml up -d
            . .venv/bin/activate
            pytest tests/integration -q
            docker compose -f docker-compose.test.yaml down -v
        '''
    }
}
```

**Learn:** **testcontainers-python** docs (testcontainers-python.readthedocs.io) — lets you spin up real service containers from pytest itself rather than maintaining a separate compose file; worth the half-day to learn since it also helps with Q22's storage testing later.

---

## Suggested order to actually implement (not read — build)

1. Action 1 (eval gate) — biggest interview-defensibility gain, and forces you to touch MLflow for real.
2. Action 2 + 6 (Kustomize/staging) — foundational, everything else builds on it.
3. Action 4 (rollback) — cheap, high value, no new tool.
4. Action 5 (smoke tests) — cheap, high value.
5. Action 3 (canary/Argo Rollouts) — most time-intensive; do last since it depends on 2.
6. Actions 7–9 — polish, do whenever you have spare time between the above.

Want me to write the actual `evaluate_model.py` + `check_eval_gate.py` scripts for Action 1 next? That's the one piece with no off-the-shelf template — everything else above is closer to "apply the tutorial."