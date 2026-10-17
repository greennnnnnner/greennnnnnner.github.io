# Skin Transfer Tool

Batch skin weight transfer in Maya, with separate source and destination lists.

## Install and launch

Copy [skin_transfer_tool.py](skin_transfer_tool.py) into your Maya user scripts directory, or add its folder to `sys.path`. Run in the Python tab of Maya's Script Editor:

```python
import skin_transfer_tool
skin_transfer_tool.show()
```

After editing the script:

```python
import importlib
importlib.reload(skin_transfer_tool)
skin_transfer_tool.show()
```

Requires Maya with Python 3 and `polyUniteSkinned` for multiple combined sources. Core transfers tested in Maya 2025.

## Workflow

1. Select skinned source meshes and click **Add Selected** under Sources.
2. Select target meshes and add them under Destinations.
3. Choose **Pair** or **Combine Sources**, then choose the influence policy and surface association.
4. Click **Transfer Skin**. All rows are processed; row selection is only for Remove and Duplicate Row.

### Pair

Pairs `source[i]` with `destination[i]`. A single source can feed every destination. Otherwise the row counts must match. Use **Duplicate Row** to repeat a source next to its existing row. Remove destinations and add them again to change their order.

### Combine Sources

Copies sources into a temporary group, combines them into one skinned mesh, and transfers to each destination. Source meshes stay intact and temporary meshes are deleted on success or failure. Duplicate source rows are used only once in this mode.

With at least two successful destinations, seam matching copies the nearest master vertex's weights to vertices within the world-space threshold. This is a copy, not an average.

## Influence policies

- **Use source influences:** creates a skinCluster if needed, adds missing source joints to an existing target skinCluster, and copies source maximum influences and skinning method. Existing target-only influences are not removed. Combine uses the largest maximum-influence and skinning-method values among the sources.
- **Use target's own influences:** requires an existing skinCluster. Preserves its influence list and settings, using label / closestJoint association to remap weights. Seam targets missing master influences are skipped so seam handling cannot add joints.

Source-influence transfers match joint names before falling back to labels and nearest joints, so reordered influence lists do not swap weights.

## Surface association

`closestPoint`, `closestComponent`, `rayCast`, or `uvSpace`. UV Space uses each mesh's current UV set.

**Match topology** selects `closestComponent` when vertex counts match, otherwise it falls back to the chosen method for that destination. This is a spatial transfer; equal vertex counts do not verify topology or guarantee a vertex-index copy. The label and documentation were corrected from the pasted draft's exact-copy claim.

## Validation and changes

The pasted draft had missing indentation, comment markers, exponent operators, and broken string literals. Those were repaired. Temporary-source and seam helpers reuse the existing Multi Weight Transfer implementation. This tool is standalone and does not need that script installed.

Maya 2025 standalone checks cover Pair, one-to-many, equal row counts, all four surface modes, Combine, seam weights, reversed influence order, preservation of target influences and skinning method, missing-bind rejection, cleanup after failure, selection restoration, and undo/redo. Run `mayapy maya_smoke.py` in a fresh process.

The interactive window layout and callbacks have not been visually tested in Maya. A failed individual transfer can leave partial edits on its target; use Undo to restore the batch. Successful destinations are reported separately and only successful destinations take part in seam matching.

[Maya scripts](../README.md)
