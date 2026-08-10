# CI/CD design

## Stages

```text
PR
 |
 +--> format
 +--> lint
 +--> typecheck
 +--> security
 +--> unit tests
 +--> Docker build
 +--> Trivy scan
 |
main
 |
 +--> publish SHA-tagged images to GHCR
 |
 +--> kubectl apply
 |
 +--> rollout status
 |
 +--> smoke test
```

## Why separate model services?

Model lifecycle and scaling characteristics differ:

- text generation is token-throughput constrained;
- vision inference is image/compute constrained;
- ASR is audio-duration constrained.

Independent services let you scale, deploy, roll back, and assign hardware per modality.

## Why immutable SHA tags?

`main` is mutable; a Git SHA is not. Deploying:

```text
ghcr.io/org/model:<git-sha>
```

makes the exact artifact reproducible and makes rollback explicit.

## Where GPU scheduling belongs

For GPU deployment, add:

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

and use an NVIDIA GPU node pool/device plugin. Do not simply add GPU requests to every service: route each model to hardware based on profiling.

## Important production boundary

The gateway currently has no authentication or rate limiting. It is suitable as an engineering reference and internal platform skeleton, but an Internet-facing deployment needs an API gateway/identity layer and abuse controls.
