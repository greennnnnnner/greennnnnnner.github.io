"""Undoable Maya API 2.0 command for hardening skin weights."""
import math

import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import maya.cmds as cmds


def maya_useNewAPI():
    pass


def _find_skin_cluster(dag_path):
    it = om.MItDependencyGraph(
        dag_path.node(), om.MFn.kSkinClusterFilter,
        om.MItDependencyGraph.kUpstream, om.MItDependencyGraph.kDepthFirst,
        om.MItDependencyGraph.kNodeLevel,
    )
    return None if it.isDone() else it.currentNode()


def _get_soft_selection():
    if not cmds.softSelect(q=True, softSelectEnabled=True):
        return None
    selection = om.MGlobal.getRichSelection().getSelection()
    for i in range(selection.length()):
        try:
            path, component = selection.getComponent(i)
        except RuntimeError:
            continue
        if component.isNull() or component.apiType() != om.MFn.kMeshVertComponent:
            continue
        if not path.hasFn(om.MFn.kMesh):
            path.extendToShape()
        if not path.hasFn(om.MFn.kMesh):
            continue
        fn = om.MFnSingleIndexedComponent(component)
        indices = list(fn.getElements())
        weights = [float(fn.weight(j).influence) if fn.hasWeights else 1.0
                   for j in range(fn.elementCount)]
        if indices:
            return path, indices, weights
    return None


def _build_surface_neighbors(path, targets):
    result = {}
    iterator = om.MItMeshVertex(path)
    for vertex in targets:
        iterator.setIndex(vertex)
        result[vertex] = list(iterator.getConnectedVertices())
    return result


def _build_volume_neighbors(path, targets, radius):
    points = om.MFnMesh(path).getPoints(om.MSpace.kWorld)
    radius_squared = radius * radius
    result = {}
    for vertex in targets:
        origin = points[vertex]
        result[vertex] = [i for i, point in enumerate(points)
                          if i != vertex and
                          (point.x - origin.x) ** 2 +
                          (point.y - origin.y) ** 2 +
                          (point.z - origin.z) ** 2 <= radius_squared]
    return result


def _apply_prune_and_normalise(row, num_inf, prune):
    values = [weight if weight >= prune else 0.0 for weight in row]
    total = sum(values)
    return [weight / total for weight in values] if total > 0.0 else values


def _compute_contrast(matrix, num_inf, targets, strengths, iterations, prune):
    current = {vertex: matrix[vertex][:] for vertex in targets}
    for _ in range(iterations):
        for vertex, strength in zip(targets, strengths):
            if strength <= 0.0:
                continue
            gamma = 1.0 + strength * 3.0
            row = [weight ** gamma if weight > 0.0 else 0.0
                   for weight in current[vertex]]
            row = _apply_prune_and_normalise(row, num_inf, prune)
            if sum(row) > 0.0:
                current[vertex] = row
    return current


def _compute_neighbor(matrix, num_inf, targets, strengths, neighbors,
                      iterations, prune):
    current = [row[:] for row in matrix]
    for _ in range(iterations):
        # Preserve the original sequential update behavior.
        for vertex, strength in zip(targets, strengths):
            if strength <= 0.0:
                continue
            row = current[vertex]
            significance = row[:]
            for neighbor in neighbors.get(vertex, ()):
                significance = [max(a, b) for a, b in
                                zip(significance, current[neighbor])]
            target = [row[i] * significance[i] for i in range(num_inf)]
            total = sum(target)
            target = [weight / total for weight in target] if total > 0.0 else row[:]
            blended = [(1.0 - strength) * a + strength * b
                       for a, b in zip(row, target)]
            blended = _apply_prune_and_normalise(blended, num_inf, prune)
            if sum(blended) > 0.0:
                current[vertex] = blended
    return current


def _component(indices):
    fn = om.MFnSingleIndexedComponent()
    component = fn.create(om.MFn.kMeshVertComponent)
    fn.addElements(indices)
    return component


