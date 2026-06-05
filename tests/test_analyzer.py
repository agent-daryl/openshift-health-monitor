import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models import HealthFinding, HealthCheckResult, Severity, CheckCategory
from src.analyzers.health_analyzer import RuleBasedAnalyzer


class TestRuleBasedAnalyzer:
    def test_no_issues(self):
        results = [
            HealthCheckResult(
                category=CheckCategory.NODES,
                checker_name="nodes",
                findings=[HealthFinding(
                    category=CheckCategory.NODES, severity=Severity.OK,
                    resource_type="Node", resource_name="n1", namespace="",
                    message="Ready"
                )]
            )
        ]
        from src.models import ClusterHealthSummary
        summary = ClusterHealthSummary.from_results(results)
        analyzer = RuleBasedAnalyzer()
        insights = analyzer.analyze(summary)
        assert len(insights) == 0
    
    def test_crash_loop_pattern(self):
        findings = []
        for i in range(5):
            findings.append(HealthFinding(
                category=CheckCategory.PODS, severity=Severity.WARNING,
                resource_type="Pod", resource_name=f"web-{i}", namespace="default",
                message=f"Pod web-{i} has 10 restarts (warning threshold: 5)"
            ))
        results = [HealthCheckResult(
            category=CheckCategory.PODS, checker_name="pods", findings=findings
        )]
        from src.models import ClusterHealthSummary
        summary = ClusterHealthSummary.from_results(results)
        analyzer = RuleBasedAnalyzer()
        insights = analyzer.analyze(summary)
        
        crash_insights = [i for i in insights if "crash" in i.message.lower() or "restart" in i.message.lower()]
        assert len(crash_insights) >= 1
    
    def test_resource_pressure_pattern(self):
        findings = [
            HealthFinding(
                category=CheckCategory.RESOURCES, severity=Severity.WARNING,
                resource_type="Node", resource_name="node-1", namespace="",
                message="Node node-1 CPU at 85%"
            ),
            HealthFinding(
                category=CheckCategory.RESOURCES, severity=Severity.WARNING,
                resource_type="Node", resource_name="node-2", namespace="",
                message="Node node-2 CPU at 78%"
            ),
        ]
        results = [HealthCheckResult(
            category=CheckCategory.RESOURCES, checker_name="resources", findings=findings
        )]
        from src.models import ClusterHealthSummary
        summary = ClusterHealthSummary.from_results(results)
        analyzer = RuleBasedAnalyzer()
        insights = analyzer.analyze(summary)
        
        pressure_insights = [i for i in insights if "resource" in i.message.lower()]
        assert len(pressure_insights) >= 1
