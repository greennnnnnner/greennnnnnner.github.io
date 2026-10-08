"""Transfer skin weights from multiple source meshes to multiple targets."""
from collections import defaultdict
import math

import maya.cmds as cmds
import maya.api.OpenMaya as om

WINDOW_NAME = "multiWeightTransferWin"
TITLE = "Multi Weight Transfer"
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
        duplicate = cmds.duplicate(source, name=unique_name(short_name(source) + "_mwtSrc"),
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
        combined = cmds.rename(result[0], unique_name("mwt_combinedSource"))
        combined = cmds.parent(combined, temp_group)[0]
    skin = get_skin_cluster(combined)
    if not skin:
        raise RuntimeError("Combined source has no skinCluster")
    return combined, skin, influences


def _ensure_destination_skincluster(destination, influences, maximum=5):
    skin = get_skin_cluster(destination)
    if skin is None:
        return cmds.skinCluster(influences, destination, toSelectedBones=True,
                                maximumInfluences=maximum, removeUnusedInfluence=False,
                                name=unique_name(short_name(destination) + "_skin"))[0]
    existing = set(_influences(skin))
    for influence in influences:
        if influence not in existing:
            cmds.skinCluster(skin, edit=True, addInfluence=influence,
                             lockWeights=False, weight=0.0)
    return skin


def transfer_weights(sources, destinations, method="closestPoint", handle_seams=True,
                     seam_threshold=0.001, seam_master=None):
    """Copy weights; optionally copy seam weights from one target to the others.

    Each source must be skinned. Destinations may be unskinned. A failed
    operation may leave partial destination edits; use Undo to restore them.
    """
    if not sources or not destinations:
        raise RuntimeError("Add at least one source and one destination")
    if method not in METHODS:
        raise RuntimeError("Unknown transfer method: {}".format(method))
    if not math.isfinite(seam_threshold) or seam_threshold < 0:
        raise RuntimeError("Seam threshold must be finite and non-negative")
    def resolve(nodes):
        result = []
        for node in nodes:
            mesh = get_mesh_transform(node)
            if mesh is None:
                raise RuntimeError("Expected a transform with one polygon mesh: {}".format(node))
            if mesh not in result:
                result.append(mesh)
        return result
    sources, destinations = resolve(sources), resolve(destinations)
    if set(sources) & set(destinations):
        raise RuntimeError("Sources and destinations must be different meshes")
    for source in sources:
        if get_skin_cluster(source) is None:
            raise RuntimeError("Source is not skinned: {}".format(source))
    master = get_mesh_transform(seam_master) if seam_master else destinations[0]
    if master not in destinations:
        raise RuntimeError("Seam master must be one of the destinations")
    previous_selection = cmds.ls(selection=True, long=True) or []
    cmds.undoInfo(openChunk=True, chunkName="MultiWeightTransfer")
    temp_group = None
    try:
        temp_group = cmds.group(empty=True, name=unique_name("mwt_sourceTemp"))
        combined, combined_skin, influences = _prepare_combined_source(sources, temp_group)
        maximum = max(cmds.skinCluster(get_skin_cluster(s), q=True, maximumInfluences=True)
                      or 5 for s in sources)
        for destination in destinations:
            skin = _ensure_destination_skincluster(destination, influences, maximum)
            options = dict(sourceSkin=combined_skin, destinationSkin=skin,
                           noMirror=True, influenceAssociation=["name"])
            if method == "uvSpace":
                source_uv = cmds.polyUVSet(combined, q=True, currentUVSet=True) or []
                target_uv = cmds.polyUVSet(destination, q=True, currentUVSet=True) or []
                if not source_uv or not target_uv:
                    raise RuntimeError("UV Space requires UV sets on source and destination")
                options["uvSpace"] = [source_uv[0], target_uv[0]]
            else:
                options["surfaceAssociation"] = method
            cmds.copySkinWeights(**options)
        seams = (match_seam_weights(destinations, master, seam_threshold)
                 if handle_seams and len(destinations) > 1 else 0)
        return {"destinations": destinations, "seam_pairs": seams}
    finally:
        try:
            if temp_group and cmds.objExists(temp_group):
                cmds.delete(temp_group)
            cmds.select([node for node in previous_selection if cmds.objExists(node)], replace=True)
        finally:
            cmds.undoInfo(closeChunk=True)


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


class MultiWeightTransferUI:
    def show(self):
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)
        window = cmds.window(WINDOW_NAME, title=TITLE, widthHeight=(560, 640), sizeable=True)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnAttach=("both", 10))
        self.source_list = self._mesh_list("Sources (skinned meshes)", True)
        self.dest_list = self._mesh_list("Destinations", False)
        cmds.separator(style="in", height=10)
        self.method_menu = cmds.optionMenu(label="Surface association")
        for method in METHODS:
            cmds.menuItem(label=method)
        self.seam_check = cmds.checkBox(label="Match seam weights", value=True)
        self.seam_field = cmds.floatFieldGrp(label="Seam threshold", value1=0.001,
                                            precision=5, numberOfFields=1)
        self.master_menu = cmds.optionMenu(label="Seam master")
        self._refresh_master_menu()
        cmds.text(label="Seam vertices copy weights from the master destination.", align="left")
        cmds.text(label="All meshes in both lists are processed.", align="left")
        cmds.button(label="Transfer Weights", height=40, command=lambda *_: self._do_transfer())
        cmds.showWindow(window)
        return self

    def _mesh_list(self, label, require_skin):
        cmds.frameLayout(label=label, collapsable=False, marginWidth=6, marginHeight=6)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        control = cmds.textScrollList(height=140, allowMultiSelection=True)
        cmds.rowLayout(numberOfColumns=3, columnWidth3=(175, 175, 175))
        cmds.button(label="Add Selected", command=lambda *_: self._add(control, require_skin))
        cmds.button(label="Remove", command=lambda *_: self._remove(control))
        cmds.button(label="Clear", command=lambda *_: self._clear(control))
        for _ in range(3):
            cmds.setParent("..")
        return control

    def _add(self, control, require_skin):
        existing = cmds.textScrollList(control, q=True, allItems=True) or []
        for node in cmds.ls(selection=True, long=True) or []:
            mesh = get_mesh_transform(node)
            if not mesh or (require_skin and not get_skin_cluster(mesh)):
                cmds.warning("Select {}polygon meshes: {}".format("skinned " if require_skin else "", node))
                continue
            if mesh not in existing:
                cmds.textScrollList(control, edit=True, append=mesh)
                existing.append(mesh)
        self._refresh_master_menu()

    def _remove(self, control):
        for item in cmds.textScrollList(control, q=True, selectItem=True) or []:
            cmds.textScrollList(control, edit=True, removeItem=item)
        self._refresh_master_menu()

    def _clear(self, control):
        cmds.textScrollList(control, edit=True, removeAll=True)
        self._refresh_master_menu()

    def _refresh_master_menu(self):
        if not hasattr(self, "master_menu"):
            return
        items = cmds.optionMenu(self.master_menu, q=True, itemListLong=True) or []
        previous = cmds.optionMenu(self.master_menu, q=True, value=True) if items else None
        for item in items:
            cmds.deleteUI(item)
        destinations = cmds.textScrollList(self.dest_list, q=True, allItems=True) or []
        for destination in destinations or ["(No destinations)"]:
            cmds.menuItem(label=destination, parent=self.master_menu)
        if previous in destinations:
            cmds.optionMenu(self.master_menu, edit=True, value=previous)

    def _do_transfer(self):
        sources = cmds.textScrollList(self.source_list, q=True, allItems=True) or []
        destinations = cmds.textScrollList(self.dest_list, q=True, allItems=True) or []
        try:
            result = transfer_weights(
                sources, destinations, method=cmds.optionMenu(self.method_menu, q=True, value=True),
                handle_seams=cmds.checkBox(self.seam_check, q=True, value=True),
                seam_threshold=cmds.floatFieldGrp(self.seam_field, q=True, value1=True),
                seam_master=cmds.optionMenu(self.master_menu, q=True, value=True) if destinations else None)
            message = "Transferred weights to {} meshes; matched {} seam vertices.".format(
                len(result["destinations"]), result["seam_pairs"])
            cmds.inViewMessage(amg=message, pos="midCenter", fade=True)
            print(message)
        except Exception as error:
            cmds.confirmDialog(title="Transfer failed", message=str(error), button=["OK"])


def show():
    return MultiWeightTransferUI().show()


if __name__ == "__main__":
    show()