class UnsmoothSkinWeightsCmd(om.MPxCommand):
    kCmdName = "unsmoothSkinWeights"
    FLAGS = (
        ("-m", "-mode", om.MSyntax.kString, "contrast"),
        ("-nm", "-neighborMode", om.MSyntax.kString, "surface"),
        ("-nr", "-neighborRadius", om.MSyntax.kDouble, 1.0),
        ("-s", "-strength", om.MSyntax.kDouble, 0.5),
        ("-i", "-iterations", om.MSyntax.kLong, 1),
        ("-pt", "-pruneThreshold", om.MSyntax.kDouble, 0.001),
    )

    def __init__(self):
        super(UnsmoothSkinWeightsCmd, self).__init__()
        self._skin_obj = None
        self._dag_path = None
        self._components = None
        self._inf_indices = None
        self._old_weights = None
        self._new_weights = None

    @staticmethod
    def creator():
        return UnsmoothSkinWeightsCmd()

    @staticmethod
    def syntax():
        syntax = om.MSyntax()
        for short, long_name, kind, _ in UnsmoothSkinWeightsCmd.FLAGS:
            syntax.addFlag(short, long_name, kind)
        syntax.useSelectionAsDefault(True)
        syntax.setObjectType(om.MSyntax.kSelectionList, 0)
        return syntax

    def isUndoable(self):
        return self._old_weights is not None

    def doIt(self, args):
        parser = om.MArgDatabase(self.syntax(), args)
        values = []
        for short, _, kind, default in self.FLAGS:
            reader = {om.MSyntax.kString: parser.flagArgumentString,
                      om.MSyntax.kDouble: parser.flagArgumentDouble,
                      om.MSyntax.kLong: parser.flagArgumentInt}[kind]
            values.append(reader(short, 0) if parser.isFlagSet(short) else default)
        mode, neighbor_mode, radius, strength, iterations, prune = values
        mode, neighbor_mode = mode.lower(), neighbor_mode.lower()
        if mode not in ("contrast", "neighbor"):
            raise RuntimeError("mode must be contrast or neighbor")
        if neighbor_mode not in ("surface", "volume"):
            raise RuntimeError("neighborMode must be surface or volume")
        if not all(math.isfinite(v) for v in (radius, strength, prune)):
            raise RuntimeError("Numeric options must be finite")
        if not 0.0 <= strength <= 1.0 or not 0.0 <= prune <= 1.0:
            raise RuntimeError("strength and pruneThreshold must be in [0, 1]")
        if radius <= 0.0 or iterations < 1:
            raise RuntimeError("neighborRadius must be positive; iterations must be >= 1")

        selection = parser.getObjectList()
        if selection.length() != 1:
            raise RuntimeError("Select one mesh or one mesh's vertices")
        path, component = selection.getComponent(0)
        if not path.hasFn(om.MFn.kMesh):
            path.extendToShape()
        if not path.hasFn(om.MFn.kMesh):
            raise RuntimeError("Selection must be a polygon mesh")
        if not component.isNull() and component.apiType() != om.MFn.kMeshVertComponent:
            raise RuntimeError("Select vertices, not edges or faces")
        count = om.MFnMesh(path).numVertices
        targets = (list(range(count)) if component.isNull() else
                   list(om.MFnSingleIndexedComponent(component).getElements()))
        soft_weights = [1.0] * len(targets)
        used_soft = False
        # Explicit object arguments must not be replaced by unrelated rich selection.
        if not component.isNull():
            soft = _get_soft_selection()
            if soft is not None:
                soft_path, soft_targets, soft_values = soft
                active = om.MGlobal.getActiveSelectionList()
                if (path.fullPathName() == soft_path.fullPathName() and
                        selection.getSelectionStrings() == active.getSelectionStrings()):
                    targets, soft_weights = soft_targets, soft_values
                    used_soft = True
        pairs = sorted(zip(targets, soft_weights))
        targets = [vertex for vertex, _ in pairs]
        soft_weights = [weight for _, weight in pairs]
        if not targets:
            raise RuntimeError("No vertices selected")
        skin = _find_skin_cluster(path)
        if skin is None:
            raise RuntimeError("No skinCluster on selected mesh")
        skin_fn = oma.MFnSkinCluster(skin)
        num_inf = len(skin_fn.influenceObjects())
        if not num_inf:
            raise RuntimeError("skinCluster has no influences")
        # getWeights/setWeights take physical indices, not sparse logical indices.
        influences = om.MIntArray(list(range(num_inf)))
        read_targets = list(range(count)) if mode == "neighbor" else targets
        flat = skin_fn.getWeights(path, _component(read_targets), influences)
        matrix = [None] * count
        for k, vertex in enumerate(read_targets):
            matrix[vertex] = list(flat[k * num_inf:(k + 1) * num_inf])
        strengths = [max(0.0, min(1.0, strength * weight)) for weight in soft_weights]
        if mode == "contrast":
            result = _compute_contrast(matrix, num_inf, targets, strengths, iterations, prune)
        else:
            neighbors = (_build_volume_neighbors(path, targets, radius)
                         if neighbor_mode == "volume" else
                         _build_surface_neighbors(path, targets))
            result = _compute_neighbor(matrix, num_inf, targets, strengths,
                                       neighbors, iterations, prune)
        self._skin_obj, self._dag_path = skin, path
        self._components = _component(targets)
        self._inf_indices = influences
        self._old_weights = om.MDoubleArray([w for v in targets for w in matrix[v]])
        self._new_weights = om.MDoubleArray([w for v in targets for w in result[v]])
        self.redoIt()
        om.MGlobal.displayInfo("unsmoothSkinWeights: {} vertices, {}{}".format(
            len(targets), mode, ", soft selection" if used_soft else ""))

    def redoIt(self):
        if self._new_weights is not None:
            oma.MFnSkinCluster(self._skin_obj).setWeights(
                self._dag_path, self._components, self._inf_indices,
                self._new_weights, normalize=False)

    def undoIt(self):
        if self._old_weights is not None:
            oma.MFnSkinCluster(self._skin_obj).setWeights(
                self._dag_path, self._components, self._inf_indices,
                self._old_weights, normalize=False)


def initializePlugin(plugin):
    om.MFnPlugin(plugin, "Custom", "1.2.1", "Any").registerCommand(
        UnsmoothSkinWeightsCmd.kCmdName, UnsmoothSkinWeightsCmd.creator,
        UnsmoothSkinWeightsCmd.syntax)


def uninitializePlugin(plugin):
    om.MFnPlugin(plugin).deregisterCommand(UnsmoothSkinWeightsCmd.kCmdName)
