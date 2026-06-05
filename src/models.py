from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from datetime import datetime


class Severity(str, Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    INFO = "info"


class CheckCategory(str, Enum):
    NODES = "nodes"
    PODS = "pods"
    RESOURCES = "resources"
    NETWORK = "network"
    STORAGE = "storage"
    ROUTES = "routes"
    EVENTS = "events"


@dataclass
class HealthFinding:
    """A single finding from a health check."""
    category: CheckCategory
    severity: Severity
    resource_type: str
    resource_name: str
    namespace: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class HealthCheckResult:
    """Result of a single health checker run."""
    category: CheckCategory
    checker_name: str
    findings: list[HealthFinding] = field(default_factory=list)
    duration_ms: float = 0.0
    error: str = ""
    
    @property
    def is_healthy(self) -> bool:
        return all(f.severity in (Severity.OK, Severity.INFO) for f in self.findings)
    
    @property
    def has_warnings(self) -> bool:
        return any(f.severity == Severity.WARNING for f in self.findings)
    
    @property
    def has_critical(self) -> bool:
        return any(f.severity == Severity.CRITICAL for f in self.findings)
    
    @property
    def total_findings(self) -> int:
        return len(self.findings)


@dataclass
class ClusterHealthSummary:
    """Aggregated health status across all checkers."""
    overall_status: Severity = Severity.OK
    total_checks: int = 0
    total_findings: int = 0
    ok_count: int = 0
    warning_count: int = 0
    critical_count: int = 0
    info_count: int = 0
    check_results: list[HealthCheckResult] = field(default_factory=list)
    top_issues: list[HealthFinding] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    @classmethod
    def from_results(cls, results: list[HealthCheckResult]) -> "ClusterHealthSummary":
        summary = cls()
        summary.total_checks = len(results)
        for r in results:
            summary.check_results.append(r)
            for f in r.findings:
                summary.total_findings += 1
                if f.severity == Severity.OK:
                    summary.ok_count += 1
                elif f.severity == Severity.WARNING:
                    summary.warning_count += 1
                elif f.severity == Severity.CRITICAL:
                    summary.critical_count += 1
                elif f.severity == Severity.INFO:
                    summary.info_count += 1
        
        if summary.critical_count > 0:
            summary.overall_status = Severity.CRITICAL
        elif summary.warning_count > 0:
            summary.overall_status = Severity.WARNING
        else:
            summary.overall_status = Severity.OK
        
        all_findings = []
        for r in results:
            all_findings.extend(r.findings)
        all_findings.sort(
            key=lambda f: (
                0 if f.severity == Severity.CRITICAL else
                1 if f.severity == Severity.WARNING else
                2 if f.severity == Severity.INFO else 3
            )
        )
        summary.top_issues = all_findings[:10]
        return summary
