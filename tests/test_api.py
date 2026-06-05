import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from src.serving import app
from src.models import HealthCheckResult, HealthFinding, Severity, CheckCategory


client = TestClient(app)


class TestHealthEndpoint:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "openshift-health-monitor"


class TestConfigEndpoint:
    def test_config(self):
        resp = client.get("/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm_enabled" in data
        assert "thresholds" in data
        assert "cpu_warning" in data["thresholds"]


class TestCheckEndpoint:
    @patch("src.serving.get_all_checkers")
    def test_check_returns_status(self, mock_checkers):
        mock_checker = MagicMock()
        mock_checker.run.return_value = HealthCheckResult(
            category=CheckCategory.NODES,
            checker_name="test",
            findings=[HealthFinding(
                category=CheckCategory.NODES, severity=Severity.OK,
                resource_type="Node", resource_name="n1", namespace="",
                message="Ready"
            )]
        )
        mock_checkers.return_value = [mock_checker]
        
        resp = client.post("/check")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_status"] == "ok"
        assert data["total_checks"] == 1
        assert "check_results" in data
        assert "duration_ms" in data
    
    @patch("src.serving.get_all_checkers")
    def test_check_critical(self, mock_checkers):
        mock_checker = MagicMock()
        mock_checker.run.return_value = HealthCheckResult(
            category=CheckCategory.NODES,
            checker_name="nodes",
            findings=[HealthFinding(
                category=CheckCategory.NODES, severity=Severity.CRITICAL,
                resource_type="Node", resource_name="n1", namespace="",
                message="Not ready"
            )]
        )
        mock_checkers.return_value = [mock_checker]
        
        resp = client.post("/check")
        data = resp.json()
        assert data["overall_status"] == "critical"
        assert data["counts"]["critical"] == 1
    
    @patch("src.serving.get_all_checkers")
    def test_check_with_llm(self, mock_checkers):
        mock_checker = MagicMock()
        mock_checker.run.return_value = HealthCheckResult(
            category=CheckCategory.NODES,
            checker_name="test",
            findings=[]
        )
        mock_checkers.return_value = [mock_checker]
        
        resp = client.post("/check?use_llm=true")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm_insight" in data


class TestSummaryEndpoint:
    @patch("src.serving.get_all_checkers")
    def test_summary(self, mock_checkers):
        mock_checker = MagicMock()
        mock_checker.run.return_value = HealthCheckResult(
            category=CheckCategory.NODES,
            checker_name="test",
            findings=[HealthFinding(
                category=CheckCategory.NODES, severity=Severity.OK,
                resource_type="Node", resource_name="n1", namespace="",
                message="Ready"
            )]
        )
        mock_checkers.return_value = [mock_checker]
        
        resp = client.get("/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_status" in data
        assert "checks_run" in data
        assert "critical" in data
        assert "warnings" in data


class TestMetricsEndpoint:
    @patch("src.serving.get_all_checkers")
    def test_metrics_prometheus_format(self, mock_checkers):
        mock_checker = MagicMock()
        mock_checker.run.return_value = HealthCheckResult(
            category=CheckCategory.NODES,
            checker_name="test",
            findings=[HealthFinding(
                category=CheckCategory.NODES, severity=Severity.WARNING,
                resource_type="Node", resource_name="n1", namespace="",
                message="Warning"
            )]
        )
        mock_checkers.return_value = [mock_checker]
        
        resp = client.get("/metrics")
        assert resp.status_code == 200
        text = resp.text
        assert "openshift_health_status" in text
        assert "openshift_health_checks_total" in text
        assert "openshift_health_findings_total" in text
