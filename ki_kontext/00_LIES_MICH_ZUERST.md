# Kontext: Starship-Lieferroboter als CARLA-Fahrzeug

Stand: 28.10.2026. Dieser Ordner fasst eine lange Arbeitssitzung (07.10.–18.10.2026) mit Claude zusammen,
damit eine andere KI ohne Vorwissen weitermachen kann. Zuerst diese Datei lesen. Details: `../docs/` und `../config/` in diesem Repo.

## Worum es geht

Ein 6-rädriger Lieferroboter nach Vorbild des Starship-Bots (Design „HKA“: anthrazit, rotes „HKA“ an beiden Seiten,
Antenne mit rotem Licht) wurde als fahrbares Fahrzeug `vehicle.starship.bot` in den Fahrsimulator CARLA eingebaut,
mit 26 simulierten Sensoren. Ein Kollege (Ricardo) will das Ganze nach **CARLA 0.10** (Unreal 5, Chaos-Physik) übertragen.

Der Nutzer ist Anfänger in Blender und Unreal, möchte Erklärungen auf **Deutsch** und Schritt für Schritt,
und lässt die KI gern selbst arbeiten (Terminal, Unreal-Editor-Python, Computer Use).

## Status

| Teil | Stand |
| --- | --- |
| Fahrzeug in CARLA (UE4) | **funktioniert**: steht, fährt ca. 6 km/h, lenkt; Mittelräder drehen optisch mit |
| Sensoren | **funktioniert**: 26 Sensoren, alle liefern Daten (Skript `starship_sensors.py`) |
| ROS 2 | nicht angebunden (lokaler CARLA-Build ohne ROS 2) |
| CARLA 0.10 | nicht installiert; Übertragung geplant, Werte und Anleitung dafür liegen vor |
| GitHub | öffentliches Repo mit allem: https://github.com/Anvinodino/starship-carla |
| Doku für Ricardo | Claude-Doc „Starship-Bot: Fahrzeugwerte für CARLA 0.10“: https://claude.ai/code/artifact/4a20db0b-e260-426d-8772-4517f153ac41 (nur sichtbar, wenn geteilt) |

## Umgebung (auf dem PC geprüft)

| | Wert |
| --- | --- |
| Unreal Engine | 4.26.2, CARLA-Fork (`github.com/CarlaUnreal/UnrealEngine`), Pfad `D:\UE4_26` |
| CARLA | Source-Build, Branch `ue4-dev`, Commit `ac006dd1b` (4.9.2026), `git describe` = 0.9.15-571; Python-Paket 0.9.16 |
| Projekt | `D:\CARLA\Unreal\CarlaUE4`, Fahrzeug-Assets in `Content/Carla/vehicle3` |
| Python-Client | `D:\CARLA\PythonAPI\examples`, Python 3.11 mit carla, pygame, numpy |
| Hardware | i5-11600KF, **16 GB RAM**, RTX 3060 12 GB, Windows 11 Home |
| Werkzeuge | Blender 5.2, GitHub CLI (`C:\Program Files\GitHub CLI\gh.exe`, angemeldet als `Anvinodino`) |

Für CARLA 0.10 empfiehlt die Doku 32 GB RAM und 16 GB VRAM; dieser PC liegt darunter.

## Wo was liegt

- **GitHub-Repo** (auch lokal unter `C:\Users\letie\Downloads\starship-carla`): Modelle, UE4-Assets, Werte, Sensorik, Skripte, Doku.
  Aufbau siehe `../README.md`.
- **Aktuelle Modelle:** `starship_hka_v5.fbx` / `.blend` (HKA-Design), `starship_carla_v4.fbx` (ursprüngliches Design, gleiches Skelett).
- **Unreal-Assets, die wirklich benutzt werden:** `BP_Starship`, `BP_Starship_FLW/FRW/RLW/RRW`, `SK_Starship_Mesh_HKA`,
  `SK_Starship_v4_SM_Starship_Skeleton`, `PA_Starship_v4`, `AnimBP_Starship_v4`, Materialien `black`, `dark_gray`,
  `hka_body`, `hka_lid`, `hka_red`. Alles andere in `vehicle3` sind alte Versuche (v2, v3, cm, `starship_carla*`, `pa_starship`, `phys_starship`) und kann gelöscht werden.
- **Viele Debug-Skripte** `starship_*.py` in `C:\Users\letie\Downloads` (Editor-Python und CARLA-Client), nicht im Repo.

## Wichtigste Werte (vollständig in `../docs/FAHRZEUGWERTE.md` und `../config/starship_values.json`)

