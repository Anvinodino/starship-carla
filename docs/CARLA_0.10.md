# Umstieg auf CARLA 0.10 (Unreal 5, Chaos)

Mesh, Skelett und Materialien lassen sich aus der FBX übernehmen. Das Fahrzeug-Blueprint und die Rad-Blueprints
müssen neu angelegt werden, weil CARLA 0.10 PhysX durch Chaos ersetzt: `WheeledVehicleMovementComponent4W` und
`VehicleWheel` gibt es dort nicht mehr. Geschätzter Aufwand mit laufendem 0.10-Editor: 1 bis 1,5 Arbeitstage,
davon der größte Teil für das Abstimmen des Fahrverhaltens.

| Asset | UE4 (PhysX) | CARLA 0.10 (Chaos) | Vorgehen |
| --- | --- | --- | --- |
| Mesh + Skelett | SK_Starship_Mesh_HKA | Skeletal Mesh | `models/starship_hka_v5.fbx` neu importieren |
| Materialien | dark_gray, black, hka_body, hka_red, hka_lid | Material | neu anlegen (einfarbig) oder migrieren |
| Physics Asset | PA_Starship_v4 | Physics Asset | Box 55 × 45 × 33 cm, Mitte 23,45 cm über `VehicleBase` |
| AnimBP | Wheel Handler + 2 × Copy Bone | Vehicle-AnimInstance mit Wheel Controller | neu bauen; Copy Bone entfällt, wenn alle 6 Räder simuliert werden |
| Rad-BPs | VehicleWheel | ChaosVehicleWheel | neu anlegen, Werte aus [FAHRZEUGWERTE.md](FAHRZEUGWERTE.md) |
| BP_Starship | WheeledVehicleMovementComponent4W | ChaosWheeledVehicleMovementComponent | von CARLAs Basis-Fahrzeug ableiten, Werte eintragen |
| Registrierung | VehicleFactory | Fahrzeugliste von CARLA 0.10 | `vehicle.starship.bot` eintragen |

Werte, die sich nicht 1:1 übertragen lassen:

- **Motor:** Chaos trennt Max Torque (Nm) von einer normierten Torque Curve (0–1). Startwert ca. 15 Nm, Kurve flach bei 1, Max RPM 720.
- **Federung:** Chaos nutzt Spring Rate statt Natural Frequency. Grobe Umrechnung: Masse pro Rad × (2π × 9 Hz)², bei 8,75 kg pro Rad ca. 28.000 N/m. Einheit im Chaos-Feld vor dem Eintragen prüfen.
- **Reifen:** keine Tire Config; Reibung über Friction Force Multiplier und Cornering Stiffness am Rad.
- **Räder:** Chaos kann mehr als 4 Räder. Die Mittelräder (`Wheel_Middle_Left/Right`) wären dann eigene Wheel Setups ohne Lenkung.
- **Schwerpunkt:** statt COM Nudge die Option Center of Mass Override der Movement-Komponente (−15 cm in Z).

Offene Frage: Die CARLA-Anleitung geht von 4 Rädern und einem gemeinsamen Basis-Skelett aus
([Add a new vehicle](https://carla.readthedocs.io/tuto_A_add_vehicle/)). Ob ein eigenes Skelett mit 6 Rädern
ohne Anpassung am C++-Code läuft, muss getestet werden.

Systemanforderungen CARLA 0.10 laut Doku: RTX 3000 oder besser mit mindestens 16 GB VRAM, 32 GB RAM empfohlen,
ca. 130 GB Platz ([Quick start](https://carla-ue5.readthedocs.io/en/latest/start_quickstart/),
[Build from source](https://carla-ue5.readthedocs.io/en/latest/build_carla/)).
