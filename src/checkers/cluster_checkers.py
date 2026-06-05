import subprocess
import json
import time
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from typing import Optional
from src.config import Config
from src.models import HealthFinding, HealthCheckResult, Severity, CheckCategory


class BaseChecker:
    """Base class for health checkers."""
    
    category: CheckCategory
    name: str
    
    def run(self) -> HealthCheckResult:
        start = time.time()
        result = HealthCheckResult(category=self.category, checker_name=self.name)
        try:
            result.findings = self.check()
        except Exception as e:
            result.error = str(e)
            result.findings = [
                HealthFinding(
                    category=self.category,
                    severity=Severity.CRITICAL,
                    resource_type="checker",
                    resource_name=self.name,
                    namespace="",
                    message=f"Checker failed: {e}",
                    recommendation="Check connectivity to the cluster and verify credentials."
                )
            ]
        result.duration_ms = (time.time() - start) * 1000
        return result
    
    def check(self) -> list[HealthFinding]:
        raise NotImplementedError
    
    def _run_oc(self, args: list[str], namespace: Optional[str] = None) -> str:
        """Run an oc command and return stdout."""
        cmd = ["oc"]
        if namespace and Config.NAMESPACE is None:
            cmd.extend(["-n", namespace])
        elif Config.NAMESPACE:
            cmd.extend(["-n", Config.NAMESPACE])
        cmd.extend(args)
        
        if Config.use_cluster_auth():
            cmd = ["oc", "--server", Config.OC_ENDPOINT, "--token", Config.OC_TOKEN] + args
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"oc {args[0]} failed: {result.stderr.strip()}")
        return result.stdout


class NodeChecker(BaseChecker):
    """Checks cluster node health."""
    
    category = CheckCategory.NODES
    name = "node_health"
    
    def check(self) -> list[HealthFinding]:
        output = self._run_oc(["get", "nodes", "-o", "json"])
        nodes = json.loads(output)
        findings = []
        
        for node in nodes.get("items", []):
            name = node["metadata"]["name"]
            conditions = node.get("status", {}).get("conditions", [])
            
            ready = False
            conditions_list = []
            for c in conditions:
                conditions_list.append(f"{c.get('type', 'unknown')}={c.get('status', 'unknown')}")
                if c.get("type") == "Ready" and c.get("status") == "True":
                    ready = True
            
            allocatable = node.get("status", {}).get("allocatable", {})
            cpu_capacity = allocatable.get("cpu", "0")
            memory_capacity = allocatable.get("memory", "0")
            
            if ready:
                findings.append(HealthFinding(
                    category=self.category,
                    severity=Severity.OK,
                    resource_type="Node",
                    resource_name=name,
                    namespace="",
                    message=f"Node {name} is Ready",
                    details={"conditions": ", ".join(conditions_list), "cpu": cpu_capacity, "memory": memory_capacity}
                ))
            else:
                findings.append(HealthFinding(
                    category=self.category,
                    severity=Severity.CRITICAL,
                    resource_type="Node",
                    resource_name=name,
                    namespace="",
                    message=f"Node {name} is NOT Ready",
                    details={"conditions": ", ".join(conditions_list)},
                    recommendation="Check node logs: oc describe node " + name + ". Investigate kubelet status and network connectivity."
                ))
            
            # Check for DiskPressure, MemoryPressure, PIDPressure
            for c in conditions:
                if c.get("type") in ("DiskPressure", "MemoryPressure", "PIDPressure") and c.get("status") == "True":
                    findings.append(HealthFinding(
                        category=self.category,
                        severity=Severity.CRITICAL,
                        resource_type="Node",
                        resource_name=name,
                        namespace="",
                        message=f"Node {name} has {c['type']} condition",
                        recommendation=f"Check {c['type'].lower()} on {name}. Consider scaling or cleanup."
                    ))
        
        not_ready = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        total = len([f for f in findings if f.resource_type == "Node"])
        
        if not_ready == 0 and total > 0:
            findings.append(HealthFinding(
                category=self.category,
                severity=Severity.INFO,
                resource_type="NodeSummary",
                resource_name="",
                namespace="",
                message=f"All {total} nodes are healthy",
            ))
        elif total == 0:
            findings.append(HealthFinding(
                category=self.category,
                severity=Severity.WARNING,
                resource_type="NodeSummary",
                resource_name="",
                namespace="",
                message="No nodes found — cluster may be unreachable",
                recommendation="Verify oc cluster connectivity and credentials."
            ))
        
        return findings


