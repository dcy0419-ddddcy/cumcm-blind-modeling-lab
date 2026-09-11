import importlib.util
import math
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "solve_b.py"
SPEC = importlib.util.spec_from_file_location("solve_b", MODULE_PATH)
solve_b = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = solve_b
SPEC.loader.exec_module(solve_b)


class Question1Tests(unittest.TestCase):
    def test_key_boundaries(self):
        self.assertEqual(solve_b.q1_boundary(8), (None, 8))
        self.assertEqual(solve_b.q1_boundary(43), (0, 12))
        self.assertEqual(solve_b.q1_boundary(100), (4, 19))

    def test_boundary_error_control_at_horizon(self):
        oc = solve_b.q1_operating_characteristic(0.10)
        self.assertLessEqual(oc["reject_probability"], 0.05 + 1e-12)
        self.assertLessEqual(oc["accept_probability"], 0.10 + 1e-12)
        total = (
            oc["reject_probability"]
            + oc["accept_probability"]
            + oc["unresolved_probability_at_max_n"]
        )
        self.assertAlmostEqual(total, 1.0, places=10)


class Question2Tests(unittest.TestCase):
    def test_optimal_policies_and_costs(self):
        expected = {
            1: ({"1101"}, 37.888888888888886),
            2: ({"1101"}, 44.0),
            3: ({"1101", "1111"}, 40.55555555555556),
            4: ({"1111"}, 41.25),
            5: ({"0100"}, 44.01234567901234),
            6: ({"0000"}, 34.3213296398892),
        }
        for case in solve_b.Q2_CASES:
            evaluated = []
            for policy in __import__("itertools").product((0, 1), repeat=4):
                result = solve_b.q2_evaluate(case, policy)
                if result["feasible"]:
                    evaluated.append((result["expected_fulfillment_cost"], policy))
            minimum = min(item[0] for item in evaluated)
            policies = {
                solve_b.q2_policy_text(policy)
                for cost, policy in evaluated
                if math.isclose(cost, minimum, abs_tol=1e-10)
            }
            self.assertEqual(policies, expected[case.case][0])
            self.assertAlmostEqual(minimum, expected[case.case][1], places=10)

    def test_unsafe_reuse_is_infeasible(self):
        result = solve_b.q2_evaluate(solve_b.Q2_CASES[0], (0, 1, 1, 1))
        self.assertFalse(result["feasible"])
        self.assertTrue(math.isinf(result["expected_fulfillment_cost"]))


class Question3Tests(unittest.TestCase):
    def test_feasible_policy_count_and_optimum(self):
        policies = solve_b.generate_q3_policies()
        self.assertEqual(len(policies), 6012)
        best = min(policies, key=lambda policy: solve_b.q3_evaluate(policy)["expected_fulfillment_cost"])
        self.assertEqual(solve_b.q3_policy_fields(best)["inspect_components"], "11111111")
        self.assertEqual(solve_b.q3_policy_fields(best)["inspect_semis"], "111")
        self.assertEqual(solve_b.q3_policy_fields(best)["dismantle_semis"], "111")
        self.assertEqual(best[3:], (0, 1))
        result = solve_b.q3_evaluate(best)
        self.assertAlmostEqual(result["expected_fulfillment_cost"], 139.77777777777777)
        self.assertAlmostEqual(result["expected_profit"], 60.22222222222223)


class OutputTests(unittest.TestCase):
    def test_generated_summary_exists(self):
        summary = MODULE_PATH.parents[1] / "results" / "summary.json"
        self.assertTrue(summary.is_file())
        self.assertGreater(summary.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
