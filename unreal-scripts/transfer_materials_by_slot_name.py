"""Copy mesh material assignments by slot name in the Unreal Editor."""

import unreal


def _material_property(asset):
    return "static_materials" if isinstance(asset, unreal.StaticMesh) else "materials"


def transfer_materials_by_slot_name(source_asset=None, target_asset=None):
    """Copy matching slots and save the target. Return the number updated."""
    # Use the selected assets when no explicit source and target are provided.
    if source_asset is None and target_asset is None:
        selected_assets = unreal.EditorUtilityLibrary.get_selected_assets()
        if len(selected_assets) != 2:
            unreal.log_warning("Select exactly two mesh assets: source and target.")
            return 0
        source_asset, target_asset = selected_assets

    mesh_types = (unreal.StaticMesh, unreal.SkeletalMesh)
    if not all(isinstance(asset, mesh_types) for asset in (source_asset, target_asset)):
        unreal.log_warning("Both assets must be StaticMesh or SkeletalMesh assets.")
        return 0
    if source_asset == target_asset:
        unreal.log_warning("Source and target must be different assets.")
        return 0

    unreal.log("Source: {} | Target: {}".format(
        source_asset.get_path_name(), target_asset.get_path_name()))

    # Build a lookup from the source's assigned, named material slots.
    source_materials = source_asset.get_editor_property(_material_property(source_asset))
    source_material_dict = {}
    for slot in source_materials:
        slot_name = slot.get_editor_property("material_slot_name")
        material = slot.get_editor_property("material_interface")
        if material is not None and str(slot_name) not in ("", "None"):
            source_material_dict[slot_name] = material

    if not source_material_dict:
        unreal.log_warning("The source has no assigned materials in named slots.")
        return 0

    # Keep the target's slot order and leave unmatched slots unchanged.
    target_property = _material_property(target_asset)
    target_materials = target_asset.get_editor_property(target_property)
    updated_count = 0
    for index, slot in enumerate(target_materials):
        slot_name = slot.get_editor_property("material_slot_name")
        if slot_name in source_material_dict:
            slot.set_editor_property("material_interface", source_material_dict[slot_name])
            target_materials[index] = slot
            updated_count += 1

    if updated_count == 0:
        unreal.log_warning("No matching material slot names were found. Nothing was changed.")
        return 0

    # Write the modified array back to the asset before saving it.
    target_asset.set_editor_property(target_property, target_materials)
    if unreal.EditorAssetLibrary.save_loaded_asset(target_asset):
        unreal.log("Material transfer complete. Updated {} slot(s).".format(updated_count))
    else:
        unreal.log_warning("Updated {} slot(s), but saving failed. Save the target manually.".format(
            updated_count))
    return updated_count


if __name__ == "__main__":
    transfer_materials_by_slot_name()
