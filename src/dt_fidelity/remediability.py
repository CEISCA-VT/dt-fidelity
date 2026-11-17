"""Paired delivery comparisons never fit or modify source trajectories."""
from .evaluator import evaluate


def classify(degraded, ideal, practical=None):
    """Manuscript precedence, including nonmonotonic delivery outcomes."""
    results = [degraded, ideal] + ([] if practical is None else [practical])
    if any(r.outcome == "unobservable" for r in results):
        return "unobservable"
    if degraded.outcome == "qualified":
        return "already_qualified_degraded"
    return "delivery_remediable" if ideal.outcome == "qualified" else "persistent_under_ideal"


def compare_delivery(*, physical_reference, source_states, deliveries, contract, **kwargs):
    if not {"degraded", "ideal"}.issubset(deliveries):
        raise ValueError("Provide degraded and ideal delivery histories")
    results = {name: evaluate(physical_reference=physical_reference, source_states=source_states,
                              delivery=history, contract=contract, **kwargs)
               for name, history in deliveries.items()}
    label = classify(results["degraded"], results["ideal"], results.get("practical"))
    restored = label == "delivery_remediable" and "practical" in results and results["practical"].outcome == "qualified"
    return {"classification": label, "practical_restores": restored, "results": results}
