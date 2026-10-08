"""Window for the unsmoothSkinWeights command."""

import maya.cmds as cmds


_PLUGIN_NAME = "unsmoothSkinWeights"
_UI_WIN      = "unsmoothSkinWeightsWin"


def _ensure_plugin_loaded():
    if cmds.pluginInfo(_PLUGIN_NAME, q=True, loaded=True):
        return True
    try:
        cmds.loadPlugin(_PLUGIN_NAME)
        return True
    except Exception as e:
        cmds.warning(
            "Could not load '{0}' plug-in. Load it manually via "
            "Window > Settings/Preferences > Plug-in Manager. ({1})".format(
                _PLUGIN_NAME, e))
        return False


def show_ui():
    if not _ensure_plugin_loaded():
        return

    if cmds.window(_UI_WIN, exists=True):
        cmds.deleteUI(_UI_WIN)

    win = cmds.window(_UI_WIN, title="Unsmooth Skin Weights",
                      widthHeight=(400, 320), sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6,
                      columnAttach=("both", 10))

    cmds.text(label="Sharpen weights on the selected mesh or vertices.", align="left")
    cmds.text(label="Press B to enable soft selection.",
              align="left")
    cmds.separator(height=6, style="in")

    col_widths = [(1, 110), (2, 60), (3, 180)]

    ctrl_mode = cmds.optionMenuGrp(
        label="Mode", columnWidth=[(1, 110), (2, 200)],
        annotation=(
            "Contrast: sharpen each vertex independently.\n"
            "Neighbor: use nearby influence maxima to mask weights."))
    cmds.menuItem(label="Contrast")
    cmds.menuItem(label="Neighbor")

    ctrl_nmode = cmds.optionMenuGrp(
        label="Neighbor mode", columnWidth=[(1, 110), (2, 200)],
        annotation=(
            "Surface: edge-connected verts (topology).\n"
            "Volume:  verts within Radius world units (ignores topology)."))
    cmds.menuItem(label="Surface")
    cmds.menuItem(label="Volume")

    ctrl_radius = cmds.floatSliderGrp(
        label="Radius (world)", field=True,
        minValue=0.01, maxValue=10.0,
        fieldMinValue=0.001, fieldMaxValue=10000.0,
        value=1.0, precision=3, columnWidth=col_widths)

    cmds.separator(height=6, style="in")

    ctrl_strength = cmds.floatSliderGrp(
        label="Strength", field=True,
        minValue=0.0, maxValue=1.0,
        fieldMinValue=0.0, fieldMaxValue=1.0,
        value=0.5, precision=3, columnWidth=col_widths)

    ctrl_iters = cmds.intSliderGrp(
        label="Iterations", field=True,
        minValue=1, maxValue=10,
        fieldMinValue=1, fieldMaxValue=100,
        value=1, columnWidth=col_widths)

    ctrl_prune = cmds.floatSliderGrp(
        label="Prune", field=True,
        minValue=0.0, maxValue=0.05,
        fieldMinValue=0.0, fieldMaxValue=1.0,
        value=0.001, precision=4, columnWidth=col_widths)

    def _refresh_enable(*_):
        m = cmds.optionMenuGrp(ctrl_mode, q=True, value=True)
        n = cmds.optionMenuGrp(ctrl_nmode, q=True, value=True)
        is_neighbor = (m == "Neighbor")
        is_volume = is_neighbor and (n == "Volume")
        cmds.optionMenuGrp(ctrl_nmode, e=True, enable=is_neighbor)
        cmds.floatSliderGrp(ctrl_radius, e=True, enable=is_volume)

    cmds.optionMenuGrp(ctrl_mode, e=True, changeCommand=_refresh_enable)
    cmds.optionMenuGrp(ctrl_nmode, e=True, changeCommand=_refresh_enable)
    _refresh_enable()

    def _apply(*_):
        m = cmds.optionMenuGrp(ctrl_mode, q=True, value=True).lower()
        n = cmds.optionMenuGrp(ctrl_nmode, q=True, value=True).lower()
        r = cmds.floatSliderGrp(ctrl_radius, q=True, value=True)
        s = cmds.floatSliderGrp(ctrl_strength, q=True, value=True)
        it = cmds.intSliderGrp(ctrl_iters, q=True, value=True)
        p = cmds.floatSliderGrp(ctrl_prune, q=True, value=True)
        try:
            cmds.unsmoothSkinWeights(
                mode=m, neighborMode=n, neighborRadius=r,
                strength=s, iterations=it, pruneThreshold=p,
            )
        except RuntimeError as e:
            cmds.warning(str(e))

    cmds.separator(height=6, style="in")
    cmds.button(label="Apply", height=34, command=_apply)
    cmds.showWindow(win)
