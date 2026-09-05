import os
from dataclasses import dataclass
from threading import Lock
from .fireworks_provider import FireworksProvider

@dataclass
class ModelTarget:
    name: str
    model: str
    weight: int = 1
    healthy: bool = True
    failures: int = 0

class ModelLoadBalancer:
    """Weighted round-robin with simple per-model failure isolation."""

    DEFAULT_TARGETS = [
        ("qwen", "accounts/fireworks/models/qwen3p7-plus", 3),
        ("deepseek", "accounts/fireworks/models/deepseek-v4-flash", 2),
    ]

    def __init__(self):
        self.lock = Lock()
        self.targets = self._load_targets()
        self.index = 0

    def _load_targets(self):
        raw = os.getenv("MODEL_TARGETS", "").strip()
        if not raw:
            explicit = os.getenv("FIREWORKS_MODEL", "").strip()
            if explicit and explicit != "accounts/fireworks/models/qwen3p7-plus":
                return [ModelTarget("fireworks-single", explicit, 1)]
            return [ModelTarget(*item) for item in self.DEFAULT_TARGETS]

        targets = []
        for item in raw.split(","):
            name_model, *weight = item.strip().split(":")
            if "=" in name_model:
                name, model = name_model.split("=", 1)
            else:
                name, model = name_model, name_model
            targets.append(ModelTarget(name.strip(), model.strip(), int(weight[0]) if weight else 1))
        return targets

    def _next(self):
        with self.lock:
            healthy = [t for t in self.targets if t.healthy]
            if not healthy:
                for t in self.targets:
                    t.healthy = True
                    t.failures = 0
                healthy = self.targets

            expanded = [t for t in healthy for _ in range(max(1, t.weight))]
            target = expanded[self.index % len(expanded)]
            self.index += 1
            return target

    def chat(self, messages, **kwargs):
        last_error = None
        attempted = set()

        for _ in range(len(self.targets)):
            target = self._next()
            if target.name in attempted:
                continue
            attempted.add(target.name)
            try:
                result = FireworksProvider(model=target.model).chat(messages, **kwargs)
                target.failures = 0
                target.healthy = True
                return result
            except Exception as exc:
                target.failures += 1
                last_error = exc
                if target.failures >= 3:
                    target.healthy = False

        raise RuntimeError(f"All model targets failed: {last_error}")
