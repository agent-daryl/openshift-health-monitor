import os
from typing import Optional

class Config:
    """Configuration for the health monitor."""
    
    # OpenShift/K8s cluster connection
    KUBECONFIG: Optional[str] = os.environ.get("KUBECONFIG")
    OC_ENDPOINT: str = os.environ.get("OC_ENDPOINT", "")
    OC_TOKEN: str = os.environ.get("OC_TOKEN", "")
    NAMESPACE: Optional[str] = os.environ.get("MONITOR_NAMESPACE")
    
    # LLM integration (optional, for intelligent analysis)
    LLM_ENABLED: bool = os.environ.get("LLM_ENABLED", "false").lower() == "true"
    LLM_API_BASE: str = os.environ.get("LLM_API_BASE", "http://10.10.0.20:8000/v1")
    LLM_MODEL: str = os.environ.get("LLM_MODEL", "qwen3.6:27b_256k")
    LLM_API_KEY: str = os.environ.get("LLM_API_KEY", "not-needed")
    
    # Thresholds
    CPU_WARNING_THRESHOLD: float = float(os.environ.get("CPU_WARNING_THRESHOLD", "0.7"))
    CPU_CRITICAL_THRESHOLD: float = float(os.environ.get("CPU_CRITICAL_THRESHOLD", "0.9"))
    MEMORY_WARNING_THRESHOLD: float = float(os.environ.get("MEMORY_WARNING_THRESHOLD", "0.8"))
    MEMORY_CRITICAL_THRESHOLD: float = float(os.environ.get("MEMORY_CRITICAL_THRESHOLD", "0.95"))
    POD_RESTART_WARNING_THRESHOLD: int = int(os.environ.get("POD_RESTART_WARNING_THRESHOLD", "5"))
    POD_RESTART_CRITICAL_THRESHOLD: int = int(os.environ.get("POD_RESTART_CRITICAL_THRESHOLD", "15"))
    NODE_NOT_READY_TIMEOUT: int = int(os.environ.get("NODE_NOT_READY_TIMEOUT", "300"))
    
    # Server
    HOST: str = os.environ.get("HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("PORT", "8080"))
    
    # Check intervals (seconds)
    CHECK_INTERVAL: int = int(os.environ.get("CHECK_INTERVAL", "60"))
    
    @classmethod
    def use_cluster_auth(cls) -> bool:
        return bool(cls.OC_ENDPOINT and cls.OC_TOKEN)
    
    @classmethod
    def use_kubeconfig(cls) -> bool:
        return bool(cls.KUBECONFIG)
