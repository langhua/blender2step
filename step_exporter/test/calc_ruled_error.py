"""Calculate maximum error of cosine curve approximation with ruled surfaces."""
import math

# Parameters
nLayers = 50  # Number of intermediate layers
nIntervals = nLayers + 1  # Number of ruled surface intervals

# Cosine curve: f(t) = 1 - cos(pi/2 * t)
# For a single interval [t0, t1], the maximum deviation from linear interpolation
# occurs at the midpoint and equals:
# max_dev = |f(t_mid) - (f(t0) + f(t1))/2|

max_deviation = 0.0
max_dev_t = 0.0

for i in range(nIntervals):
    t0 = i / nIntervals
    t1 = (i + 1) / nIntervals
    t_mid = (t0 + t1) / 2.0
    
    f0 = 1.0 - math.cos(math.pi / 2.0 * t0)
    f1 = 1.0 - math.cos(math.pi / 2.0 * t1)
    f_mid = 1.0 - math.cos(math.pi / 2.0 * t_mid)
    
    # Linear interpolation at midpoint
    f_linear = (f0 + f1) / 2.0
    
    # Deviation
    dev = abs(f_mid - f_linear)
    if dev > max_deviation:
        max_deviation = dev
        max_dev_t = t_mid

# The maximum deviation in the cosine curve parameter
# This is multiplied by the total taper amount to get actual error
total_taper_x = (100 - 80) / 2.0  # 10mm
total_taper_y = (70 - 50) / 2.0  # 10mm

print(f"Number of intermediate layers: {nLayers}")
print(f"Number of ruled surface intervals: {nIntervals}")
print(f"Maximum deviation in cosine curve parameter: {max_deviation:.6f}")
print(f"Maximum deviation occurs at t ≈ {max_dev_t:.4f}")
print(f"")
print(f"Total taper (X): {total_taper_x}mm")
print(f"Total taper (Y): {total_taper_y}mm")
print(f"")
print(f"Maximum error (X): {max_deviation * total_taper_x:.6f}mm")
print(f"Maximum error (Y): {max_deviation * total_taper_y:.6f}mm")
print(f"")

# Calculate required layers for <0.001mm error
target_error = 0.001  # mm
required_dev = target_error / max(total_taper_x, total_taper_y)

print(f"Target error: {target_error}mm")
print(f"Required cosine curve deviation: {required_dev:.6f}")

# Binary search for required number of intervals
for n in range(10, 10000):
    n_int = n + 1
    max_dev = 0.0
    for i in range(n_int):
        t0 = i / n_int
        t1 = (i + 1) / n_int
        t_mid = (t0 + t1) / 2.0
        
        f0 = 1.0 - math.cos(math.pi / 2.0 * t0)
        f1 = 1.0 - math.cos(math.pi / 2.0 * t1)
        f_mid = 1.0 - math.cos(math.pi / 2.0 * t_mid)
        f_linear = (f0 + f1) / 2.0
        dev = abs(f_mid - f_linear)
        max_dev = max(max_dev, dev)
    
    if max_dev * max(total_taper_x, total_taper_y) < target_error:
        print(f"Required intermediate layers for <{target_error}mm error: {n}")
        print(f"  (This creates {n_int} ruled surface intervals)")
        break
