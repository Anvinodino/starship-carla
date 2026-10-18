"""Starship-Bot mit kompletter Sensor-Ausstattung in CARLA spawnen und live anzeigen.

Aufruf (CARLA bzw. Play im Editor muss laufen):
    python starship_sensors.py                 # fahren mit WASD, ESC beendet
    python starship_sensors.py --test 8        # 8 s automatisch geradeaus, speichert starship_sensors_test.png

Steuerung: W Gas, S Bremse, A/D lenken, Q Rueckwaerts an/aus, Leertaste Handbremse, ESC Ende.
Sensor-Konfiguration: ../../config/starship_sensors.json (im Repo), alternativ --config <Pfad>.
"""
import argparse
import json
import math
import os
import time

import numpy as np
import pygame
import carla

HERE = os.path.dirname(os.path.abspath(__file__))
TILE_W, TILE_H = 320, 240
WIN_W, WIN_H = 4 * TILE_W, 3 * TILE_H
US_TIMEOUT = 0.25          # s ohne Obstacle-Event -> Ultraschall meldet "frei"


class SensorHub:
    """Haelt die letzten Messwerte aller Sensoren (spaeter Quelle fuer ROS2-Publisher)."""

    def __init__(self, cfg):
        self.cfg = {s["id"]: s for s in cfg["sensors"]}
        self.images = {}        # id -> np.uint8 HxWx3 (RGB)
        self.depth = {}         # id -> np.float32 HxW in Metern
        self.radar = {}         # id -> np.array N x 4 (depth, azimuth, altitude, velocity)
        self.us = {}            # id -> (distanz_m, zeitstempel, objektname)
        self.gnss = None
        self.imu = None
        self.counts = {}

    def _count(self, sid):
        self.counts[sid] = self.counts.get(sid, 0) + 1

    def on_rgb(self, sid, img):
        a = np.frombuffer(img.raw_data, dtype=np.uint8).reshape(img.height, img.width, 4)
        self.images[sid] = a[:, :, 2::-1].copy()
        self._count(sid)

    def on_depth(self, sid, img):
        a = np.frombuffer(img.raw_data, dtype=np.uint8).reshape(img.height, img.width, 4).astype(np.float32)
        d = (a[:, :, 2] + a[:, :, 1] * 256.0 + a[:, :, 0] * 65536.0) / (256.0 ** 3 - 1) * 1000.0
        rng = self.cfg[sid].get("max_range", 5.0)
        d[d > rng] = np.inf       # ToF liefert ausserhalb der Reichweite keinen Wert
        self.depth[sid] = d
        self._count(sid)

    def on_radar(self, sid, meas):
        pts = np.frombuffer(meas.raw_data, dtype=np.float32).reshape(-1, 4)  # velocity, azimuth, altitude, depth
        self.radar[sid] = pts[:, [3, 1, 2, 0]].copy()
        self._count(sid)

    def on_obstacle(self, sid, ev):
        name = ev.other_actor.type_id if ev.other_actor else "?"
        self.us[sid] = (ev.distance, time.time(), name)
        self._count(sid)

    def us_distance(self, sid):
        rng = float(self.cfg[sid]["attributes"]["distance"])
        v = self.us.get(sid)
        if v is None or time.time() - v[1] > US_TIMEOUT:
            return rng, None
        return v[0], v[2]

    def on_gnss(self, sid, m):
        self.gnss = (m.latitude, m.longitude, m.altitude)
        self._count(sid)

    def on_imu(self, sid, m):
        self.imu = (m.accelerometer, m.gyroscope, m.compass)
        self._count(sid)


def spawn_sensors(world, vehicle, cfg, hub):
    lib = world.get_blueprint_library()
    actors = []
    for s in cfg["sensors"]:
        bp = lib.find(s["type"])
        for k, v in s.get("attributes", {}).items():
            if bp.has_attribute(k):
                bp.set_attribute(k, v)
            else:
                print("  Hinweis: %s hat kein Attribut %s" % (s["type"], k))
        if bp.has_attribute("role_name"):
            bp.set_attribute("role_name", s["id"])
        if bp.has_attribute("ros_name"):
            bp.set_attribute("ros_name", s["id"])
        tf = carla.Transform(carla.Location(x=s["x"], y=s["y"], z=s["z"]),
                             carla.Rotation(yaw=s.get("yaw", 0), pitch=s.get("pitch", 0)))
        a = world.spawn_actor(bp, tf, attach_to=vehicle)
        sid, t = s["id"], s["type"]
        if t == "sensor.camera.rgb":
            a.listen(lambda d, sid=sid: hub.on_rgb(sid, d))
        elif t == "sensor.camera.depth":
            a.listen(lambda d, sid=sid: hub.on_depth(sid, d))
        elif t == "sensor.other.radar":
            a.listen(lambda d, sid=sid: hub.on_radar(sid, d))
        elif t == "sensor.other.obstacle":
            a.listen(lambda d, sid=sid: hub.on_obstacle(sid, d))
        elif t == "sensor.other.gnss":
            a.listen(lambda d, sid=sid: hub.on_gnss(sid, d))
        elif t == "sensor.other.imu":
            a.listen(lambda d, sid=sid: hub.on_imu(sid, d))
        actors.append(a)
    return actors


