"""Batch skin weight transfer with Pair and Combine Sources modes."""
from collections import defaultdict
from contextlib import contextmanager
import math
import maya.cmds as cmds
import maya.api.OpenMaya as om

WINDOW_NAME = "skinTransferToolWin"
TITLE = "Skin Transfer Tool"
METHODS = ("closestPoint", "closestComponent", "rayCast", "uvSpace")

def get_skin_cluster(mesh):
    if not mesh or not cmds.objExists(mesh):
        return None
    history = cmds.listHistory(mesh, pruneDagObjects=True) or []
    skins = cmds.ls(history, type="skinCluster") or []
    return skins[0] if skins else None


def get_mesh_transform(node):
    if not node or not cmds.objExists(node):
        return None
    if cmds.nodeType(node) == "mesh":
        node = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
    if node and cmds.nodeType(node) == "transform":
        shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True, type="mesh") or []
        if len(shapes) == 1:
            return cmds.ls(node, long=True)[0]
    return None


def unique_name(base):
    name, index = base, 1
    while cmds.objExists(name):
        name = "{}{}".format(base, index)
        index += 1
    return name


def short_name(node):
    return node.split("|")[-1].split(":")[-1]


def _influences(skin):
    return cmds.ls(cmds.skinCluster(skin, q=True, influence=True) or [], long=True) or []


def _prepare_combined_source(sources, temp_group):
    influences = list(dict.fromkeys(inf for source in sources
                                   for inf in _influences(get_skin_cluster(source))))
    duplicates = []
    for source in sources:
        skin = get_skin_cluster(source)
        maximum = cmds.skinCluster(skin, q=True, maximumInfluences=True) or 5
        duplicate = cmds.duplicate(source, name=unique_name(short_name(source) + "_sttSrc"),
                                   renameChildren=True, inputConnections=False)[0]
        duplicate = cmds.parent(duplicate, temp_group)[0]
        # Bake the duplicate's evaluated geometry; source history stays intact.
        cmds.delete(duplicate, constructionHistory=True)
        duplicate_skin = cmds.skinCluster(
            influences, duplicate, toSelectedBones=True, maximumInfluences=maximum,
            removeUnusedInfluence=False, name=unique_name(short_name(duplicate) + "_skin"))[0]
        cmds.copySkinWeights(sourceSkin=skin, destinationSkin=duplicate_skin,
                             noMirror=True, surfaceAssociation="closestPoint",
                             influenceAssociation=["name"])
        duplicates.append(duplicate)
    if len(duplicates) == 1:
        combined = duplicates[0]
    else:
        result = cmds.polyUniteSkinned(duplicates, constructionHistory=False,
                                      mergeUVSets=1) or []
        if not result:
            raise RuntimeError("Could not combine source meshes")
        combined = cmds.rename(result[0], unique_name("stt_combinedSource"))
        combined = cmds.parent(combined, temp_group)[0]
    skin = get_skin_cluster(combined)
    if not skin:
        raise RuntimeError("Combined source has no skinCluster")
    return combined, skin, influences


def _get_world_positions(mesh):
    selection = om.MSelectionList()
    selection.add(mesh)
    path = selection.getDagPath(0)
    path.extendToShape()
    return [(p.x, p.y, p.z) for p in om.MFnMesh(path).getPoints(om.MSpace.kWorld)]


def _nearest_seam_matches(positions, master, threshold):
    cell_size = max(threshold * 2.0, 1e-6)
    def cell(point):
        return tuple(math.floor(value / cell_size) for value in point)
    grid = defaultdict(list)
    for mesh, points in positions.items():
        if mesh != master:
            for index, point in enumerate(points):
                grid[cell(point)].append((mesh, index))
    matches = {}
    for master_index, point in enumerate(positions[master]):
        key = cell(point)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for mesh, index in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                        distance = sum((a - b) ** 2 for a, b in zip(point, positions[mesh][index]))
                        previous = matches.get((mesh, index))
                        if distance <= threshold ** 2 and (previous is None or distance < previous[0]):
                            matches[(mesh, index)] = (distance, master_index)
    return matches


