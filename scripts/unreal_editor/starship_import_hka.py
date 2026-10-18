import unreal

import os

# Importiert models/starship_hka_v5.fbx auf das vorhandene v4-Skelett in /Game/Carla/vehicle3/.
HERE = os.path.dirname(os.path.abspath(__file__))
FBX = os.path.join(HERE, "..", "..", "models", "starship_hka_v5.fbx")
D = "/Game/Carla/vehicle3/"
LOG = os.path.join(HERE, "starship_import_hka_log.txt")
EAL = unreal.EditorAssetLibrary
out = []

skel = unreal.load_asset(D + "SK_Starship_v4_SM_Starship_Skeleton")
opts = unreal.FbxImportUI()
opts.import_mesh = True
opts.import_as_skeletal = True
opts.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
opts.import_animations = False
opts.import_materials = True
opts.import_textures = False
opts.create_physics_asset = False
opts.skeleton = skel
opts.skeletal_mesh_import_data.import_uniform_scale = 1.0
opts.skeletal_mesh_import_data.set_editor_property("import_morph_targets", False)

task = unreal.AssetImportTask()
task.filename = FBX
task.destination_path = D[:-1]
task.destination_name = "SK_Starship_HKA"
task.automated = True
task.replace_existing = False
task.save = True
task.options = opts
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
paths = list(task.imported_object_paths)
out.append("imported: %s" % paths)

mesh_path = D + "SK_Starship_Mesh_HKA"
mesh_obj = [p for p in paths if "SkeletalMesh" in str(unreal.load_asset(p).get_class().get_name())] if paths else []
src = mesh_obj[0] if mesh_obj else (paths[0] if paths else None)
if src and not EAL.does_asset_exist(mesh_path):
    out.append("rename ok: %s" % EAL.rename_asset(src, mesh_path))
mesh = unreal.load_asset(mesh_path)
mesh.set_editor_property("physics_asset", unreal.load_asset(D + "PA_Starship_v4"))
b = mesh.get_bounds()
out.append("bounds half %s origin %s" % (b.box_extent, b.origin))
out.append("skeleton: %s" % mesh.skeleton.get_path_name())
out.append("physics: %s" % mesh.physics_asset.get_path_name())
out.append("materials: %s" % [(str(m.material_slot_name), m.material_interface.get_path_name() if m.material_interface else None) for m in mesh.materials])
EAL.save_loaded_asset(mesh, only_if_is_dirty=False)

cdo = unreal.get_default_object(unreal.load_object(None, D + "BP_Starship.BP_Starship_C"))
comp = cdo.get_editor_property("mesh")
comp.set_editor_property("skeletal_mesh", mesh)
comp.set_editor_property("anim_class", unreal.load_object(None, D + "AnimBP_Starship_v4.AnimBP_Starship_v4_C"))
comp.set_editor_property("override_materials", [])
bp = unreal.load_asset(D + "BP_Starship")
bp.modify()
out.append("BP saved: %s" % EAL.save_loaded_asset(bp, only_if_is_dirty=False))
out.append("BP mesh now: %s" % comp.get_editor_property("skeletal_mesh").get_path_name())
EAL.save_directory(D, only_if_is_dirty=True, recursive=False)
with open(LOG, "w") as f:
    f.write("\n".join(str(x) for x in out))
