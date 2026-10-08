"""Integration checks in a fresh mayapy process; does not open user scenes.

Run: mayapy tests/maya_smoke.py
"""
from pathlib import Path
import maya.standalone


maya.standalone.initialize(name="python")
import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma


def rows(skin, mesh):
    selection = om.MSelectionList()
    selection.add(mesh)
    path = selection.getDagPath(0)
    path.extendToShape()
    selection = om.MSelectionList()
    selection.add(skin)
    fn = oma.MFnSkinCluster(selection.getDependNode(0))
    component_fn = om.MFnSingleIndexedComponent()
    component = component_fn.create(om.MFn.kMeshVertComponent)
    component_fn.addElements(list(range(om.MFnMesh(path).numVertices)))
    weights, count = fn.getWeights(path, component)
    return [list(weights[i:i + count]) for i in range(0, len(weights), count)]


def close(a, b):
    return all(abs(x - y) < 1e-9 for row_a, row_b in zip(a, b)
               for x, y in zip(row_a, row_b))


try:
    plugin = Path(__file__).resolve().parents[1] / "plug-ins" / "unsmoothSkinWeights.py"
    cmds.loadPlugin(str(plugin))
    cmds.undoInfo(state=True)
    cmds.softSelect(softSelectEnabled=False)
    mesh = cmds.polyPlane(name="unsmoothTestMesh", subdivisionsX=2, subdivisionsY=2)[0]
    joints = []
    for x in (-1, 0, 1):
        cmds.select(clear=True)
        joints.append(cmds.joint(position=(x, 0, 0)))
    skin = cmds.skinCluster(joints, mesh, toSelectedBones=True)[0]
    cmds.skinCluster(skin, edit=True, removeInfluence=joints[1])
    cmds.skinPercent(skin, mesh + ".vtx[*]", transformValue=[(joints[0], 0.8), (joints[2], 0.2)])
    baseline = rows(skin, mesh)
    cmds.select(mesh + ".vtx[0]")
    cmds.unsmoothSkinWeights(mode="contrast", strength=0.5, pruneThreshold=0)
    changed = rows(skin, mesh)
    expected = 0.8 ** 2.5 / (0.8 ** 2.5 + 0.2 ** 2.5)
    assert abs(changed[0][0] - expected) < 1e-9, changed[0]
    assert close(changed[1:], baseline[1:])
    cmds.undo()
    assert close(rows(skin, mesh), baseline), "Undo did not restore weights"
    cmds.redo()
    assert close(rows(skin, mesh), changed), "Redo did not reapply weights"
    for neighbor_mode in ("surface", "volume"):
        cmds.unsmoothSkinWeights(mode="neighbor", neighborMode=neighbor_mode,
                                neighborRadius=2.0, strength=0.5)
        assert all(abs(sum(row) - 1.0) < 1e-9 for row in rows(skin, mesh))
    cmds.softSelect(softSelectEnabled=True, softSelectDistance=2.0)
    cmds.unsmoothSkinWeights(mode="contrast", strength=0.2)
    assert all(abs(sum(row) - 1.0) < 1e-9 for row in rows(skin, mesh))
    print("PASS: Maya {}: contrast, sparse influences, non-target preservation, undo/redo, surface, volume, soft selection".format(cmds.about(version=True)))
finally:
    maya.standalone.uninitialize()
