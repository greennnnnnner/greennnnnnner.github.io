# Unreal Scripts

## Transfer Materials by Slot Name

[Python script](transfer_materials_by_slot_name.py)

Copies material assignments from a source mesh to a target mesh by `material_slot_name`. Works with static and skeletal mesh assets, including mixed pairs. Unmatched target slots stay unchanged. The target is saved after a successful transfer.

### Run in the Unreal Editor

Enable Python Editor Script Plugin and Editor Scripting Utilities. Download the script to your project's `Content/Python` folder.

For a quick transfer, select exactly two mesh assets in the Content Browser and run this in the Python console:

```python
import runpy
runpy.run_path("C:/path/to/transfer_materials_by_slot_name.py", run_name="__main__")
```

The first asset returned by the selection API is the source; the second is the target. Selection order is not guaranteed by the API. For a reliable source and target, use explicit asset paths:

```python
import unreal
from transfer_materials_by_slot_name import transfer_materials_by_slot_name

source = unreal.load_asset("/Game/Characters/SK_A")
target = unreal.load_asset("/Game/Characters/SK_B")
transfer_materials_by_slot_name(source, target)
```

### Matching rules

- Uses the displayed slot name, not the imported slot name or slot index.
- Skips source slots with no assigned material or no name.
- If source slot names repeat, the last assigned material wins.
- Keeps the target's slot order and other slot settings.
- Does not create slots or copy mesh geometry.

### Validation

Python syntax checked. Not yet tested inside the Unreal Editor; engine-version compatibility remains unverified. Static meshes use `static_materials`; skeletal meshes use `materials`. The modified array is written back before saving.

API references: [StaticMesh](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/StaticMesh?application_version=5.5), [SkeletalMesh](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/SkeletalMesh?application_version=5.5), [EditorAssetLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/EditorAssetLibrary?application_version=5.5).

[Back to homepage](../README.md)
