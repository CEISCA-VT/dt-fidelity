"""Causal newest-source receiver; all public clocks use integer nanoseconds."""
from dataclasses import dataclass
import numpy as np


def nanoseconds(seconds):
    """Historical np.rint clock convention; not truncation or float comparisons."""
    seconds = np.asarray(seconds, dtype=float)
    if not np.isfinite(seconds).all() or np.any(np.abs(seconds) >= 9.22e9):
        raise ValueError("Seconds must be finite and fit an int64 nanosecond clock")
    return np.rint(seconds * 1_000_000_000).astype(np.int64)


def clock(values, name="clock"):
    a = np.asarray(values)
    if a.ndim != 1 or a.dtype.kind not in "iu" or np.any(a > np.iinfo(np.int64).max):
        raise ValueError(f"{name} must be a one-dimensional integer-nanosecond array")
    return a.astype(np.int64)


@dataclass
class Trajectory:
    time_ns: np.ndarray
    values: dict[str, np.ndarray]
    valid: np.ndarray | None = None
    available_ns: np.ndarray | None = None

    def __post_init__(self):
        self.time_ns = clock(self.time_ns)
        if np.any(np.diff(self.time_ns) <= 0):
            raise ValueError("Trajectory source/query timestamps must strictly increase")
        self.values = {k: np.asarray(v, dtype=float) for k, v in self.values.items()}
        if not self.values or any(v.ndim != 1 or len(v) != len(self.time_ns) for v in self.values.values()):
            raise ValueError("Trajectory components must match the timestamp vector")
        self.valid = np.ones(len(self.time_ns), bool) if self.valid is None else np.asarray(self.valid, bool)
        if self.valid.shape != self.time_ns.shape:
            raise ValueError("Validity mask must match timestamps")
        self.available_ns = self.time_ns.copy() if self.available_ns is None else clock(self.available_ns, "availability")
        if self.available_ns.shape != self.time_ns.shape or np.any(self.available_ns < self.time_ns):
            raise ValueError("Availability must match source states and cannot precede source time")


@dataclass
class Delivery:
    source_indices: np.ndarray
    arrival_ns: np.ndarray

    def __post_init__(self):
        self.source_indices = clock(self.source_indices, "source indices")
        self.arrival_ns = clock(self.arrival_ns, "arrivals")
        if self.source_indices.shape != self.arrival_ns.shape:
            raise ValueError("Packet indices and arrivals must have the same length")


def reconstruct(source_states, delivery, query_ns):
    """Lost packets are omitted. Duplicate transmissions are permitted."""
    query = clock(query_ns, "queries")
    source = delivery.source_indices
    if np.any(source < 0) or np.any(source >= len(source_states.time_ns)):
        raise ValueError("Packet source index out of range")
    if np.any(delivery.arrival_ns < source_states.available_ns[source]):
        raise ValueError("Causal delivery requires arrival >= source availability")
    order = np.argsort(delivery.arrival_ns, kind="stable")
    arrivals, indices = delivery.arrival_ns[order], source[order]
    # Strictly increasing source timestamps mean max index == newest timestamp.
    newest = np.maximum.accumulate(indices)
    packet = np.searchsorted(arrivals, query, side="right") - 1
    held = np.full(len(query), -1, dtype=int)
    valid = packet >= 0
    held[valid] = newest[packet[valid]]
    return held


def periodic_delivery(source_states, rate_hz, delay_ms=0.0, source_clock_hz=10.0):
    """Native-clock subsampling used by the original primary ledger.

    Adds transmission delay AFTER availability; never changes state/source time.
    """
    if not np.isfinite(rate_hz) or rate_hz <= 0 or not np.isfinite(source_clock_hz) or source_clock_hz <= 0:
        raise ValueError("Rates must be positive and finite")
    stride = int(round(source_clock_hz / rate_hz))
    if stride < 1 or not np.isclose(stride * rate_hz, source_clock_hz, rtol=0, atol=1e-12):
        raise ValueError("Rate must divide the native source clock")
    if not np.isfinite(delay_ms) or delay_ms < 0:
        raise ValueError("Transmission delay must be nonnegative and finite")
    indices = np.arange(0, len(source_states.time_ns), stride)
    return Delivery(indices, source_states.available_ns[indices] + int(round(delay_ms * 1e6)))
