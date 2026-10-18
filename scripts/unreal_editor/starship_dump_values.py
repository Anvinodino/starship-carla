# Dumps all Starship vehicle settings from the UE4 editor to JSON (read-only).
import os
import unreal, json

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "starship_values.json")
BASE = "/Game/Carla/vehicle3/"
result = {"errors": []}


def val(v, depth=0):
    if depth > 6:
        return str(v)
    if isinstance(v, (bool, int, float, str)) or v is None:
        return v
    if isinstance(v, unreal.Name):
        return str(v)
    if isinstance(v, unreal.Text):
        return str(v)
    if isinstance(v, unreal.Object):
        return v.get_path_name()
    if isinstance(v, unreal.EnumBase):
        return str(v.name)
    if isinstance(v, (list, tuple, unreal.Array)):
        return [val(x, depth + 1) for x in v]
    if isinstance(v, unreal.StructBase):
        out = {}
        for name in dir(v):
            if name.startswith("_"):
                continue
            try:
                a = v.get_editor_property(name)
            except Exception:
                continue
            out[name] = val(a, depth + 1)
        return out or str(v)
    return str(v)


def props(obj, names):
    out = {}
    for n in names:
        try:
            out[n] = val(obj.get_editor_property(n))
        except Exception as e:
            out[n] = "ERR: %s" % e
    return out


def curve_keys(rfc):
    try:
        rc = rfc.get_editor_property("editor_curve_data")
        keys = rc.get_editor_property("keys")
        return [[k.get_editor_property("time"), k.get_editor_property("value")] for k in keys]
    except Exception as e:
        return "ERR: %s" % e


try:
    cls = unreal.EditorAssetLibrary.load_blueprint_class(BASE + "BP_Starship")
    cdo = unreal.get_default_object(cls)
    result["bp_class"] = cls.get_path_name()
    result["bp_parent"] = str(unreal.SystemLibrary.get_class_display_name(cls))
    mesh = cdo.get_editor_property("mesh")
    result["mesh"] = props(mesh, ["skeletal_mesh", "anim_class", "override_materials", "collision_profile_name"])
    try:
        bi = mesh.get_editor_property("body_instance")
        result["mesh"]["body_instance"] = props(bi, ["com_nudge", "mass_scale", "linear_damping", "angular_damping", "collision_enabled", "object_type"])
    except Exception as e:
        result["errors"].append("body_instance: %s" % e)
    mv = cdo.get_editor_property("vehicle_movement")
    result["movement_class"] = mv.get_class().get_name()
    result["movement"] = props(mv, [
        "mass", "drag_coefficient", "chassis_width", "chassis_height", "inertia_tensor_scale",
        "min_normalized_tire_load", "min_normalized_tire_load_filtered", "max_normalized_tire_load",
        "max_normalized_tire_load_filtered", "threshold_longitudinal_speed", "low_forward_speed_sub_step_count",
        "high_forward_speed_sub_step_count", "reverse_as_brake", "deprecated_spring_offset_mode",
        "ackermann_accuracy", "idle_brake_input", "stop_threshold", "wrong_direction_threshold",
        "use_rvo_avoidance"])
    ws = []
    for w in mv.get_editor_property("wheel_setups"):
        ws.append(props(w, ["wheel_class", "bone_name", "additional_offset", "disable_steering"]))
    result["wheel_setups"] = ws
    eng = mv.get_editor_property("engine_setup")
    result["engine"] = props(eng, ["max_rpm", "moi", "damping_rate_full_throttle",
                                   "damping_rate_zero_throttle_clutch_engaged",
                                   "damping_rate_zero_throttle_clutch_disengaged"])
    result["engine"]["torque_curve"] = curve_keys(eng.get_editor_property("torque_curve"))
    result["differential"] = val(mv.get_editor_property("differential_setup"))
    tr = mv.get_editor_property("transmission_setup")
    result["transmission"] = props(tr, ["use_gear_auto_box", "gear_switch_time", "gear_auto_box_latency",
                                        "final_ratio", "reverse_gear_ratio", "neutral_gear_up_ratio", "clutch_strength"])
    result["transmission"]["forward_gears"] = [props(g, ["ratio", "down_ratio", "up_ratio"]) for g in tr.get_editor_property("forward_gears")]
    result["steering_curve"] = curve_keys(mv.get_editor_property("steering_curve"))
    try:
        vb = cdo.get_editor_property("vehicle_bounds")
        result["vehicle_bounds"] = props(vb, ["box_extent", "relative_location", "collision_profile_name"])
    except Exception as e:
        result["errors"].append("vehicle_bounds: %s" % e)
except Exception as e:
    result["errors"].append("BP: %s" % e)

wheel_props = ["shape_radius", "shape_width", "mass", "damping_rate", "steer_angle", "affected_by_handbrake",
               "tire_config", "lat_stiff_max_load", "lat_stiff_value", "long_stiff_value",
               "suspension_force_offset", "suspension_max_raise", "suspension_max_drop",
               "suspension_natural_frequency", "suspension_damping_ratio", "suspension_sweep_type",
               "max_brake_torque", "max_hand_brake_torque", "auto_adjust_collision_size",
               "dont_create_shape", "collision_mesh"]
result["wheels"] = {}
for w in ["FLW", "FRW", "RLW", "RRW"]:
    try:
        c = unreal.EditorAssetLibrary.load_blueprint_class(BASE + "BP_Starship_" + w)
        result["wheels"][w] = props(unreal.get_default_object(c), wheel_props)
    except Exception as e:
        result["errors"].append("wheel %s: %s" % (w, e))

try:
    sk = unreal.EditorAssetLibrary.load_asset(BASE + "SK_Starship_Mesh_HKA")
    result["skeletal_mesh"] = props(sk, ["physics_asset", "skeleton", "materials"])
    b = sk.get_bounds()
    result["skeletal_mesh"]["bounds_box_extent"] = val(b.box_extent)
    result["skeletal_mesh"]["bounds_origin"] = val(b.origin)
except Exception as e:
    result["errors"].append("skeletal mesh: %s" % e)

with open(OUT, "w") as f:
    json.dump(result, f, indent=2, default=str)
unreal.log("STARSHIP DUMP WRITTEN: " + OUT)
