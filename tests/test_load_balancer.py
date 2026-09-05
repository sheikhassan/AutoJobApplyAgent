import os
from app.load_balancer import ModelLoadBalancer

def test_single_default_target(monkeypatch):
    monkeypatch.delenv("MODEL_TARGETS", raising=False)
    monkeypatch.setenv("FIREWORKS_MODEL", "test-model")
    lb = ModelLoadBalancer()
    assert len(lb.targets) == 1
    assert lb.targets[0].model == "test-model"