def match_seam_weights(meshes, master, threshold=0.001):
    """Copy the nearest master vertex's weights to targets within threshold."""
    if not math.isfinite(threshold) or threshold < 0:
        raise RuntimeError("Seam threshold must be finite and non-negative")
    if len(meshes) < 2 or master not in meshes:
        return 0
    matches = _nearest_seam_matches({mesh: _get_world_positions(mesh) for mesh in meshes},
                                    master, threshold)
    skins = {mesh: get_skin_cluster(mesh) for mesh in meshes}
    if not all(skins.values()):
        raise RuntimeError("Seam matching requires skinned meshes")
    influences = _influences(skins[master])
    cache = {}
    processed = 0
    for (mesh, index), (_, master_index) in matches.items():
        if master_index not in cache:
            values = cmds.skinPercent(skins[master], "{}.vtx[{}]".format(master, master_index),
                                       q=True, value=True) or []
            weights = {inf: value for inf, value in zip(influences, values) if value > 1e-8}
            total = sum(weights.values())
            cache[master_index] = {inf: value / total for inf, value in weights.items()} if total else {}
        weights = cache[master_index]
        if not weights:
            continue
        existing = set(_influences(skins[mesh]))
        for influence in weights:
            if influence not in existing:
                cmds.skinCluster(skins[mesh], edit=True, addInfluence=influence,
                                 lockWeights=False, weight=0.0)
        cmds.skinPercent(skins[mesh], "{}.vtx[{}]".format(mesh, index),
                         transformValue=list(weights.items()), zeroRemainingInfluences=True)
        processed += 1
    return processed


def _resolve(nodes, unique=False):
    meshes = []
    for node in nodes:
        mesh = get_mesh_transform(node)
        if mesh is None:
            raise RuntimeError("Expected a transform with one polygon mesh: {}".format(node))
        if not unique or mesh not in meshes:
            meshes.append(mesh)
    return meshes


def _validate(sources, destinations, method, use_source_influences):
    if not sources or not destinations:
        raise RuntimeError("Add at least one source and one destination")
    if method not in METHODS:
        raise RuntimeError("Unknown surface association: {}".format(method))
    sources = _resolve(sources)
    destinations = _resolve(destinations, unique=True)
    if set(sources) & set(destinations):
        raise RuntimeError("A mesh cannot be both a source and a destination")
    for mesh in sources:
        if not get_skin_cluster(mesh):
            raise RuntimeError("Source is not skinned: {}".format(mesh))
    if not use_source_influences:
        for mesh in destinations:
            if not get_skin_cluster(mesh):
                raise RuntimeError("Use target's own influences requires a skinCluster: {}".format(mesh))
    return sources, destinations


@contextmanager
def _operation(name):
    selection = cmds.ls(selection=True, long=True) or []
    cmds.undoInfo(openChunk=True, chunkName=name)
    try:
        yield
    finally:
        try:
            cmds.select([node for node in selection if cmds.objExists(node)], replace=True)
        finally:
            cmds.undoInfo(closeChunk=True)


def _ensure_destination_skincluster(destination, influences, maximum=5, method=0,
                                    add_missing=True):
    skin = get_skin_cluster(destination)
    if not add_missing:
        if not skin:
            raise RuntimeError("Target has no skinCluster: {}".format(destination))
        return skin
    if not influences:
        raise RuntimeError("Source has no influences")
    if skin is None:
        skin = cmds.skinCluster(influences, destination, toSelectedBones=True,
                                maximumInfluences=maximum, removeUnusedInfluence=False,
                                name=unique_name(short_name(destination) + "_skin"))[0]
    else:
        existing = set(_influences(skin))
        for influence in influences:
            if influence not in existing:
                cmds.skinCluster(skin, edit=True, addInfluence=influence,
                                 lockWeights=False, weight=0.0)
        # Changing maximumInfluences with skinCluster -edit can reassign weights.
        cmds.setAttr(skin + ".maxInfluences", maximum)
    cmds.setAttr(skin + ".skinningMethod", method)
    return skin


