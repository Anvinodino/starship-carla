"""Beschleunigung und Hoechstgeschwindigkeit des Bots messen (Gas 100 %, 8 s geradeaus)."""
import os, time
import carla

client = carla.Client("localhost", 2000); client.set_timeout(30.0)
world = client.get_world()
for a in world.get_actors().filter("vehicle.starship.bot"):
    a.destroy()
sps = world.get_map().get_spawn_points()
sp = sps[int(os.environ.get("SP", "0"))]; sp.location.z += 0.3
v = world.spawn_actor(world.get_blueprint_library().find("vehicle.starship.bot"), sp)
time.sleep(2.0)
z0 = v.get_location().z
v.apply_control(carla.VehicleControl(throttle=1.0))
t0 = time.time(); rows = []
while time.time() - t0 < 8:
    vel = v.get_velocity(); tr = v.get_transform()
    rows.append((time.time() - t0, 3.6 * (vel.x ** 2 + vel.y ** 2) ** 0.5, tr.rotation.pitch, tr.location.z))
    time.sleep(0.25)
v.apply_control(carla.VehicleControl(brake=1.0))
time.sleep(2)
vel = v.get_velocity(); stop = 3.6 * (vel.x ** 2 + vel.y ** 2) ** 0.5
for t, s, p, z in rows[::4]:
    print("t=%4.1f s  %5.2f km/h  pitch=%5.1f  z=%.3f" % (t, s, p, z))
top = max(r[1] for r in rows)
t_reach = next((r[0] for r in rows if r[1] >= 0.9 * top), None)
print("Ruhehoehe z=%.3f | Hoechstgeschw. %.2f km/h | 90%% davon nach %.1f s | nach Bremsen %.2f km/h | max. Nickwinkel %.1f Grad" % (
    z0, top, t_reach, stop, max(abs(r[2]) for r in rows)))
v.destroy()