- Maße 56,5 × 55,4 × 65,7 cm; Radradius 9 cm, Breite 4 cm; Radstand 38,2 cm, Spur 51,2 cm.
- Knochen: Wurzel `VehicleBase` (Z 9 cm), `Wheel_Front/Middle/Rear_Left/Right`; alle ohne Rotation.
- Masse 35 kg, COM −15 cm Z, Max RPM 720, Torque ca. 10–15 Nm, 1 Gang (1,0), Final 3,4.
- Physik: eine Box 55 × 45 × 33 cm auf `VehicleBase` (Unterkante 16 cm über Boden), keine Rad-Bodies.
- PhysX-4W: nur 4 Räder simuliert; AnimBP kopiert die Drehung der Hinterräder auf die Mittelräder.

## Gelöste Probleme (nicht wiederholen)

1. **Skalierung:** Die erste FBX hatte Knoten-Skalierung 100, der Bot fiel durch die Welt. Lösung: Export in cm, keine Skalierung, Armature heißt „Armature“ (UE überspringt sie, Wurzel wird `VehicleBase`).
2. **Knochen-Rotation:** Knochen zeigten in Blender nach oben, dadurch 90° gedreht in UE und das Fahrwerk rechnete seitwärts. Lösung v4: alle Knochen mit tail = head + (0, 15, 0) cm, roll 0.
3. **VehicleBounds** hatte Kollision, der Bot stand auf dieser Box. Muss `NoCollision` sein.
4. **Tire Config** fehlte und CARLA stürzte beim Spawnen ab. Alle Räder brauchen `CommonTireConfig`.
5. **Speichern schlug fehl** (Datei gesperrt), dadurch gingen Assets beim Neustart verloren. Nach jedem Import **Save All**, gesperrte Dateien nicht im selben Editor-Lauf löschen.
6. **Speicher voll** (`Ran out of memory`): Town10 plus zwei gleichzeitig laufende Editoren auf 16 GB. Nur **einen** Editor starten, Map **Town02** verwenden (Startargument `/Game/Carla/Maps/Town02`).
7. Editor-Python: `get_vehicle_physics_control()` auf der Blueprint-Vorlage (CDO) aufrufen **crasht den Editor**. `carla`-Client `apply_physics_control` lässt den Bot aus der Welt fallen.

## Arbeitsweise, die sich bewährt hat

- Editor-Python im Output Log: `py "C:/Pfad/skript.py"`; Ergebnisse in eine Datei schreiben statt im Log suchen.
- Werte lesen ohne Editor: `.uasset`-Dateien lassen sich nur lesend parsen (Namenstabelle + Property-Tags).
- Bei Computer Use: vor jedem Klick die Maus bewegen (Slate), Details-Suchfeld nimmt kein Tippen an,
  den Editor nie über `open_application` starten (startet eine zweite Instanz).
- Start des Editors mit Town10 dauert mehrere Minuten; Play in Town10 4–5 Minuten.

## Offene Punkte

- CARLA 0.10: Source-Build mit Editor nötig (wahrscheinlich auf Ricardos PC); Blueprints und Räder für Chaos neu anlegen.
  Aufwand geschätzt 1–1,5 Tage plus Build. Details in `../docs/CARLA_0.10.md`.
- Offene Frage: Funktioniert in CARLA 0.10 ein eigenes Skelett mit 6 Rädern ohne Änderung am C++-Code?
- VehicleBounds sitzt noch auf der Höhe des alten Meshes (Z 69 cm), für HKA besser Z 33 cm, Extent 28 × 28 × 33 cm.
- ROS 2: lokal nicht gebaut (Ros2 OFF). Optionen: carla-ros-bridge (z. B. in WSL2) oder CARLA mit `--ros2` neu bauen.
- Alte Assets in `vehicle3` aufräumen (in einem frischen Editor-Lauf).

## Dateien im Repo

| Datei | Inhalt |
| --- | --- |
| `ki_kontext/00_LIES_MICH_ZUERST.md` | diese Zusammenfassung |
| `ki_kontext/arbeitsnotizen_claude.md` | Claudes interne Projektnotiz (knapp, Englisch, mit allen Zwischenständen) |
| `README.md` | Import-Anleitung |
| `docs/FAHRZEUGWERTE.md` | alle Fahrzeug-, Rad- und Kollisionswerte |
| `docs/SENSORIK.md` | alle 26 Sensoren mit Position, Begründung und Quellen |
| `docs/CARLA_0.10.md` | was sich beim Umstieg auf Chaos ändert |
| `config/starship_values.json`, `config/starship_sensors.json` | dieselben Werte maschinenlesbar |
| `docs/images/` | Bilder: Bot in CARLA, Sensorpositionen, Content Browser, Blueprint |