def _run_copy(source, source_skin, target, target_skin, method,
              use_source_influences=True, match_topology=False):
    use_topology = match_topology and cmds.polyEvaluate(source, vertex=True) == cmds.polyEvaluate(target, vertex=True)
    if match_topology and not use_topology:
        cmds.warning("Vertex counts differ; using {} for {}".format(method, target))
    actual = "closestComponent" if use_topology else method
    # Match joint names before falling back to labels and joint positions.
    association = ["name", "label", "closestJoint"] if use_source_influences else ["label", "closestJoint"]
    options = dict(sourceSkin=source_skin, destinationSkin=target_skin,
                   noMirror=True, influenceAssociation=association)
    if actual == "uvSpace":
        source_uv = cmds.polyUVSet(source, q=True, currentUVSet=True) or []
        target_uv = cmds.polyUVSet(target, q=True, currentUVSet=True) or []
        if not source_uv or not target_uv:
            raise RuntimeError("UV Space requires UV sets on both meshes")
        options["uvSpace"] = [source_uv[0], target_uv[0]]
    else:
        options["surfaceAssociation"] = actual
    cmds.copySkinWeights(**options)
    return actual


def copy_one(source, target, method="closestPoint", match_topology=False,
             use_source_influences=True):
    sources, targets = _validate([source], [target], method, use_source_influences)
    source, target = sources[0], targets[0]
    source_skin = get_skin_cluster(source)
    maximum = cmds.getAttr(source_skin + ".maxInfluences") or 5
    skinning_method = cmds.getAttr(source_skin + ".skinningMethod")
    target_skin = _ensure_destination_skincluster(
        target, _influences(source_skin), maximum, skinning_method, use_source_influences)
    return _run_copy(source, source_skin, target, target_skin, method,
                     use_source_influences, match_topology)


def run_pair(sources, destinations, method="closestPoint", match_topology=False,
             use_source_influences=True):
    """Pair rows by index, or send a single source to every destination."""
    sources, destinations = _validate(sources, destinations, method, use_source_influences)
    if len(sources) == 1:
        pairs = [(sources[0], target) for target in destinations]
    elif len(sources) == len(destinations):
        pairs = list(zip(sources, destinations))
    else:
        raise RuntimeError("Use equal row counts or one source. Duplicate a source row for repeated pairs.")
    results = []
    with _operation("SkinTransfer_Pair"):
        for source, target in pairs:
            try:
                actual = copy_one(source, target, method, match_topology, use_source_influences)
                results.append((source, target, actual, None))
            except Exception as error:
                cmds.warning("{} -> {} failed: {}".format(source, target, error))
                results.append((source, target, None, str(error)))
    return results


