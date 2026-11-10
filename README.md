# Anno 117 Savegame-Editor

Kleiner Desktop-Editor (Python/tkinter) für Spielstände von *Anno 117 – Pax Romana*:

- Denare, Baurechte und Auxiliareserven
- Lager jeder eigenen Insel (Latium, Albion, Aegyptus)
- Spieleinstellungen inkl. DLC-Optionen (z. B. Vulkanaktivität), mit den deutschen Texten aus dem Spiel
- Hell/Dunkel umschaltbar

Gespeichert wird immer als **neue Datei**, das Original bleibt unangetastet.

## Start

Python 3 (nur Standardbibliothek). `savegame_editor.pyw` doppelklicken.

Der Pfad zur Spielinstallation steht oben in der Datei (`GAME`). Beim ersten Start werden daraus die Namen gelesen und in `namen_de.json` zwischengespeichert.

```
python savegame_editor.pyw --selftest "<Spielstand>.a8s"
```
prüft, dass ein Spielstand byte-identisch neu geschrieben wird.

## Formate

Das Dateiformat (RDA-Container, FileDB, Lager-Codierung, Einstellungen) ist in [STAND.md](STAND.md) beschrieben. `tools/` enthält die Lese-Prototypen aus der Analyse.
