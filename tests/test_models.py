import pytest
import json
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models import (
    HealthFinding, HealthCheckResult, ClusterHealthSummary,
    Severity, CheckCategory
)


class TestHealthFinding:
    def test_create_finding(self):
        f = HealthFinding(
            category=CheckCategory.NODES,
            severity=Severity.CRITICAL,
            resource_type="Node",
            resource_name="worker-1",
            namespace="",
            message="Node is not ready"
        )
        assert f.severity == Severity.CRITICAL
        assert f.category == CheckCategory.NODES
        assert f.recommendation == ""
    
    def test_create_finding_with_details(self):
        f = HealthFinding(
            category=CheckCategory.PODS,
            severity=Severity.WARNING,
            resource_type="Pod",
            resource_name="web-abc",
            namespace="production",
            message="High restart count",
            details={"restarts": 10, "threshold": 5},
            recommendation="Check pod logs"
        )
        assert f.details["restarts"] == 10
        assert f.recommendation == "Check pod logs"


class TestHealthCheckResult:
    def test_healthy(self):
        findings = [
            HealthFinding(
                category=CheckCategory.NODES, severity=Severity.OK,
                resource_type="Node", resource_name="n1", namespace="",
                message="OK"
            )
        ]
        result = HealthCheckResult(
            category=CheckCategory.NODES,
            checker_name="test",
            findings=findings
        )
        assert result.is_healthy
        assert not result.has_warnings
        assert not result.has_critical
        assert result.total_findings == 1
    
    def test_has_warnings(self):
        findings = [
            HealthFinding(
                category=CheckCategory.NODES, severity=Severity.WARNING,
                resource_type="Node", resource_name="n1", namespace="",
                message="Warning"
            )
        ]
        result = HealthCheckResult(
            category=CheckCategory.NODES,
            checker_name="test",
            findings=findings
        )
        assert not result.is_healthy
        assert result.has_warnings
        assert not result.has_critical
    
    def test_has_critical(self):
        findings = [
            HealthFinding(
                category=CheckCategory.NODES, severity=Severity.CRITICAL,
                resource_type="Node", resource_name="n1", namespace="",
                message="Critical"
            )
        ]
        result = HealthCheckResult(
            category=CheckCategory.NODES,
            checker_name="test",
            findings=findings
        )
        assert not result.is_healthy
        assert not result.has_warnings
        assert result.has_critical


class TestClusterHealthSummary:
    def test_from_results_all_ok(self):
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
        summary = ClusterHealthSummary.from_results(results)
        assert summary.overall_status == Severity.OK
        assert summary.total_checks == 1
        assert summary.ok_count == 1
        assert summary.critical_count == 0
    
    def test_from_results_with_critical(self):
        results = [
            HealthCheckResult(
                category=CheckCategory.NODES,
                checker_name="nodes",
                findings=[
                    HealthFinding(
                        category=CheckCategory.NODES, severity=Severity.OK,
                        resource_type="Node", resource_name="n1", namespace="",
                        message="Ready"
                    ),
                    HealthFinding(
                        category=CheckCategory.NODES, severity=Severity.CRITICAL,
                        resource_type="Node", resource_name="n2", namespace="",
                        message="Not ready"
                    ),
                ]
            ),
            HealthCheckResult(
                category=CheckCategory.PODS,
                checker_name="pods",
                findings=[
                    HealthFinding(
                        category=CheckCategory.PODS, severity=Severity.WARNING,
                        resource_type="Pod", resource_name="p1", namespace="default",
                        message="Restarting"
                    ),
                ]
            ),
        ]
        summary = ClusterHealthSummary.from_results(results)
        assert summary.overall_status == Severity.CRITICAL
        assert summary.total_checks == 2
        assert summary.total_findings == 3
        assert summary.ok_count == 1
        assert summary.warning_count == 1
        assert summary.critical_count == 1
        assert len(summary.top_issues) == 3
    
    def test_from_results_with_warnings_only(self):
        results = [
            HealthCheckResult(
                category=CheckCategory.PODS,
                checker_name="pods",
                findings=[HealthFinding(
                    category=CheckCategory.PODS, severity=Severity.WARNING,
                    resource_type="Pod", resource_name="p1", namespace="default",
                    message="Restarting"
                )]
            )
        ]
        summary = ClusterHealthSummary.from_results(results)
        assert summary.overall_status == Severity.WARNING
    
    def test_top_issues_sorted_by_severity(self):
        results = [
            HealthCheckResult(
                category=CheckCategory.NODES,
                checker_name="nodes",
                findings=[
                    HealthFinding(
                        category=CheckCategory.NODES, severity=Severity.INFO,
                        resource_type="Event", resource_name="info1", namespace="",
                        message="Info message"
                    ),
                    HealthFinding(
                        category=CheckCategory.NODES, severity=Severity.CRITICAL,
                        resource_type="Node", resource_name="critical1", namespace="",
                        message="Critical issue"
                    ),
                    HealthFinding(
                        category=CheckCategory.NODES, severity=Severity.WARNING,
                        resource_type="Node", resource_name="warn1", namespace="",
                        message="Warning issue"
                    ),
                ]
            )
        ]
        summary = ClusterHealthSummary.from_results(results)
        assert summary.top_issues[0].severity == Severity.CRITICAL
        assert summary.top_issues[1].severity == Severity.WARNING
        assert summary.top_issues[2].severity == Severity.INFO


class TestSeverity:
    def test_severity_values(self):
        assert Severity.OK.value == "ok"
        assert Severity.WARNING.value == "warning"
        assert Severity.CRITICAL.value == "critical"
        assert Severity.INFO.value == "info"


class TestCheckCategory:
    def test_category_values(self):
        assert CheckCategory.NODES.value == "nodes"
        assert CheckCategory.PODS.value == "pods"
        assert CheckCategory.RESOURCES.value == "resources"
        assert CheckCategory.NETWORK.value == "network"
        assert CheckCategory.STORAGE.value == "storage"
        assert CheckCategory.ROUTES.value == "routes"
        assert CheckCategory.EVENTS.value == "events"
