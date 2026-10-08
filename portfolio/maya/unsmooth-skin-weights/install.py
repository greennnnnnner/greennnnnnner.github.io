"""Install from Maya's Python Script Editor using runpy.run_path()."""
from pathlib import Path
import importlib
import shutil
import sys

import maya.cmds as cmds


def install():
    root = Path(__file__).resolve().parent
    plugin_source = root / "plug-ins" / "unsmoothSkinWeights.py"
    ui_source = root / "scripts" / "unsmoothSkinWeightsUI.py"
    for source in (plugin_source, ui_source):
        if not source.is_file():
            raise RuntimeError("Missing file: {}".format(source))
    try:
        loaded = cmds.pluginInfo("unsmoothSkinWeights", q=True, loaded=True)
    except RuntimeError:
        loaded = False
    if loaded:
        raise RuntimeError("Unsmooth Skin Weights is loaded. Restart Maya before installing an update.")
    user_directory = Path(cmds.internalVar(userAppDir=True))
    plugin_directory = user_directory / str(cmds.about(version=True)) / "plug-ins"
    scripts_directory = user_directory / "scripts"
    for directory in (plugin_directory, scripts_directory):
        directory.mkdir(parents=True, exist_ok=True)
    for source, destination in ((plugin_source, plugin_directory / plugin_source.name),
                                (ui_source, scripts_directory / ui_source.name)):
        if source.resolve() != destination.resolve():
            if destination.exists():
                backup = destination.with_name(destination.name + ".bak")
                index = 1
                while backup.exists():
                    backup = destination.with_name(destination.name + ".bak.{}".format(index))
                    index += 1
                shutil.copy2(destination, backup)
            shutil.copy2(source, destination)
    if str(scripts_directory) not in sys.path:
        sys.path.insert(0, str(scripts_directory))
    cmds.loadPlugin(str(plugin_directory / plugin_source.name))
    importlib.invalidate_caches()
    ui = importlib.import_module("unsmoothSkinWeightsUI")
    importlib.reload(ui).show_ui()
    print("Installed Unsmooth Skin Weights to {}".format(user_directory))


if __name__ == "__main__":
    install()