class PodChecker(BaseChecker):
    """Checks pod health across the cluster."""
    
    category = CheckCategory.PODS
    name = "pod_health"
    
    def check(self) -> list[HealthFinding]:
        output = self._run_oc(["get", "pods", "--all-namespaces", "-o", "json"])
        pods = json.loads(output)
        findings = []
        
        for pod in pods.get("items", []):
            name = pod["metadata"]["name"]
            ns = pod["metadata"].get("namespace", "default")
            phase = pod.get("status", {}).get("phase", "Unknown")
            restarts = sum(c.get("restartCount", 0) for c in pod.get("status", {}).get("containerStatuses", []))
            
            if phase == "Running":
                if restarts >= Config.POD_RESTART_CRITICAL_THRESHOLD:
                    findings.append(HealthFinding(
                        category=self.category,
                        severity=Severity.CRITICAL,
                        resource_type="Pod",
                        resource_name=name,
                        namespace=ns,
                        message=f"Pod {name} has {restarts} restarts (critical threshold: {Config.POD_RESTART_CRITICAL_THRESHOLD})",
                        recommendation=f"Investigate crash loop: oc logs {name} -n {ns} --previous"
                    ))
                elif restarts >= Config.POD_RESTART_WARNING_THRESHOLD:
                    findings.append(HealthFinding(
                        category=self.category,
                        severity=Severity.WARNING,
                        resource_type="Pod",
                        resource_name=name,
                        namespace=ns,
                        message=f"Pod {name} has {restarts} restarts (warning threshold: {Config.POD_RESTART_WARNING_THRESHOLD})",
                        recommendation=f"Monitor pod: oc logs {name} -n {ns}"
                    ))
                else:
                    findings.append(HealthFinding(
                        category=self.category,
                        severity=Severity.OK,
                        resource_type="Pod",
                        resource_name=name,
                        namespace=ns,
                        message=f"Pod {name} is Running",
                        details={"restarts": restarts}
                    ))
            elif phase in ("Pending", "Unknown"):
                findings.append(HealthFinding(
                    category=self.category,
                    severity=Severity.WARNING,
                    resource_type="Pod",
                    resource_name=name,
                    namespace=ns,
                    message=f"Pod {name} is in {phase} state",
                    recommendation=f"Check pod events: oc describe pod {name} -n {ns}"
                ))
            elif phase == "Failed":
                findings.append(HealthFinding(
                    category=self.category,
                    severity=Severity.CRITICAL,
                    resource_type="Pod",
                    resource_name=name,
                    namespace=ns,
                    message=f"Pod {name} has Failed",
                    recommendation=f"Check logs: oc logs {name} -n {ns}. Check events: oc describe pod {name} -n {ns}"
                ))
            elif phase == "Succeeded":
                findings.append(HealthFinding(
                    category=self.category,
                    severity=Severity.INFO,
                    resource_type="Pod",
                    resource_name=name,
                    namespace=ns,
                    message=f"Pod {name} completed successfully (Job/CronJob)"
                ))
        
        return findings


class ResourceQuotaChecker(BaseChecker):
    """Checks resource quotas and utilization."""
    
    category = CheckCategory.RESOURCES
    name = "resource_utilization"
    
    def check(self) -> list[HealthFinding]:
        findings = []
        
        # Check node resource utilization
        try:
            output = self._run_oc(["top", "nodes", "--no-headers"])
            for line in output.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) < 5:
                    continue
                node_name = parts[0]
                cpu_usage = parts[1]
                cpu_total = parts[2]
                mem_usage = parts[3]
                mem_total = parts[4]
                
                cpu_pct = self._parse_resource_pct(cpu_usage, cpu_total)
                mem_pct = self._parse_resource_pct(mem_usage, mem_total)
                
                if cpu_pct >= Config.CPU_CRITICAL_THRESHOLD:
                    findings.append(HealthFinding(
                        category=self.category,
                        severity=Severity.CRITICAL,
                        resource_type="Node",
                        resource_name=node_name,
                        namespace="",
                        message=f"Node {node_name} CPU at {cpu_pct*100:.0f}%",
                        recommendation="Consider adding nodes or reducing workload. Check for CPU-intensive pods."
                    ))
                elif cpu_pct >= Config.CPU_WARNING_THRESHOLD:
                    findings.append(HealthFinding(
                        category=self.category,
                        severity=Severity.WARNING,
                        resource_type="Node",
                        resource_name=node_name,
                        namespace="",
                        message=f"Node {node_name} CPU at {cpu_pct*100:.0f}%",
                    ))
                
                if mem_pct >= Config.MEMORY_CRITICAL_THRESHOLD:
                    findings.append(HealthFinding(
                        category=self.category,
                        severity=Severity.CRITICAL,
                        resource_type="Node",
                        resource_name=node_name,
                        namespace="",
                        message=f"Node {node_name} Memory at {mem_pct*100:.0f}%",
                        recommendation="Check for memory leaks. Consider OOMKill events: oc get events -A --field-selector reason=OOMKilling"
                    ))
                elif mem_pct >= Config.MEMORY_WARNING_THRESHOLD:
                    findings.append(HealthFinding(
                        category=self.category,
                        severity=Severity.WARNING,
                        resource_type="Node",
                        resource_name=node_name,
                        namespace="",
                        message=f"Node {node_name} Memory at {mem_pct*100:.0f}%",
                    ))
        
        except RuntimeError:
            findings.append(HealthFinding(
                category=self.category,
                severity=Severity.INFO,
                resource_type="ResourceSummary",
                resource_name="",
                namespace="",
                message="Node resource metrics unavailable (metrics-server may not be installed)",
            ))
        
        return findings
    
    def _parse_resource_pct(self, usage: str, total: str) -> float:
        u = self._parse_resource(usage)
        t = self._parse_resource(total)
        return u / t if t > 0 else 0.0
    
    def _parse_resource(self, val: str) -> float:
        val = val.strip()
        if val.endswith("m"):
            return float(val[:-1]) / 1000
        elif val.endswith("Ki"):
            return float(val[:-2])
        elif val.endswith("Mi"):
            return float(val[:-2]) * 1024
        elif val.endswith("Gi"):
            return float(val[:-2]) * 1024 * 1024
        else:
            try:
                return float(val)
            except ValueError:
                return 0.0


