"""Run with mayapy in a fresh process; creates disposable test meshes."""
from pathlib import Path
import sys
import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as cmds
sys.path.insert(0, str(Path(__file__).resolve().parent))
import skin_transfer_tool as tool


def mesh(name, joints=None, reverse=False):
    node = cmds.polyPlane(name=name, subdivisionsX=1, subdivisionsY=1)[0]
    if joints:
        skin = cmds.skinCluster(joints[::-1] if reverse else joints, node, toSelectedBones=True)[0]
        cmds.skinPercent(skin, node + ".vtx[*]", transformValue=[(joints[0], .8), (joints[1], .2)])
    return node


def weight(node, joint):
    return cmds.skinPercent(tool.get_skin_cluster(node), node + ".vtx[0]", q=True, transform=joint)


try:
    cmds.undoInfo(state=True)
    joints = []
    for x in (-1, 1):
        cmds.select(clear=True)
        joints.append(cmds.joint(position=(x, 0, 0)))
    source = mesh("source", joints)
    source2 = mesh("source2", joints, True)
    target = mesh("target", joints, True)
    target2 = mesh("target2")
    cmds.select(source)
    pairs = tool.run_pair([source], [target, target2])
    assert all(row[3] is None for row in pairs), pairs
    assert abs(weight(target, joints[0]) - .8) < 1e-6
    assert abs(weight(target2, joints[0]) - .8) < 1e-6
    assert cmds.ls(selection=True) == [source]
    cmds.undo()
    assert tool.get_skin_cluster(target2) is None
    cmds.redo()
    assert tool.get_skin_cluster(target2)
    pairs = tool.run_pair([source, source2], [target, target2], match_topology=True)
    assert all(row[3] is None for row in pairs), pairs
    for method in tool.METHODS:
        pairs = tool.run_pair([source], [target], method=method)
        assert pairs[0][3] is None, pairs
    try:
        tool.run_pair([source, source2], [target])
        raise AssertionError("Count mismatch accepted")
    except RuntimeError:
        pass
    results, seams = tool.run_combine([source, source2], [target, target2])
    assert all(row[3] is None for row in results), results
    assert seams == 4, seams
    assert not cmds.ls("stt_sourceTemp*"), "Temporary group leaked"
    assert abs(weight(source, joints[0]) - .8) < 1e-6
    assert cmds.ls(selection=True) == [source]
    # A different target skeleton must remain unchanged in target-influence mode.
    other_joints = []
    for x in (-1, 1):
        cmds.select(clear=True)
        other_joints.append(cmds.joint(position=(x, 0, 0)))
    own_target = mesh("ownTarget", other_joints)
    own_skin = tool.get_skin_cluster(own_target)
    cmds.setAttr(own_skin + ".skinningMethod", 1)
    original_infs = tool._influences(own_skin)
    result = tool.run_pair([source], [own_target], use_source_influences=False)
    assert result[0][3] is None, result
    assert tool._influences(own_skin) == original_infs
    assert cmds.getAttr(own_skin + ".skinningMethod") == 1
    results, _ = tool.run_combine([source], [target, own_target], use_source_influences=False)
    assert all(row[3] is None for row in results), results
    assert tool._influences(own_skin) == original_infs
    unbound = mesh("unbound")
    try:
        tool.run_pair([source], [unbound], use_source_influences=False)
        raise AssertionError("Unbound target accepted")
    except RuntimeError:
        pass
    # Force preparation failure and check cleanup and undo chunk closure.
    prepare = tool._prepare_combined_source
    def fail(*args):
        raise RuntimeError("Injected preparation failure")
    tool._prepare_combined_source = fail
    try:
        tool.run_combine([source], [target])
    except RuntimeError:
        pass
    finally:
        tool._prepare_combined_source = prepare
    assert not cmds.ls("stt_sourceTemp*")
    print("PASS: Pair, fan-out, repeated sources, four methods, Combine, seams, target influences, validation, cleanup, selection, undo/redo")
finally:
    maya.standalone.uninitialize()
