# Unsmooth Skin Weights

Sharpen skin-weight transitions on a mesh or selected vertices. Maya soft selection controls the falloff. The operation supports Undo and Redo.

## Install

Download the repository and extract it. In Maya's Python Script Editor, run:

```python
import runpy
runpy.run_path(r"C:\path\to\maya-skin-tools\unsmooth-skin-weights\install.py", run_name="__main__")
```

The installer copies the command plug-in and UI to Maya's user directories, loads the plug-in, and opens the window. Existing files are backed up. Restart Maya before installing an update to a loaded plug-in.

For manual installation, copy `plug-ins/unsmoothSkinWeights.py` to your Maya plug-ins directory and `scripts/unsmoothSkinWeightsUI.py` to your Maya scripts directory. Load the plug-in in Plug-in Manager, then run:

```python
import unsmoothSkinWeightsUI
unsmoothSkinWeightsUI.show_ui()
```

## Use

1. Select one skinned mesh or its vertices.
2. Enable soft selection with **B** if you need a falloff.
3. Choose a mode and adjust Strength.
4. Click **Apply**. Use Undo to compare the result.

**Contrast** applies a gamma curve to each vertex's weights. It strengthens the dominant influence without reading nearby vertices.

**Neighbor** uses each influence's highest weight in the local neighborhood as a mask. **Surface** uses edge-connected vertices. **Volume** uses vertices within a world-space radius, including vertices across folds or on nearby meshes' surfaces only when part of the same selected mesh.

| Parameter | Default | Range or values |
| --- | --- | --- |
| Mode | Contrast | Contrast, Neighbor |
| Neighbor mode | Surface | Surface, Volume |
| Radius | 1.0 | Greater than 0; world units |
| Strength | 0.5 | 0–1 |
| Iterations | 1 | Integer, at least 1 |
| Prune | 0.001 | 0–1; removes weights below the threshold |

```python
import maya.cmds as cmds
cmds.unsmoothSkinWeights(mode="contrast", strength=0.5, iterations=1)
cmds.unsmoothSkinWeights(mode="neighbor", neighborMode="surface", strength=0.5)
cmds.unsmoothSkinWeights(mode="neighbor", neighborMode="volume", neighborRadius=1.0)
```

## Notes

- This sharpens existing weights; it cannot recover weights from before a smoothing operation.
- Neighbor updates run in vertex-index order. Later vertices read earlier updates in the same iteration.
- Volume search costs O(selected vertices × mesh vertices). Neighbor mode reads all mesh weights.
- The tool does not enforce influence locks or maximum-influence limits. Use an unlocked working skinCluster.
- If pruning clears every influence on a vertex, its previous weights are retained.