class EventsChecker(BaseChecker):
    """Checks recent cluster events for issues."""
    
    category = CheckCategory.EVENTS
    name = "recent_events"
    
    def check(self) -> list[HealthFinding]:
        findings = []
        warning_events = []
        error_keywords = ["Failed", "Unhealthy", "BackOff", "OOMKilled", "Evicted", 
                          "DeadlineExceeded", "ErrImagePull", "ImagePullBackOff",
                          "CrashLoopBackOff", "NodeNotReady"]
        
        try:
            output = self._run_oc(["get", "events", "--all-namespaces", "--sort-by=.lastTimestamp", "-o", "json"])
            events = json.loads(output)
            
            for event in events.get("items", []):
                reason = event.get("reason", "")
                msg = event.get("message", "")
                event_type = event.get("type", "Normal")
                ns = event.get("metadata", {}).get("namespace", "default")
                inv_obj = event.get("involvedObject", {})
                
                if event_type == "Warning" or any(kw in reason for kw in error_keywords):
                    warning_events.append({
                        "namespace": ns,
                        "reason": reason,
                        "message": msg,
                        "object": f"{inv_obj.get('kind', '')}/{inv_obj.get('name', '')}"
                    })
            
            if warning_events:
                critical_events = [e for e in warning_events if any(kw in e["reason"] for kw in ["OOMKilled", "CrashLoopBackOff", "Evicted"])]
                if critical_events:
                    for e in critical_events[:5]:
                        findings.append(HealthFinding(
                            category=self.category,
                            severity=Severity.CRITICAL,
                            resource_type="Event",
                            resource_name=e["reason"],
                            namespace=e["namespace"],
                            message=f"Critical event: {e['message'][:120]}",
                            details={"object": e["object"]},
                            recommendation=f"Investigate {e['object']} in namespace {e['namespace']}"
                        ))
                
                warning_only = [e for e in warning_events if e not in critical_events]
                if warning_only:
                    findings.append(HealthFinding(
                        category=self.category,
                        severity=Severity.WARNING,
                        resource_type="Event",
                        resource_name=f"{len(warning_events)} warnings",
                        namespace="",
                        message=f"{len(warning_events)} warning events in the cluster",
                        details={"sample": [f"{e['namespace']}: {e['reason']}" for e in warning_only[:3]]},
                        recommendation="Review events: oc get events --all-namespaces --sort-by=.lastTimestamp"
                    ))
            else:
                findings.append(HealthFinding(
                    category=self.category,
                    severity=Severity.OK,
                    resource_type="EventSummary",
                    resource_name="",
                    namespace="",
                    message="No warning events detected",
                ))
        
        except RuntimeError:
            findings.append(HealthFinding(
                category=self.category,
                severity=Severity.INFO,
                resource_type="EventSummary",
                resource_name="",
                namespace="",
                message="Unable to fetch cluster events",
            ))
        
        return findings


def get_all_checkers() -> list[BaseChecker]:
    """Return all registered checkers."""
    return [
        NodeChecker(),
        PodChecker(),
        ResourceQuotaChecker(),
        EventsChecker(),
    ]