def depth_to_rgb(d):
    finite = np.isfinite(d)
    rng = np.nanmax(np.where(finite, d, np.nan)) if finite.any() else 1.0
    n = np.clip(np.where(finite, d / max(rng, 0.1), 1.0), 0, 1)
    out = np.zeros(d.shape + (3,), np.uint8)
    out[..., 0] = (255 * (1 - n)).astype(np.uint8)
    out[..., 1] = (255 * (1 - np.abs(n - 0.5) * 2)).astype(np.uint8)
    out[..., 2] = (255 * n).astype(np.uint8)
    out[~finite] = (20, 20, 20)
    return out


def blit_array(surf, arr, x, y, label, font):
    if arr is not None:
        s = pygame.surfarray.make_surface(arr.swapaxes(0, 1))
        surf.blit(pygame.transform.smoothscale(s, (TILE_W, TILE_H)), (x, y))
    else:
        pygame.draw.rect(surf, (30, 30, 30), (x, y, TILE_W, TILE_H))
    surf.blit(font.render(label, True, (255, 255, 0)), (x + 4, y + 2))


def draw_ultrasonic(surf, hub, cfg, x0, y0, font):
    pygame.draw.rect(surf, (15, 15, 25), (x0, y0, TILE_W, TILE_H))
    cx, cy, scale = x0 + TILE_W // 2, y0 + TILE_H // 2 + 10, 30.0   # 30 px pro Meter
    pygame.draw.rect(surf, (200, 200, 200), (cx - 0.225 * scale, cy - 0.275 * scale, 0.45 * scale, 0.55 * scale), 1)
    for s in cfg["sensors"]:
        if s["type"] != "sensor.other.obstacle":
            continue
        dist, obj = hub.us_distance(s["id"])
        yaw = math.radians(s["yaw"])
        sx, sy = cx + s["y"] * scale, cy - s["x"] * scale
        ex, ey = sx + math.sin(yaw) * dist * scale, sy - math.cos(yaw) * dist * scale
        col = (0, 200, 0) if obj is None else ((255, 60, 60) if dist < 1.0 else (255, 200, 0))
        pygame.draw.line(surf, col, (sx, sy), (ex, ey), 3)
    surf.blit(font.render("Ultraschall (8x, 3 m)", True, (255, 255, 0)), (x0 + 4, y0 + 2))


def draw_radar(surf, hub, cfg, x0, y0, font):
    pygame.draw.rect(surf, (10, 20, 10), (x0, y0, TILE_W, TILE_H))
    cx, cy, scale = x0 + TILE_W // 2, y0 + TILE_H // 2, 5.0          # 5 px pro Meter (+-24 m)
    pygame.draw.circle(surf, (40, 80, 40), (cx, cy), int(10 * scale), 1)
    pygame.draw.circle(surf, (40, 80, 40), (cx, cy), int(20 * scale), 1)
    pygame.draw.rect(surf, (200, 200, 200), (cx - 2, cy - 3, 4, 6))
    n = 0
    for sid, pts in hub.radar.items():
        s = hub.cfg[sid]
        for depth, az, alt, vel in pts:
            ang = math.radians(s["yaw"]) + az
            px = cx + (s["y"] + math.sin(ang) * depth) * scale
            py = cy - (s["x"] + math.cos(ang) * depth) * scale
            col = (255, 80, 80) if vel < -0.3 else ((80, 160, 255) if vel > 0.3 else (220, 220, 220))
            surf.set_at((int(px), int(py)), col)
            n += 1
    surf.blit(font.render("Radar 4x (Punkte: %d)" % n, True, (255, 255, 0)), (x0 + 4, y0 + 2))


