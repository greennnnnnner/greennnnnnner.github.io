"""Test spatial seam matching without importing Maya."""
import ast
from collections import defaultdict
import math
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1] / "multi-weight-transfer/scripts/multi_weight_transfer.py"
tree = ast.parse(source.read_text(encoding="utf-8"))
tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name == "_nearest_seam_matches"]
namespace = {"math": math, "defaultdict": defaultdict}
exec(compile(tree, str(source), "exec"), namespace)
match = namespace["_nearest_seam_matches"]


class SeamTests(unittest.TestCase):
    def test_nearest_master_wins(self):
        result = match({"master": [(0, 0, 0), (0.05, 0, 0)],
                        "target": [(0.04, 0, 0), (2, 0, 0)]}, "master", 0.1)
        self.assertEqual(result[("target", 0)][1], 1)
        self.assertNotIn(("target", 1), result)

    def test_negative_coordinates_and_cell_boundary(self):
        result = match({"master": [(-0.201, 0, 0)],
                        "target": [(-0.199, 0, 0)]}, "master", 0.01)
        self.assertIn(("target", 0), result)

    def test_zero_threshold(self):
        result = match({"master": [(0, 0, 0)],
                        "target": [(0, 0, 0), (1e-9, 0, 0)]}, "master", 0)
        self.assertEqual(set(result), {("target", 0)})


if __name__ == "__main__":
    unittest.main()