def run_combine(sources, destinations, method="closestPoint", match_topology=False,
                handle_seams=True, seam_threshold=0.001, seam_master=None,
                use_source_influences=True):
    """Combine sources temporarily, then transfer to each destination."""
    sources, destinations = _validate(sources, destinations, method, use_source_influences)
    sources = list(dict.fromkeys(sources))
    if not math.isfinite(seam_threshold) or seam_threshold < 0:
        raise RuntimeError("Seam threshold must be finite and non-negative")
    master = get_mesh_transform(seam_master) if seam_master else destinations[0]
    if master not in destinations:
        raise RuntimeError("Seam master must be a destination")
    results, seam_count = [], 0
    with _operation("SkinTransfer_Combine"):
        temp_group = cmds.group(empty=True, name=unique_name("stt_sourceTemp"))
        try:
            combined, combined_skin, influences = _prepare_combined_source(sources, temp_group)
            maximum = max(cmds.getAttr(get_skin_cluster(s) + ".maxInfluences") or 5 for s in sources)
            skinning_method = max(cmds.getAttr(get_skin_cluster(s) + ".skinningMethod") for s in sources)
            for target in destinations:
                try:
                    skin = _ensure_destination_skincluster(target, influences, maximum,
                                                          skinning_method, use_source_influences)
                    actual = _run_copy(combined, combined_skin, target, skin, method,
                                       use_source_influences, match_topology)
                    results.append((target, skin, actual, None))
                except Exception as error:
                    cmds.warning("Transfer to {} failed: {}".format(target, error))
                    results.append((target, None, method, str(error)))
            successful = [row[0] for row in results if row[3] is None]
            if handle_seams and len(successful) > 1 and master in successful:
                seam_targets = successful
                if not use_source_influences:
                    # Exact master weights need matching joints; never add joints in target mode.
                    master_influences = set(_influences(get_skin_cluster(master)))
                    seam_targets = [target for target in successful
                                    if master_influences <= set(_influences(get_skin_cluster(target)))]
                    if len(seam_targets) != len(successful):
                        cmds.warning("Skipped seam targets missing the master's influences; target binds were preserved")
                seam_count = match_seam_weights(seam_targets, master, seam_threshold)
        finally:
            if cmds.objExists(temp_group):
                cmds.delete(temp_group)
    return results, seam_count


