import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import Config


class TestConfig:
    def test_defaults(self):
        assert Config.HOST == "0.0.0.0"
        assert Config.PORT == 8080
        assert Config.CPU_WARNING_THRESHOLD == 0.7
        assert Config.CPU_CRITICAL_THRESHOLD == 0.9
        assert Config.MEMORY_WARNING_THRESHOLD == 0.8
        assert Config.MEMORY_CRITICAL_THRESHOLD == 0.95
        assert Config.POD_RESTART_WARNING_THRESHOLD == 5
        assert Config.POD_RESTART_CRITICAL_THRESHOLD == 15
    
    def test_use_cluster_auth_false_by_default(self):
        assert not Config.use_cluster_auth()
    
    def test_use_kubeconfig_false_by_default(self):
        assert not Config.use_kubeconfig()
