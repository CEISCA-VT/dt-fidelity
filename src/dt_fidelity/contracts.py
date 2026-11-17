"""Service quantities retain their own units and inclusive tolerances."""
from dataclasses import dataclass, field
from collections.abc import Mapping
import math


@dataclass(frozen=True)
class ServiceContract:
    name: str
    tolerances: Mapping[str, float]
    max_age_s: float
    horizon_s: float = 0.0
    satisfaction: float = 0.80
    minimum_observability: float = 0.95
    units: Mapping[str, str] = field(default_factory=dict)
    evidence_rules: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.tolerances or any(not math.isfinite(v) or v < 0 for v in self.tolerances.values()):
            raise ValueError("Declare nonnegative finite component tolerances")
        if any(not math.isfinite(v) or v < 0 for v in (self.max_age_s, self.horizon_s)):
            raise ValueError("Age and horizon must be finite and nonnegative")
        if not (0 < self.satisfaction <= 1 and 0 < self.minimum_observability <= 1):
            raise ValueError("Satisfaction and observability must be in (0, 1]")
        object.__setattr__(self, "tolerances", dict(self.tolerances))
        object.__setattr__(self, "units", dict(self.units))