class SkinTransferUI:
    def show(self):
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)
        window = cmds.window(WINDOW_NAME, title=TITLE, widthHeight=(620, 760), sizeable=True)
        cmds.scrollLayout(childResizable=True)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnAttach=("both", 10))
        self.source_list = self._mesh_list("Sources (skinned meshes)", True)
        self.dest_list = self._mesh_list("Destinations", False)
        self.mode_radio = cmds.radioButtonGrp(numberOfRadioButtons=2,
            labelArray2=["Pair", "Combine Sources"], select=1,
            changeCommand=lambda *_: self._update_seam_enable())
        self.inf_radio = cmds.radioButtonGrp(numberOfRadioButtons=2,
            labelArray2=["Use source influences", "Use target's own influences"], select=1)
        self.method_menu = cmds.optionMenu(label="Surface association")
        for method in METHODS:
            cmds.menuItem(label=method)
        self.topo_check = cmds.checkBox(label="Match topology (equal vertex counts: closestComponent)", value=False)
        cmds.text(label="Topology matching uses spatial proximity, not vertex index order.", align="left")
        self.seam_check = cmds.checkBox(label="Paste master weights onto overlapping vertices", value=True)
        self.seam_field = cmds.floatFieldGrp(label="Seam threshold", numberOfFields=1,
                                            value1=0.001, precision=5)
        self.master_menu = cmds.optionMenu(label="Seam master")
        self._refresh_master_menu()
        self._update_seam_enable()
        cmds.text(label="Pair: equal row counts, or one source to all destinations.", align="left")
        cmds.text(label="Combine: temporary merged source; seam matching requires 2+ destinations.", align="left")
        cmds.button(label="Transfer Skin", height=42, command=lambda *_: self._do_copy())
        cmds.showWindow(window)
        return self

    def _mesh_list(self, label, require_skin):
        cmds.frameLayout(label=label, collapsable=False, marginWidth=6, marginHeight=6)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        control = cmds.textScrollList(height=135, allowMultiSelection=True)
        cmds.rowLayout(numberOfColumns=4 if require_skin else 3)
        cmds.button(label="Add Selected", command=lambda *_: self._add(control, require_skin))
        cmds.button(label="Remove", command=lambda *_: self._remove(control))
        cmds.button(label="Clear", command=lambda *_: self._clear(control))
        if require_skin:
            cmds.button(label="Duplicate Row", command=lambda *_: self._duplicate_rows(control))
        for _ in range(3):
            cmds.setParent("..")
        return control

    def _add(self, control, require_skin):
        existing = cmds.textScrollList(control, q=True, allItems=True) or []
        for node in cmds.ls(selection=True, long=True) or []:
            mesh = get_mesh_transform(node)
            if not mesh or (require_skin and not get_skin_cluster(mesh)):
                cmds.warning("Skipping invalid {}mesh: {}".format("skinned " if require_skin else "", node))
                continue
            if require_skin or mesh not in existing:
                cmds.textScrollList(control, edit=True, append=mesh)
                existing.append(mesh)
        self._refresh_master_menu()

    def _remove(self, control):
        indices = cmds.textScrollList(control, q=True, selectIndexedItem=True) or []
        for index in sorted(indices, reverse=True):
            cmds.textScrollList(control, edit=True, removeIndexedItem=index)
        self._refresh_master_menu()

    def _clear(self, control):
        cmds.textScrollList(control, edit=True, removeAll=True)
        self._refresh_master_menu()

    def _duplicate_rows(self, control):
        items = cmds.textScrollList(control, q=True, allItems=True) or []
        indices = cmds.textScrollList(control, q=True, selectIndexedItem=True) or []
        if not indices:
            cmds.warning("Select a source row to duplicate")
            return
        cmds.textScrollList(control, edit=True, removeAll=True)
        for index, item in enumerate(items, 1):
            cmds.textScrollList(control, edit=True, append=item)
            if index in indices:
                cmds.textScrollList(control, edit=True, append=item)

    def _refresh_master_menu(self):
        if not hasattr(self, "master_menu"):
            return
        items = cmds.optionMenu(self.master_menu, q=True, itemListLong=True) or []
        previous = cmds.optionMenu(self.master_menu, q=True, value=True) if items else None
        for item in items:
            cmds.deleteUI(item)
        destinations = cmds.textScrollList(self.dest_list, q=True, allItems=True) or []
        for target in destinations or ["(No destinations)"]:
            cmds.menuItem(label=target, parent=self.master_menu)
        if previous in destinations:
            cmds.optionMenu(self.master_menu, edit=True, value=previous)

    def _update_seam_enable(self):
        enabled = cmds.radioButtonGrp(self.mode_radio, q=True, select=True) == 2
        cmds.checkBox(self.seam_check, edit=True, enable=enabled)
        cmds.floatFieldGrp(self.seam_field, edit=True, enable=enabled)
        cmds.optionMenu(self.master_menu, edit=True, enable=enabled)

    def _do_copy(self):
        sources = cmds.textScrollList(self.source_list, q=True, allItems=True) or []
        destinations = cmds.textScrollList(self.dest_list, q=True, allItems=True) or []
        options = dict(method=cmds.optionMenu(self.method_menu, q=True, value=True),
                       match_topology=cmds.checkBox(self.topo_check, q=True, value=True),
                       use_source_influences=cmds.radioButtonGrp(self.inf_radio, q=True, select=True) == 1)
        try:
            seams = 0
            if cmds.radioButtonGrp(self.mode_radio, q=True, select=True) == 1:
                results = run_pair(sources, destinations, **options)
            else:
                results, seams = run_combine(sources, destinations,
                    handle_seams=cmds.checkBox(self.seam_check, q=True, value=True),
                    seam_threshold=cmds.floatFieldGrp(self.seam_field, q=True, value1=True),
                    seam_master=cmds.optionMenu(self.master_menu, q=True, value=True) if destinations else None,
                    **options)
            success = sum(row[3] is None for row in results)
            message = "{} / {} transfers succeeded; {} seam vertices matched.".format(success, len(results), seams)
            cmds.inViewMessage(amg=message, pos="midCenter", fade=True)
            print("[SkinTransferTool] " + message)
            for row in results:
                print(row)
        except Exception as error:
            cmds.confirmDialog(title="Transfer failed", message=str(error), button=["OK"])


def show():
    return SkinTransferUI().show()


if __name__ == "__main__":
    show()