def draw_status(surf, hub, vehicle, ctrl, x0, y0, w, font, t0):
    pygame.draw.rect(surf, (20, 20, 20), (x0, y0, w, TILE_H))
    v = vehicle.get_velocity()
    lines = ["Speed: %.1f km/h  Gang: %d%s" % (3.6 * math.hypot(v.x, v.y), vehicle.get_control().gear,
                                               "  R" if ctrl.reverse else "")]
    if hub.gnss:
        lines.append("GNSS: %.6f, %.6f  alt %.1f" % hub.gnss)
    if hub.imu:
        acc, gyr, comp = hub.imu
        lines.append("IMU acc: %.2f %.2f %.2f" % (acc.x, acc.y, acc.z))
        lines.append("IMU gyr: %.3f %.3f %.3f  Kompass %.0f" % (gyr.x, gyr.y, gyr.z, math.degrees(comp)))
    el = max(time.time() - t0, 0.1)
    rates = {}
    for sid, c in hub.counts.items():
        g = hub.cfg[sid]["group"]
        rates.setdefault(g, []).append(c / el)
    lines.append("Raten (Hz): " + ", ".join("%s %.0f" % (g, sum(r) / len(r)) for g, r in sorted(rates.items())))
    for i, ln in enumerate(lines):
        surf.blit(font.render(ln, True, (230, 230, 230)), (x0 + 6, y0 + 6 + i * 20))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--config", default=os.path.join(HERE, "..", "..", "config", "starship_sensors.json"))
    ap.add_argument("--spawn", type=int, default=25, help="Index des Spawnpunkts")
    ap.add_argument("--sync", action="store_true", help="synchroner Modus (20 Hz, alle Sensoren im Gleichtakt)")
    ap.add_argument("--test", type=float, default=0.0, help="Sekunden automatisch fahren, dann Screenshot speichern")
    args = ap.parse_args()

    cfg = json.load(open(args.config, encoding="utf-8-sig"))
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    world = client.get_world()
    original = world.get_settings()
    if args.sync:
        s = world.get_settings(); s.synchronous_mode = True; s.fixed_delta_seconds = 0.05
        world.apply_settings(s)

    lib = world.get_blueprint_library()
    for a in world.get_actors().filter(cfg["vehicle"]["blueprint"]):
        a.destroy()
    vbp = lib.find(cfg["vehicle"]["blueprint"])
    vbp.set_attribute("role_name", cfg["vehicle"]["role_name"])
    sp = world.get_map().get_spawn_points()[args.spawn]
    sp.location.z += 0.3
    vehicle = world.spawn_actor(vbp, sp)
    hub = SensorHub(cfg)
    sensors = spawn_sensors(world, vehicle, cfg, hub)
    print("Bot + %d Sensoren gespawnt." % len(sensors))

    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Starship-Bot Sensoren")
    font = pygame.font.SysFont("consolas", 15)
    clock = pygame.time.Clock()
    ctrl = carla.VehicleControl()
    t0 = time.time()
    try:
        running = True
        while running:
            if args.sync:
                world.tick()
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_q:
                    ctrl.reverse = not ctrl.reverse
            k = pygame.key.get_pressed()
            if args.test > 0:
                ctrl.throttle, ctrl.steer, ctrl.brake = 0.5, 0.0, 0.0
                if time.time() - t0 > args.test:
                    running = False
            else:
                ctrl.throttle = 0.7 if k[pygame.K_w] else 0.0
                ctrl.brake = 1.0 if k[pygame.K_s] else 0.0
                ctrl.steer = (-0.6 if k[pygame.K_a] else 0.0) + (0.6 if k[pygame.K_d] else 0.0)
                ctrl.hand_brake = bool(k[pygame.K_SPACE])
            vehicle.apply_control(ctrl)

            row = [("cam_front", "Kamera vorne"), ("cam_left_front", "Stereo links"),
                   ("cam_right_front", "Stereo rechts"), ("cam_rear_left", "Stereo hinten")]
            for i, (sid, lab) in enumerate(row):
                blit_array(screen, hub.images.get(sid), i * TILE_W, 0, lab, font)
            blit_array(screen, hub.images.get("cam_front_left"), 3 * TILE_W, TILE_H, "Stereo vorne (30 Grad unten)", font)
            for i, sid in enumerate(["tof_front", "tof_left", "tof_right"]):
                d = hub.depth.get(sid)
                blit_array(screen, depth_to_rgb(d) if d is not None else None, i * TILE_W, TILE_H, sid + " (ToF 5 m)", font)
            draw_ultrasonic(screen, hub, cfg, 0, 2 * TILE_H, font)
            draw_radar(screen, hub, cfg, TILE_W, 2 * TILE_H, font)
            draw_status(screen, hub, vehicle, ctrl, 2 * TILE_W, 2 * TILE_H, 2 * TILE_W, font, t0)
            pygame.display.flip()
            clock.tick(30)
        if args.test > 0:
            out = os.path.join(HERE, "starship_sensors_test.png")
            pygame.image.save(screen, out)
            el = time.time() - t0
            print("Screenshot:", out)
            for sid, v in hub.us.items():
                print('  US-Treffer', sid, 'dist=%.2f' % v[0], 'objekt=', v[2])
            for sid in sorted(hub.cfg):
                print("  %-16s %5.1f Hz" % (sid, hub.counts.get(sid, 0) / el))
    finally:
        for a in sensors:
            if a.is_alive:
                a.stop(); a.destroy()
        if vehicle.is_alive:
            vehicle.destroy()
        if args.sync:
            world.apply_settings(original)
        pygame.quit()


if __name__ == "__main__":
    main()



