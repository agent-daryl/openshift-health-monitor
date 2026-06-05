from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import Config
from src.models import ClusterHealthSummary, Severity
from src.checkers.cluster_checkers import get_all_checkers
from src.analyzers.health_analyzer import RuleBasedAnalyzer, LLMAnalyzer
import time

app = FastAPI(
    title="OpenShift Health Monitor",
    description="Cluster health monitoring and intelligent analysis for OpenShift/Kubernetes",
    version="0.1.0"
)

rule_analyzer = RuleBasedAnalyzer()
llm_analyzer = LLMAnalyzer()


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "openshift-health-monitor"}


@app.get("/config")
def get_config():
    return {
        "llm_enabled": Config.LLM_ENABLED,
        "namespace": Config.NAMESPACE or "all namespaces",
        "thresholds": {
            "cpu_warning": Config.CPU_WARNING_THRESHOLD,
            "cpu_critical": Config.CPU_CRITICAL_THRESHOLD,
            "memory_warning": Config.MEMORY_WARNING_THRESHOLD,
            "memory_critical": Config.MEMORY_CRITICAL_THRESHOLD,
            "pod_restart_warning": Config.POD_RESTART_WARNING_THRESHOLD,
            "pod_restart_critical": Config.POD_RESTART_CRITICAL_THRESHOLD,
        }
    }


@app.post("/check")
def run_checks(use_llm: Optional[bool] = False):
    """Run all health checks and return results."""
    start = time.time()
    checkers = get_all_checkers()
    results = []
    
    for checker in checkers:
        result = checker.run()
        results.append(result)
    
    summary = ClusterHealthSummary.from_results(results)
    
    # Add rule-based correlations
    correlations = rule_analyzer.analyze(summary)
    for c in correlations:
        summary.top_issues.append(c)
    
    # Add LLM analysis if enabled
    llm_insight = None
    if use_llm and Config.LLM_ENABLED:
        llm_insight = llm_analyzer.analyze(summary)
    
    duration_ms = (time.time() - start) * 1000
    
    return JSONResponse(content={
        "overall_status": summary.overall_status.value,
        "total_checks": summary.total_checks,
        "total_findings": summary.total_findings,
        "counts": {
            "ok": summary.ok_count,
            "warning": summary.warning_count,
            "critical": summary.critical_count,
            "info": summary.info_count
        },
        "top_issues": [
            {
                "severity": f.severity.value,
                "resource_type": f.resource_type,
                "resource_name": f.resource_name,
                "namespace": f.namespace,
                "message": f.message,
                "recommendation": f.recommendation,
                "details": f.details,
            }
            for f in summary.top_issues
        ],
        "check_results": [
            {
                "checker": r.checker_name,
                "category": r.category.value,
                "duration_ms": round(r.duration_ms, 1),
                "is_healthy": r.is_healthy,
                "total_findings": r.total_findings,
                "error": r.error,
                "findings": [
                    {
                        "severity": f.severity.value,
                        "resource_type": f.resource_type,
                        "resource_name": f.resource_name,
                        "namespace": f.namespace,
                        "message": f.message,
                        "recommendation": f.recommendation,
                    }
                    for f in r.findings
                ]
            }
            for r in results
        ],
        "llm_insight": llm_insight,
        "duration_ms": round(duration_ms, 1),
        "timestamp": summary.timestamp,
    })


@app.get("/summary")
def get_summary():
    """Quick summary endpoint — runs checks and returns only high-level status."""
    checkers = get_all_checkers()
    results = [checker.run() for checker in checkers]
    summary = ClusterHealthSummary.from_results(results)
    
    return {
        "overall_status": summary.overall_status.value,
        "checks_run": summary.total_checks,
        "critical": summary.critical_count,
        "warnings": summary.warning_count,
        "info": summary.info_count,
        "top_issue": summary.top_issues[0].message if summary.top_issues else "All clear",
    }


@app.get("/metrics")
def get_metrics():
    """Prometheus-style metrics endpoint."""
    checkers = get_all_checkers()
    results = [checker.run() for checker in checkers]
    summary = ClusterHealthSummary.from_results(results)
    
    lines = [
        "# HELP openshift_health_status Overall cluster health status (0=ok, 1=warning, 2=critical)",
        "# TYPE openshift_health_status gauge",
        f'openshift_health_status{{status="{summary.overall_status.value}"}} '
        f'{"2" if summary.overall_status == Severity.CRITICAL else "1" if summary.overall_status == Severity.WARNING else "0"}',
        "# HELP openshift_health_checks_total Total number of checks run",
        "# TYPE openshift_health_checks_total gauge",
        f"openshift_health_checks_total {summary.total_checks}",
        "# HELP openshift_health_findings_total Total findings by severity",
        "# TYPE openshift_health_findings_total gauge",
        f'openshift_health_findings_total{{severity="ok"}} {summary.ok_count}',
        f'openshift_health_findings_total{{severity="warning"}} {summary.warning_count}',
        f'openshift_health_findings_total{{severity="critical"}} {summary.critical_count}',
        f'openshift_health_findings_total{{severity="info"}} {summary.info_count}',
    ]
    
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines) + "\n")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.HOST, port=Config.PORT)
