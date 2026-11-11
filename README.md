# Anno 117 Savegame-Editor

[Deutsch](#deutsch) · [English](#english)

## Deutsch

Kleiner Desktop-Editor (Python/tkinter) für Spielstände von *Anno 117 – Pax Romana*:

- Denare, Baurechte und Auxiliareserven
- Lager jeder eigenen Insel (Latium, Albion, Aegyptus), mit Suchfeld
- Fruchtbarkeiten und Rohstoffvorkommen: Insel auf der Regionskarte anklicken (gedreht wie im Spiel, Mausrad zoomt), dann im Fenster mit den Warensymbolen an- und abhaken. Die Karte zeigt Inselnamen und gebaute Gebäude als Punkte; die Maus auf einer Insel zeigt ihre Fruchtbarkeiten
- Spieleinstellungen inkl. DLC-Optionen (z. B. Vulkanaktivität), mit den Texten und der Gliederung des Spielmenüs, mit Suchfeld
- Deutsch/Englisch und Hell/Dunkel umschaltbar

Gespeichert wird immer als **neue Datei**, das Original bleibt unangetastet.

### Start

`Anno117-Savegame-Editor.exe` unter [Releases](../../releases) herunterladen und starten, eine Installation ist nicht nötig. Windows warnt beim ersten Start vor unbekannten Programmen („Weitere Informationen“ → „Trotzdem ausführen“), weil die Datei nicht signiert ist.

Beim ersten Start fragt der Editor nach dem Installationsordner von Anno 117 und dem Ordner mit den Spielständen (meist `Dokumente\Anno 117 - Pax Romana`). Aus dem Spielordner liest er nur Namen, Texte, Inselbilder und Symbole, er schreibt dort nichts hinein. Seine Einstellungen und die aus dem Spiel gelesenen Namen legt er in `%APPDATA%\Anno117 Savegame-Editor` ab.

Ab Version 1.2.0 sucht der Editor bei jedem Start auf GitHub nach einer neueren Version (er fragt nur `api.github.com` ab). Gibt es eine, fragt er nach. Mit „Ja“ lädt die exe das Update, prüft die Prüfsumme, ersetzt sich selbst und startet neu. Mit „Nein“ fragt er bei dieser Version nicht mehr nach. Ohne Internet startet er ohne Meldung. Von 1.0.0 oder 1.1.0 muss man 1.2.0 einmal von Hand herunterladen.

Mit installiertem Python 3 (nur Standardbibliothek) geht auch ein Doppelklick auf `savegame_editor.pyw`. Die .pyw öffnet bei einem Update nur die Download-Seite.

### Selbst bauen und prüfen

```
pip install pyinstaller
pyinstaller --onefile --windowed --name Anno117-Savegame-Editor savegame_editor.pyw
```
legt die .exe in `dist/` ab.

```
python savegame_editor.pyw --selftest "<Spielstand>.a8s"
```
prüft, dass ein Spielstand byte-identisch neu geschrieben wird (der Spielordner muss schon gewählt sein).

Für eine neue Version `VERSION` in `savegame_editor.pyw` hochsetzen und die exe bauen. Dann ein Release mit dem Tag `v<VERSION>` anlegen und die exe unter dem Namen `Anno117-Savegame-Editor.exe` anhängen. Nur dann findet die Update-Suche sie.

## English

Small desktop editor (Python/tkinter) for *Anno 117 – Pax Romana* save games:

- Denarii, building permits (Officium, Depot, Shrine) and garrison auxilia
- Storage of each of your islands (Latium, Albion, Aegyptus), with a search field
- Fertilities and resource deposits: click an island on the region map (turned as in the game, the wheel zooms), then tick or untick them with their icons. The map shows island names and existing buildings as dots; pointing at an island shows its fertilities
- Game settings incl. DLC options (e.g. volcanic activity), with the game's own texts and menu layout, with a search field
- German/English and light/dark mode

Edits are always saved as a **new file**; the original stays untouched.

### Getting started

Download `Anno117-Savegame-Editor.exe` from [Releases](../../releases) and run it, no installation needed. Windows warns about an unknown program on first launch ("More info" → "Run anyway") because the file is not signed.

On first launch the editor asks for your Anno 117 installation folder and your save game folder (usually `Documents\Anno 117 - Pax Romana`). It only reads names, texts, island images and icons from the game folder and never writes to it. Its settings and the names read from the game are stored in `%APPDATA%\Anno117 Savegame-Editor`.

From version 1.2.0 on, the editor checks GitHub for a newer version at every start (it only contacts `api.github.com`). If one exists, it asks first. Click "Yes" and the exe downloads the update, verifies its checksum, replaces itself and restarts. Click "No" and it won't ask again about that version. Without internet it starts without a message. Users of 1.0.0 or 1.1.0 need to download 1.2.0 once by hand.

With Python 3 installed (standard library only) you can also double-click `savegame_editor.pyw`. For an update, the .pyw only opens the download page.

### Build and test it yourself

```
pip install pyinstaller
pyinstaller --onefile --windowed --name Anno117-Savegame-Editor savegame_editor.pyw
```
puts the .exe in `dist/`.

```
python savegame_editor.pyw --selftest "<save game>.a8s"
```
checks that a save game is written back byte-identical (the game folder must already be set).

To ship a new version, raise `VERSION` in `savegame_editor.pyw` and build the exe. Then create a release tagged `v<VERSION>` and attach the exe as `Anno117-Savegame-Editor.exe`. Only then will the update check find it.
