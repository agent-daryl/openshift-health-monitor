# OpenShift Health Monitor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-0399c8.svg)](https://fastapi.tiangolo.com/)
[![Tests: 24 passing](https://img.shields.io/badge/tests-24%20passing-brightgreen.svg)](tests/)
[![Prometheus](https://img.shields.io/badge/metrics-Prometheus-E6522C.svg)](/metrics)

Cluster health monitoring and intelligent analysis for OpenShift/Kubernetes. Runs automated health checks across nodes, pods, resources, and events — with optional LLM-powered correlation and recommendations.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Health Monitor API                      │
│  POST /check   GET /summary   GET /health   GET /metrics│
└──────────────┬──────────────────────────────────────────┘
               │
       ┌───────┼───────────┬───────────┐
       ▼       ▼           ▼           ▼
   Node     Pod      Resource     Event
  Checker  Checker   Checker    Checker
       │       │           │           │
       └───────┴───────┬───┴───────────┘
                       ▼
            ┌─────────────────────┐
            │  ClusterHealth      │
            │  Summary            │
            └────────┬────────────┘
                     ▼
            ┌─────────────────────┐
            │  Rule-Based         │
            │  Analyzer           │
            │  (correlations)     │
            └────────┬────────────┘
                     ▼
            ┌─────────────────────┐
            │  LLM Analyzer       │
            │  (optional insights)│
            └─────────────────────┘
```

## Features

- **4 Health Checkers**: Node health, Pod status, Resource utilization, Event analysis
- **Severity Classification**: OK, Warning, Critical, Info — with configurable thresholds
- **Rule-Based Correlation**: Detects patterns across checkers (crash loops, resource pressure, cascading failures)
- **Optional LLM Analysis**: Intelligent root-cause suggestions via OpenAI-compatible endpoint
- **Prometheus Metrics**: `/metrics` endpoint for Grafana integration
- **OpenShift-Ready**: Full RBAC manifests, ServiceAccount, Routes, SCC support
- **Configurable Thresholds**: All thresholds via environment variables

## Quick Start

### Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -v
```

### API Server

```bash
# With OpenShift cluster access (via oc CLI)
uvicorn src.serving:app --host 0.0.0.0 --port 8080

# With LLM analysis enabled
LLM_ENABLED=true LLM_API_BASE=http://your-llm:8000/v1 \
  uvicorn src.serving:app --host 0.0.0.0 --port 8080
```

### Docker

```bash
docker build -t openshift-health-monitor .
docker run -p 8080:8080 \
  -v $HOME/.kube:/root/.kube:ro \
  openshift-health-monitor
```

### OpenShift Deployment

```bash
# Apply RBAC first
oc apply -f manifests/namespace.yaml
oc apply -f manifests/rbac.yaml

# Deploy application
oc apply -f manifests/deployment.yaml
oc apply -f manifests/service.yaml

# Grant SCC (OpenShift-specific)
oc adm policy add-scc-to-user anyuid -z health-monitor -n openshift-health-monitor
```

## API Reference

### `POST /check`

Run all health checks with optional LLM analysis.

```bash
curl -X POST http://localhost:8080/check
curl -X POST http://localhost:8080/check?use_llm=true
```

Response:
```json
{
  "overall_status": "warning",
  "total_checks": 4,
  "total_findings": 12,
  "counts": { "ok": 8, "warning": 3, "critical": 0, "info": 1 },
  "top_issues": [
    {
      "severity": "warning",
      "resource_type": "Pod",
      "resource_name": "web-abc123",
      "namespace": "production",
      "message": "Pod web-abc123 has 12 restarts",
      "recommendation": "oc logs web-abc123 -n production"
    }
  ],
  "check_results": [...],
  "llm_insight": null,
  "duration_ms": 245.3
}
```

### `GET /summary`

Quick health overview.

```bash
curl http://localhost:8080/summary
```

### `GET /health`

Liveness/readiness probe.

### `GET /metrics`

Prometheus-format metrics for Grafana.

### `GET /config`

Current configuration and thresholds.

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `KUBECONFIG` | — | Path to kubeconfig |
| `OC_ENDPOINT` | — | OpenShift API server URL |
| `OC_TOKEN` | — | Service account token |
| `MONITOR_NAMESPACE` | all | Specific namespace to monitor |
| `LLM_ENABLED` | `false` | Enable LLM-powered analysis |
| `LLM_API_BASE` | `http://10.10.0.20:8000/v1` | LLM endpoint |
| `LLM_MODEL` | `qwen3.6:27b_256k` | LLM model name |
| `CPU_WARNING_THRESHOLD` | `0.7` | CPU warning threshold (fraction) |
| `CPU_CRITICAL_THRESHOLD` | `0.9` | CPU critical threshold |
| `MEMORY_WARNING_THRESHOLD` | `0.8` | Memory warning threshold |
| `MEMORY_CRITICAL_THRESHOLD` | `0.95` | Memory critical threshold |
| `POD_RESTART_WARNING_THRESHOLD` | `5` | Pod restart warning count |
| `POD_RESTART_CRITICAL_THRESHOLD` | `15` | Pod restart critical count |

## Project Structure

```
openshift-health-monitor/
  src/
    config.py               # Configuration management
    models.py               # Data models (Finding, Result, Summary)
    serving.py              # FastAPI application
    checkers/
      cluster_checkers.py   # Node, Pod, Resource, Event checkers
    analyzers/
      health_analyzer.py    # Rule-based + LLM analyzers
  tests/
    test_models.py          # Model tests (12 tests)
    test_analyzer.py        # Analyzer tests (3 tests)
    test_api.py             # API integration tests (7 tests)
    test_config.py          # Config tests (3 tests)
  manifests/
    namespace.yaml          # OpenShift namespace
    rbac.yaml               # ServiceAccount, ClusterRole, ClusterRoleBinding
    deployment.yaml         # Deployment with probes
    service.yaml            # Service + Route
  Dockerfile                # Container definition
  requirements.txt          # Dependencies
```

## Exam Relevance (EX280)

This project reinforces EX280 exam concepts:
- **Node management**: `oc get nodes`, node conditions, taints/tolerations
- **Pod troubleshooting**: restart counts, CrashLoopBackOff, event analysis
- **Resource management**: quotas, limit ranges, resource utilization
- **RBAC**: ServiceAccounts, ClusterRoles, ClusterRoleBindings
- **Security**: SCCs, security contexts
- **Networking**: Routes, Services, NetworkPolicies
- **Operators**: monitoring stack integration

## Stack

- FastAPI + Uvicorn (API)
- Pydantic v2 (validation)
- OpenShift `oc` CLI (cluster access)
- Optional: llama.cpp / Ollama (LLM analysis)
- Prometheus-compatible metrics

## Author

agent-daryl (AI agent) — built for Daryl Allen's MLOps portfolio and EX280 preparation


---

> **Privacy note:** Internal IP addresses originally present in this repository have been replaced with placeholder addresses in the `10.10.0.0/16` range to protect the owner's private network topology. Compiled `__pycache__` artifacts were also removed from history.
