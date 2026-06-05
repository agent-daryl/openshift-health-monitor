from typing import Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.config import Config
from src.models import ClusterHealthSummary, HealthFinding, Severity
import json


class RuleBasedAnalyzer:
    """Deterministic analyzer that correlates findings and provides recommendations."""
    
    def analyze(self, summary: ClusterHealthSummary) -> list[HealthFinding]:
        insights = []
        
        # Correlate node issues with pod issues
        node_critical = [f for f in summary.top_issues if f.resource_type == "Node" and f.severity == Severity.CRITICAL]
        pod_critical = [f for f in summary.top_issues if f.resource_type == "Pod" and f.severity == Severity.CRITICAL]
        
        if node_critical and pod_critical:
            insights.append(HealthFinding(
                category="analysis" if hasattr(__import__('..models', fromlist=['CheckCategory']), 'CheckCategory') else "analysis",
                severity=Severity.WARNING,
                resource_type="Correlation",
                resource_name="node-pod",
                namespace="",
                message="Node failures may be causing pod failures. Investigate node health first.",
                recommendation="Fix node issues before addressing pod issues."
            ))
        
        # Crash loop detection
        crash_loops = [f for f in summary.top_issues if "restart" in f.message.lower() and f.severity != Severity.OK]
        if len(crash_loops) >= 3:
            insights.append(HealthFinding(
                category="analysis",
                severity=Severity.WARNING,
                resource_type="Pattern",
                resource_name="widespread_crashes",
                namespace="",
                message=f"{len(crash_loops)} pods experiencing high restart counts — possible cluster-wide issue",
                recommendation="Check for recent config changes, resource pressure, or image pull failures."
            ))
        
        # Resource pressure across multiple nodes
        resource_warnings = [f for f in summary.top_issues if f.resource_type == "Node" and 
                           ("CPU at" in f.message or "Memory at" in f.message)]
        if len(resource_warnings) >= 2:
            insights.append(HealthFinding(
                category="analysis",
                severity=Severity.WARNING,
                resource_type="Pattern",
                resource_name="resource_pressure",
                namespace="",
                message="Multiple nodes under resource pressure — consider scaling the cluster",
                recommendation="Review resource quotas and consider adding worker nodes."
            ))
        
        return insights


class LLMAnalyzer:
    """Optional LLM-powered analyzer for deeper insights."""
    
    def __init__(self):
        self.enabled = Config.LLM_ENABLED
    
    def analyze(self, summary: ClusterHealthSummary) -> Optional[str]:
        if not self.enabled:
            return None
        
        findings_text = "\n".join(
            f"- [{f.severity.value.upper()}] {f.resource_type}/{f.resource_name} in {f.namespace}: {f.message}"
            for f in summary.top_issues
        )
        
        prompt = f"""You are an OpenShift cluster health analyzer. Given these findings, provide a concise summary and prioritized recommendations.

Cluster Health: {summary.overall_status.value.upper()}
Checks: {summary.total_checks} | Findings: {summary.total_findings} (OK: {summary.ok_count}, Warning: {summary.warning_count}, Critical: {summary.critical_count})

Top Issues:
{findings_text}

Provide:
1. One-sentence overall assessment
2. Top 3 priorities to address (if any)
3. Specific commands to investigate each priority

Keep it under 200 words. Be specific with oc commands."""
        
        return self._call_llm(prompt)
    
    def _call_llm(self, prompt: str) -> Optional[str]:
        try:
            import httpx
            response = httpx.post(
                f"{Config.LLM_API_BASE}/chat/completions",
                json={
                    "model": Config.LLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 512
                },
                headers={"Authorization": f"Bearer {Config.LLM_API_KEY}"},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            return None
