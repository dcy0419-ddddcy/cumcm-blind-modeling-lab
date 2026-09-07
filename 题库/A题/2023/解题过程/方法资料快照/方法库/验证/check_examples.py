"""Original, deterministic teaching checks; stdlib only; no problem data or I/O."""
import json
import math
import platform
import random
import sys

checks = []


def check(name, condition, evidence):
    checks.append({"name": name, "passed": bool(condition), "evidence": evidence})


def close(a, b, tol=1e-12):
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def matvec(a, v):
    return tuple(dot(row, v) for row in a)


def reflect(d, n):
    return tuple(x - 2 * dot(d, n) * y for x, y in zip(d, n))


check("M01_tank_balance", 20 + 4 * 3 == 32, {"litres": 32})
angle = math.pi / 2
r = ((math.cos(angle), -math.sin(angle), 0),
     (math.sin(angle), math.cos(angle), 0), (0, 0, 1))
v = (2, 0, 1)
rv = matvec(r, v)
check("M02_active_rotation", all(close(a, b) for a, b in zip(rv, (0, 2, 1))), rv)
transpose = tuple(zip(*r))
back = matvec(transpose, rv)
check("M02_inverse_rotation", all(close(a, b) for a, b in zip(back, v)), back)
check("M02_rotation_norm", close(dot(rv, rv), dot(v, v)), dot(rv, rv))
d, n = (0.6, 0, -0.8), (0, 0, 1)
out = reflect(d, n)
check("M02_reflection", all(close(a, b) for a, b in zip(out, (0.6, 0, 0.8))), out)
check("M02_normal_sign_invariance", reflect(d, (0, 0, -1)) == out, out)
check("M02_reflection_unit", close(dot(out, out), 1), dot(out, out))
t = (1 - 3) / -1
check("M02_plane_forward_intersection", t == 2 and 3 - t == 1, {"t": t, "z": 3 - t})
check("M03_conditional_energy", close((80 / 100) * (60 / 80), 60 / 100), 0.6)
a, b = {1, 2, 3}, {3, 4}
check("M03_union", len(a | b) == len(a) + len(b) - len(a & b), len(a | b))
beta = math.pi / 3  # Teaching angle, not a physical parameter proposal.
z = 2 * math.pi * (1 - math.cos(beta))
steps = 20000
integral = sum(math.sin(beta * (i + 0.5) / steps) for i in range(steps)) * beta / steps
mass = 2 * math.pi * integral / z
check("M03_cone_normalization", close(mass, 1, 1e-8), {"mass": mass, "nodes": steps})
mean_cos = sum(1 - ((i + 0.5) / 100) * (1 - math.cos(beta)) for i in range(100)) / 100
check("M03_cone_mean_cos", close(mean_cos, 0.75), mean_cos)
check("M04_product_order_counterexample", (1 * 3 + 3 * 1) / 2 == 3 and 2 * 2 == 4,
      {"mean_product": 3, "product_means": 4})
ratio_mean = (10 / 20 + 90 / 100) / 2
pooled = (10 + 90) / (20 + 100)
check("M04_ratio_counterexample", close(ratio_mean, 0.7) and close(pooled, 5 / 6),
      {"mean_ratios": ratio_mean, "ratio_totals": pooled})
check("M04_two_level_mean", ((2 + 4) / 2 + (6 + 8) / 2) / 2 == (2 + 4 + 6 + 8) / 4, 5)
errors = []
for nodes in (10, 20, 40):
    val = sum(((i + 0.5) / nodes) ** 2 for i in range(nodes)) / nodes
    err = abs(val - 1 / 3)
    errors.append(err)
    check(f"M05_midpoint_{nodes}", close(err, 1 / (12 * nodes ** 2)),
          {"nodes": nodes, "estimate": val, "absolute_error": err})
check("M05_midpoint_order", close(errors[0] / errors[1], 4, 1e-9), errors[0] / errors[1])
seed = 731
rng1, rng2 = random.Random(seed), random.Random(seed)
sample1 = [rng1.random() for _ in range(20)]
sample2 = [rng2.random() for _ in range(20)]
check("M05_seed_reproducibility", sample1 == sample2,
      {"seed": seed, "generator": "Python random.Random", "samples": 20})

result = {
    "scope": "generic teaching examples only; no target data loaded",
    "python": sys.version,
    "platform": platform.platform(),
    "dependencies": "Python standard library only",
    "tests": len(checks),
    "passed": sum(c["passed"] for c in checks),
    "checks": checks,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(0 if all(c["passed"] for c in checks) else 1)
