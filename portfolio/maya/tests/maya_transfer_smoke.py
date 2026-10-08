"""Run in a fresh mayapy process; creates its own test meshes."""
from pathlib import Path
import sys
import maya.standalone

maya.standalone.initialize(name="python")
import maya.cmds as cmds

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "multi-weight-transfer/scripts"))
import multi_weight_transfer as mwt


def values(skin, mesh):
    return cmds.skinPercent(skin, mesh + ".vtx[0]", q=True, value=True)


try:
    cmds.undoInfo(state=True)
    joints = []
    for x in (-1, 1):
        cmds.select(clear=True)
        joints.append(cmds.joint(position=(x, 0, 0)))
    source = cmds.polyPlane(name="sourceA", subdivisionsX=1, subdivisionsY=1)[0]
    source2 = cmds.polyPlane(name="sourceB", subdivisionsX=1, subdivisionsY=1)[0]
    cmds.move(2, 0, 0, source2)
    skin = cmds.skinCluster(joints, source, toSelectedBones=True)[0]
    skin2 = cmds.skinCluster(joints[::-1], source2, toSelectedBones=True)[0]
    for sc, mesh in ((skin, source), (skin2, source2)):
        cmds.skinPercent(sc, mesh + ".vtx[*]", transformValue=[(joints[0], 0.8), (joints[1], 0.2)])
    target = cmds.polyPlane(name="targetA", subdivisionsX=1, subdivisionsY=1)[0]
    target2 = cmds.polyPlane(name="targetB", subdivisionsX=1, subdivisionsY=1)[0]
    target_skin = cmds.skinCluster(joints[::-1], target, toSelectedBones=True)[0]
    cmds.skinPercent(target_skin, target + ".vtx[*]", transformValue=[(joints[0], 0.1), (joints[1], 0.9)])
    original = values(target_skin, target)
    source_weights = values(skin, source)
    cmds.select(source)
    result = mwt.transfer_weights([source, source2], [target, target2], seam_threshold=0.001)
    assert result["seam_pairs"] == 4, result
    actual = cmds.skinPercent(target_skin, target + ".vtx[0]", q=True, transform=joints[0])
    assert abs(actual - 0.8) < 1e-6, actual
    assert values(skin, source) == source_weights
    assert not cmds.ls("mwt_sourceTemp*"), "Temporary group was left in scene"
    assert cmds.ls(selection=True) == [source]
    cmds.undo()
    assert all(abs(a - b) < 1e-6 for a, b in zip(values(target_skin, target), original))
    assert mwt.get_skin_cluster(target2) is None
    cmds.redo()
    assert mwt.get_skin_cluster(target2)
    for method in ("closestComponent", "rayCast", "uvSpace"):
        mwt.transfer_weights([source], [target], method=method, handle_seams=False)
        total = sum(values(target_skin, target))
        assert abs(total - 1) < 1e-6, (method, total)
    print("PASS: Maya 2025: multiple sources and targets, influence name matching, seams, cleanup, selection, undo/redo, four methods")
finally:
    maya.standalone.uninitialize()
