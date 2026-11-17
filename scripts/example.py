"""A small external trajectory example; not historical reproduction evidence."""
import numpy as np
from dt_fidelity import ServiceContract, Trajectory, nanoseconds, periodic_delivery, evaluate

time = nanoseconds(np.arange(101) / 10)
reference = Trajectory(time, {"east_m": np.arange(101) / 10,
                              "north_m": np.zeros(101), "heading_rad": np.zeros(101)})
twin = Trajectory(time, {k: v.copy() for k, v in reference.values.items()})
contract = ServiceContract("global_pose", {"position_m": 1., "heading_deg": 5.}, max_age_s=1.)
result = evaluate(physical_reference=reference, source_states=twin,
                  delivery=periodic_delivery(twin, rate_hz=5, delay_ms=50), contract=contract)
print(result.outcome)
print(result.joint_satisfaction)
print(result.observability)
