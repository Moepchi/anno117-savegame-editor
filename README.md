# Anno 117 Savegame-Editor

Kleiner Desktop-Editor (Python/tkinter) für Spielstände von *Anno 117 – Pax Romana*:

- Denare, Baurechte und Auxiliareserven
- Lager jeder eigenen Insel (Latium, Albion, Aegyptus)
- Spieleinstellungen inkl. DLC-Optionen (z. B. Vulkanaktivität), mit den Texten aus dem Spiel
- Deutsch/Englisch und Hell/Dunkel umschaltbar

Gespeichert wird immer als **neue Datei**, das Original bleibt unangetastet.

## Start

`Anno117-Savegame-Editor.exe` herunterladen und starten, eine Installation ist nicht nötig. Windows warnt beim ersten Start vor unbekannten Programmen („Weitere Informationen“ → „Trotzdem ausführen“), weil die Datei nicht signiert ist.

Beim ersten Start fragt der Editor nach dem Installationsordner von Anno 117 und dem Ordner mit den Spielständen (meist `Dokumente\Anno 117 - Pax Romana`). Seine Einstellungen und die aus dem Spiel gelesenen Namen legt er in `%APPDATA%\Anno117 Savegame-Editor` ab.

Mit installiertem Python 3 (nur Standardbibliothek) geht auch ein Doppelklick auf `savegame_editor.pyw`.

## Selbst bauen und prüfen

```
pip install pyinstaller
pyinstaller --onefile --windowed --name Anno117-Savegame-Editor savegame_editor.pyw
```
legt die .exe in `dist/` ab.

```
python savegame_editor.pyw --selftest "<Spielstand>.a8s"
```
prüft, dass ein Spielstand byte-identisch neu geschrieben wird (der Spielordner muss schon gewählt sein).

## Formate

Das Dateiformat (RDA-Container, FileDB, Lager-Codierung, Einstellungen) ist in [STAND.md](STAND.md) beschrieben. `tools/` enthält die Lese-Prototypen aus der Analyse.
