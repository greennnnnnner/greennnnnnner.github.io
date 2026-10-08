"""Execute pure algorithm definitions from the plugin without Maya imports."""
import ast
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "plug-ins" / "unsmoothSkinWeights.py"
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
names = {"_apply_prune_and_normalise", "_compute_contrast", "_compute_neighbor"}
tree.body = [node for node in tree.body
             if isinstance(node, ast.FunctionDef) and node.name in names]
namespace = {}
exec(compile(tree, str(SOURCE), "exec"), namespace)
contrast = namespace["_compute_contrast"]
neighbor = namespace["_compute_neighbor"]


class AlgorithmTests(unittest.TestCase):
    def test_contrast_matches_gamma(self):
        result = contrast([[0.8, 0.2]], 2, [0], [0.5], 1, 0.0)[0]
        expected = 0.8 ** 2.5 / (0.8 ** 2.5 + 0.2 ** 2.5)
        self.assertAlmostEqual(result[0], expected)
        self.assertAlmostEqual(sum(result), 1.0)

    def test_zero_strength_preserves_small_weights(self):
        matrix = [[0.9999, 0.0001], [0.2, 0.8]]
        self.assertEqual(contrast(matrix, 2, [0], [0], 3, 0.01)[0], matrix[0])
        self.assertEqual(neighbor(matrix, 2, [0], [0], {0: [1]}, 3, 0.01), matrix)

    def test_sparse_contrast_and_source_immutability(self):
        matrix = [None, [0.8, 0.2], None]
        result = contrast(matrix, 2, [1], [1], 2, 0)
        self.assertGreater(result[1][0], 0.99)
        self.assertEqual(matrix[1], [0.8, 0.2])

    def test_neighbor_uses_significance_and_keeps_nontargets(self):
        matrix = [[0.5, 0.5], [1.0, 0.0]]
        result = neighbor(matrix, 2, [0], [1], {0: [1]}, 1, 0)
        self.assertAlmostEqual(result[0][0], 2.0 / 3.0)
        self.assertEqual(result[1], matrix[1])
        self.assertEqual(matrix[0], [0.5, 0.5])

    def test_pruning_and_all_pruned_fallback(self):
        self.assertEqual(contrast([[0.99, 0.01]], 2, [0], [1], 1, 0.001)[0], [1, 0])
        matrix = [[0.5, 0.5]]
        self.assertEqual(contrast(matrix, 2, [0], [1], 1, 1)[0], matrix[0])
        self.assertEqual(neighbor(matrix, 2, [0], [1], {}, 1, 1), matrix)

    def test_soft_falloff_changes_less(self):
        full = contrast([[0.8, 0.2]], 2, [0], [1], 1, 0)[0][0]
        soft = contrast([[0.8, 0.2]], 2, [0], [0.25], 1, 0)[0][0]
        self.assertGreater(full, soft)
        self.assertGreater(soft, 0.8)

    def test_zero_rows_remain_zero(self):
        self.assertEqual(contrast([[0, 0]], 2, [0], [1], 1, 0)[0], [0, 0])
        self.assertEqual(neighbor([[0, 0]], 2, [0], [1], {}, 1, 0), [[0, 0]])


if __name__ == "__main__":
    unittest.main()
