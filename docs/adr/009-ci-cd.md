# ADR-009: GitHub Actions with a self-hosted deploy runner

**Status:** Accepted · **Use cases:** all

## Context

The project needs a CI/CD pipeline with automated tests, builds, deployment and reproducible experiments. Our cluster runs locally, so GitHub's own runners cannot reach it.

## Decision

- **Pull requests** run on GitHub-hosted runners: lint, unit tests, a short **replay test** on a kind cluster created inside the job, and image builds.
- **Merge to `main`** pushes images tagged with the commit hash to GitHub Container Registry.
- A **self-hosted runner** on the machine that runs our cluster then applies the Kubernetes manifests and runs a smoke test. Only `main` may use this runner, so code from pull requests never reaches our machine.
- Replay data, model versions and configuration are pinned in the repository, so experiments can be repeated.

## Alternatives

| Option | Why not |
| --- | --- |
| Argo CD (GitOps) | Nice for continuous syncing, but another system to install and learn. |
| Jenkins or GitLab CI | Our code is on GitHub already. |
| Deploy by hand | Not reproducible and not a CI/CD pipeline. |

## Consequences

- ✅ Every change is tested on a real (small) Kubernetes cluster before merging.
- ✅ Deployments are traceable to a commit.
- ❌ The self-hosted runner must be kept running and isolated.
- ❌ Spinning up kind in every pull request takes a few minutes.

## Sustainability

The replay test uses a short clip of data and only the lightest profile, so CI runs stay short. We do not run the full pipeline on every push to a branch, only on pull requests and `main`.
