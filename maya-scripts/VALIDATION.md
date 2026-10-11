# Validation

Checked on 2026-10-08 with Maya 2025's bundled Python on Windows.

| Check | Result |
| --- | --- |
| Unsmooth numerical tests | 7 passed |
| Spatial seam tests | 3 passed |
| Unsmooth Maya integration | Passed: Contrast, Surface, Volume, soft selection, sparse influence indices, non-target preservation, Undo and Redo |
| Transfer Maya integration | Passed: multiple sources and destinations, influence name matching, seam copying, temporary cleanup, selection restoration, Undo and Redo, all four association methods |
| Python syntax | Passed |

The integration scripts create test meshes in separate Maya standalone
processes. They do not open user scenes. The Unsmooth run emitted a Maya
normalization warning; weight and undo assertions passed.

Window layout and installer writes have not been tested in an interactive Maya
session. Other Maya versions, production meshes, locked influences, instanced
meshes and large-mesh performance have not been verified.

Run the checks from this repository's root:

```shell
mayapy -m unittest discover -s unsmooth-skin-weights/tests -p test_algorithms.py -v
mayapy -m unittest discover -s tests -p test_seams.py -v
mayapy unsmooth-skin-weights/tests/maya_smoke.py
mayapy tests/maya_transfer_smoke.py
```
