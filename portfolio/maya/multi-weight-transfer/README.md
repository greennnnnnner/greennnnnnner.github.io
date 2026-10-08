# Multi Weight Transfer

Copy skin weights from one or more source meshes to one or more destinations. Sources are duplicated and combined into a temporary skinned mesh. Destinations receive any missing influences.

Seam matching copies weights from a chosen master destination to nearby vertices on the other destinations. It does not average weights.

## Install

Copy `scripts/multi_weight_transfer.py` to your Maya user scripts directory. In Maya's Python Script Editor, run:

```python
import multi_weight_transfer
multi_weight_transfer.show()
```

You can also add the repository's scripts directory to `sys.path`:

```python
import sys
sys.path.insert(0, r"C:\path\to\maya-skin-tools\multi-weight-transfer\scripts")
import multi_weight_transfer
multi_weight_transfer.show()
```

## Use

1. Select the source meshes and click **Add Selected** under Sources. Each source must be skinned.
2. Select the destination meshes and add them under Destinations. They may be unskinned.
3. Choose a surface association method.
4. Enable **Match seam weights** if the destinations share a seam. Select the master and set the threshold in world units.
5. Click **Transfer Weights**.

All meshes in both lists are processed. List selection is only used by **Remove**. A single Undo reverses the transfer, including newly created skinClusters.

| Method | Correspondence |
| --- | --- |
| `closestPoint` | Closest point on the source surface. Default. |
| `closestComponent` | Closest source component. |
| `rayCast` | Ray intersection with the source surface. |
| `uvSpace` | Current UV sets on source and destination. Requires suitable UV correspondence. |

```python
import multi_weight_transfer as mwt
result = mwt.transfer_weights(
    sources=["body_source", "sleeve_source"],
    destinations=["body_target", "sleeve_target"],
    method="closestPoint",
    handle_seams=True,
    seam_threshold=0.001,
    seam_master="body_target",
)
```

## Notes

- Sources and destinations must use the same skeleton. Influences are matched by name.
- Meshes should overlap in world space for spatial methods.
- Seam matching changes weights, not vertex positions. The closest master vertex within the threshold wins.
- Source and destination lists must not overlap. Each transform must have one visible polygon mesh shape.
- The source geometry and weights are left intact; temporary geometry is removed after the operation.
- A failed transfer may leave partial destination edits. Use Undo to restore them.
- Use unlocked influences. Existing skinCluster settings can affect normalization and influence limits.
