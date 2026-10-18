"""HKA-Starship-Bot in CARLA fahren - ohne Sensor-Ausstattung, nur zwei Ansichten.

Links:  Fahrersicht (vorne am Bot, Augenhoehe ca. 45 cm)
Rechts: Beobachter-Kamera, die dem Bot folgt (V wechselt: hinten-oben / Draufsicht)

Beide Bilder kommen von "Zuschauer-Kameras". Sie gehoeren NICHT zur Sensor-Ausstattung
des Bots, werden nirgends veroeffentlicht und dienen nur der Anzeige.

Aufruf (Play im Unreal-Editor muss laufen):
    py -3.11 starship_drive.py              # Spawnpunkt 0
    py -3.11 starship_drive.py --spawn 5    # anderer Spawnpunkt

Tasten: W Gas | S Bremse | A/D lenken | Q Rueckwaerts an/aus | Leertaste Handbremse
        V Beobachter-Ansicht wechseln | Backspace neu spawnen | ESC Ende
"""
import argparse
import math

import numpy as np
import pygame
import carla

VIEW_W, VIEW_H = 640, 480
VIEWS = {
    "hinten-oben": carla.Transform(carla.Location(x=-2.2, z=1.4), carla.Rotation(pitch=-22)),
    "Draufsicht": carla.Transform(carla.Location(z=6.0), carla.Rotation(pitch=-90)),
}


class View:
    """Eine Kamera, deren letztes Bild als pygame-Surface bereitliegt."""

    def __init__(self, world, vehicle, transform, fov, attachment):
        bp = world.get_blueprint_library().find("sensor.camera.rgb")
        bp.set_attribute("image_size_x", str(VIEW_W))
        bp.set_attribute("image_size_y", str(VIEW_H))
        bp.set_attribute("fov", str(fov))
        bp.set_attribute("role_name", "viewer")
        self.surface = None
        self.actor = world.spawn_actor(bp, transform, attach_to=vehicle, attachment_type=attachment)
        self.actor.listen(self._on_image)

    def _on_image(self, img):
        a = np.frombuffer(img.raw_data, dtype=np.uint8).reshape(img.height, img.width, 4)[:, :, 2::-1]
        self.surface = pygame.surfarray.make_surface(a.swapaxes(0, 1))

    def destroy(self):
        if self.actor.is_alive:
            self.actor.stop()
            self.actor.destroy()


def spawn_bot(world, index):
    for a in world.get_actors().filter("vehicle.starship.bot"):
        a.destroy()
    bp = world.get_blueprint_library().find("vehicle.starship.bot")
    bp.set_attribute("role_name", "hero")
    points = world.get_map().get_spawn_points()
    sp = points[index % len(points)]
    sp.location.z += 0.3
    return world.spawn_actor(bp, sp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--spawn", type=int, default=0)
    args = ap.parse_args()

    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    world = client.get_world()

    pygame.init()
    screen = pygame.display.set_mode((2 * VIEW_W, VIEW_H))
    pygame.display.set_caption("HKA-Bot fahren")
    font = pygame.font.SysFont("consolas", 18)
    clock = pygame.time.Clock()

    spawn_index = args.spawn
    vehicle = spawn_bot(world, spawn_index)
    view_names = list(VIEWS)
    view_idx = 0
    fpv = View(world, vehicle, carla.Transform(carla.Location(x=0.30, z=0.45)), 90, carla.AttachmentType.Rigid)
    obs = View(world, vehicle, VIEWS[view_names[view_idx]], 75, carla.AttachmentType.SpringArmGhost)
    ctrl = carla.VehicleControl()

    def respawn(new_index):
        nonlocal vehicle, fpv, obs
        fpv.destroy(); obs.destroy()
        if vehicle.is_alive:
            vehicle.destroy()
        vehicle = spawn_bot(world, new_index)
        fpv = View(world, vehicle, carla.Transform(carla.Location(x=0.30, z=0.45)), 90, carla.AttachmentType.Rigid)
        obs = View(world, vehicle, VIEWS[view_names[view_idx]], 75, carla.AttachmentType.SpringArmGhost)

    try:
        running = True
        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        running = False
                    elif e.key == pygame.K_q:
                        ctrl.reverse = not ctrl.reverse
                    elif e.key == pygame.K_v:
                        view_idx = (view_idx + 1) % len(view_names)
                        obs.destroy()
                        obs = View(world, vehicle, VIEWS[view_names[view_idx]], 75, carla.AttachmentType.SpringArmGhost)
                    elif e.key == pygame.K_BACKSPACE:
                        spawn_index += 1
                        respawn(spawn_index)

            k = pygame.key.get_pressed()
            ctrl.throttle = 1.0 if k[pygame.K_w] else 0.0
            ctrl.brake = 1.0 if k[pygame.K_s] else 0.0
            ctrl.steer = (-0.7 if k[pygame.K_a] else 0.0) + (0.7 if k[pygame.K_d] else 0.0)
            ctrl.hand_brake = bool(k[pygame.K_SPACE])
            vehicle.apply_control(ctrl)

            screen.fill((20, 20, 20))
            if fpv.surface:
                screen.blit(fpv.surface, (0, 0))
            if obs.surface:
                screen.blit(obs.surface, (VIEW_W, 0))
            v = vehicle.get_velocity()
            kmh = 3.6 * math.hypot(v.x, v.y)
            hud = [("Fahrersicht", (10, 8)),
                   ("Beobachter: %s  (V wechselt)" % view_names[view_idx], (VIEW_W + 10, 8)),
                   ("%.1f km/h%s" % (kmh, "   RUECKWAERTS" if ctrl.reverse else ""), (10, VIEW_H - 30))]
            for text, pos in hud:
                screen.blit(font.render(text, True, (0, 0, 0)), (pos[0] + 1, pos[1] + 1))
                screen.blit(font.render(text, True, (255, 255, 0)), pos)
            pygame.display.flip()
            clock.tick(30)
    finally:
        fpv.destroy(); obs.destroy()
        if vehicle.is_alive:
            vehicle.destroy()
        pygame.quit()


if __name__ == "__main__":
    main()
