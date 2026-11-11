"""Anno 117 Savegame-Editor: Denare und Reichsgueter, Insellager, Spieleinstellungen (inkl. DLC-Optionen).

Speichert immer als neue Datei, das Original bleibt unangetastet. Formatnotizen: STAND.md

  savegame_editor.pyw                       Fenster (Doppelklick)
  python savegame_editor.pyw --selftest X   prueft, dass Spielstand X unveraendert identisch neu geschrieben wird
"""
import array, collections, functools, glob, hashlib, html, json, math, os, re, struct, subprocess, sys, tempfile, threading, time, unicodedata, urllib.request, webbrowser, zlib

DATA = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'Anno117 Savegame-Editor')
CACHE = os.path.join(DATA, 'namen_{}.json')  # game names per language
PREFS = os.path.join(DATA, 'einstellungen.json')  # game folder, save folder, dark mode, language
LANGS = {'de': ('Deutsch', 'german'), 'en': ('English', 'english')}  # code: (menu name, texts_<x>.xml)
LANG = 'de'  # set by the window
VERSION = '1.2.0'  # the GitHub release tag is 'v' + VERSION
TITLE = f'Anno 117 Savegame-Editor {VERSION}'
UPDATE_API = 'https://api.github.com/repos/Moepchi/anno117-savegame-editor/releases/latest'
EXE = 'Anno117-Savegame-Editor.exe'  # release asset name
PLAYER = 41  # OwnerProfile / ParticipantGUID of the human player
DIAG = .5 ** .5  # the game shows maps turned by 45°
MAGIC = b'\x08\x00\x00\x00\xfd\xff\xff\xff'
# setup tags whose UI category is spelled differently in assets.xml
ALIAS = {'SetupTraderTraderPrices': 'TraderTradePrices',
         'SetupVolcanoSchedulerIntervalDuration': 'VolcanoSchedulerIntervalLength',
         'SetupContinetnalIslandSettlementCosts': 'ContinentalIslandSettlementCosts'}
# pirate comboboxes -> field tag in the save (Dormancy left out on purpose: 2 = defeated has no menu entry)
PIRATE = {'PirateRaidDifficulty': 'RaidDifficulty', 'PirateWarFleetDifficulty': 'WarFleetDifficulty',
          'PiratePatrolsDifficulty': 'PatrolDifficulty', 'PirateWarThreatsDifficulty': 'WarThreats'}
# tab titles of the game's setup menu (SettingsMenu GUID -> LineId); assets.xml lists the menus but not their titles
SECTIONS = {'150498': '-6914829576719174900', '50976': '-6913167428570173649', '51051': '-6909293900839592885',
            '51052': '-6909425974996756542', '51053': '-6909049289369605519'}
# settings that only act when a game begins (the game's own texts say "zu Beginn", or they shape the generated map):
# shown grey and locked. Not here on purpose: the volcano ("jederzeit änderbar") and DLC3MainStory (can be switched off later)
START_ONLY = {'SetupStartShips', 'SetupStartWithKontor', 'SetupStartGoods', 'SetupStartCredits', 'SetupDistributionWorkforce',
              'SetupRevealedMap', 'SetupContinentalIslandStart', 'EnableGameSeedInRacerAttributeCalculations',
              'SetupStartSessionIslandSize', 'SetupFertility', 'SetupStartForestSize', 'SetupRawMaterial',
              'SetupStartSessionIslandDifficulty'}

# English UI texts keyed by the German original; names of goods, islands and settings come from the game itself
EN = {
    'Kein Anno-Spielstand': 'Not an Anno save game',
    'Unerwartetes Spielstandformat (Block-Flags {})': 'Unexpected save game format (block flags {})',
    'Unbekanntes FileDB-Format': 'Unknown FileDB format',
    'Mengen über 255 sind in diesem Lager nicht möglich (Spielstand kennt kein StrgLrg).':
        'Amounts above 255 are not possible in this storage (the save has no StrgLrg).',
    'Reich: Denare, Baurechte, Reserven': 'Empire: Denarii, permits, auxilia',
    'Insel': 'Island',
    'Lade Namen aus den Spieldateien …': 'Loading names from the game files …',
    'Denare & Lager': 'Denarii & storage',
    'Ware': 'Good', 'Menge': 'Amount', 'Einstellung': 'Setting', 'Wert': 'Value',
    'Doppelklick ändert eine Menge. Mehrere Zeilen mit Strg/Umschalt markieren und':
        'Double-click changes an amount. Select several rows with Ctrl/Shift and',
    'Auswahl setzen …': 'Set selection …',
    'Spieleinstellungen': 'Game settings',
    'Doppelklick zum Ändern. Gruppen und Reihenfolge wie im Spielmenü. Grau = Startoptionen und Kartenerzeugung: '
    'Sie wirken nur beim Spielbeginn und sind darum gesperrt.':
        'Double-click to change. Groups and order as in the game menu. Grey = start options and map generation: '
        'they only apply when a game begins, so they are locked.',
    'Nur beim Spielbeginn wirksam, darum gesperrt: {}': 'Only applies when a game begins, so it is locked: {}',
    'Ohne Menütext im Spiel (Rohwerte)': 'Not in the game menu (raw values)',
    'Fruchtbarkeiten': 'Fertilities',
    'Berg': 'Mountain', 'Fluss': 'River', 'Sumpf': 'Marsh',
    'Maus auf einer Insel zeigt ihre Fruchtbarkeiten, ein Klick ändert sie. Gelb = deins, Rot = andere Parteien. '
    'Mausrad zoomt, Ziehen verschiebt.':
        'Point at an island to see its fertilities, click to change them. Yellow = yours, red = other parties. '
        'Wheel zooms, drag moves.',
    'Gebäude zeigen': 'Show buildings', 'Suche:': 'Search:',
    'Karte nicht lesbar: {}': 'Cannot read the map: {}',
    'Haken setzen oder entfernen. Steht ein Bauplatz dabei (Berg, Fluss, Sumpf), '
    'wirkt sie nur, wenn die Insel so einen Bauplatz hat.':
        'Tick or untick. If a slot is listed (mountain, river, marsh), it only works when the island has such a slot.',
    'Andere Regionen': 'Other regions',
    'Schließen': 'Close',
    '{} markierte Waren': '{} selected goods',
    'Neue Menge für {}:': 'New amount for {}:',
    'Wert {} (unbekannt)': 'Value {} (unknown)',
    '{} (Rohwert)': '{} (raw value)',
    'Übernehmen': 'Apply',
    'Version {} ist verfügbar (du hast {}).': 'Version {} is available (you have {}).',
    'Jetzt herunterladen und neu starten?': 'Download it and restart now?',
    'Download-Seite öffnen?': 'Open the download page?',
    'Ungespeicherte Änderungen gehen dabei verloren.': 'Unsaved changes will be lost.',
    'Lade Update …': 'Downloading update …',
    'Update fehlgeschlagen: {}': 'Update failed: {}',
    'Prüfsumme des Downloads stimmt nicht.': "The download's checksum does not match.",
    'Spielstand öffnen': 'Open save game',
    'Anno 117 Spielstand': 'Anno 117 save game',
    'Lade Spielstand …': 'Loading save game …',
    'Geladen: {}': 'Loaded: {}',
    'Speichern unter': 'Save as',
    ' bearbeitet': ' edited',
    'Bitte unter neuem Namen speichern, das Original bleibt unangetastet.':
        'Please save under a new name; the original stays untouched.',
    'Speichere …': 'Saving …',
    'Gespeichert: {}': 'Saved: {}',
    'Spielstand öffnen …': 'Open save game …',
    'Speichern unter …': 'Save as …',
    'Dunkler Modus': 'Dark mode',
    'Bitte wähle den Installationsordner von Anno 117 (der Ordner mit „maindata“), '
    'z. B. …\\steamapps\\common\\Anno 117 - Pax Romana.':
        'Please choose the Anno 117 installation folder (the one containing "maindata"), '
        'e.g. …\\steamapps\\common\\Anno 117 - Pax Romana.',
    'In diesem Ordner fehlt „maindata\\config.rda“. Bitte den Installationsordner von Anno 117 wählen.':
        'This folder has no "maindata\\config.rda". Please choose the Anno 117 installation folder.',
    'Anno 117 Installationsordner': 'Anno 117 installation folder',
    'Bitte wähle den Ordner mit deinen Spielständen, meist Dokumente\\Anno 117 - Pax Romana.':
        'Please choose the folder with your save games, usually Documents\\Anno 117 - Pax Romana.',
    'Ordner mit den Spielständen': 'Save game folder',
    'Spielstand öffnen, um zu beginnen.': 'Open a save game to begin.',
}


def t(text):
    return EN.get(text, text) if LANG == 'en' else text


# ---------- RDA container (.a8s): per inner file [data][560 B directory entry][32 B block header] ----------

def read_rda(path):
    data = open(path, 'rb').read()
    if data[:18] != b'Resource File V2.2':
        raise ValueError(t('Kein Anno-Spielstand'))
    off, files = struct.unpack_from('<Q', data, 784)[0], []
    while off < len(data):
        flags, n, dsize, _, nxt = struct.unpack_from('<IIQQQ', data, off)
        if flags:
            raise ValueError(t('Unerwartetes Spielstandformat (Block-Flags {})').format(flags))
        for i in range(n):
            e = data[off - dsize + i * 560:off - dsize + (i + 1) * 560]
            foff, size = struct.unpack_from('<QQ', e, 520)
            files.append((e[:520].decode('utf-16-le').split('\0')[0], data[foff:foff + size]))
        if nxt <= off or nxt >= len(data):
            break
        off = nxt
    return data[:792], files


def write_rda(path, head, files):
    out, prev = bytearray(head), None
    for name, content in files:
        pos = len(out)
        out += content
        out += name.encode('utf-16-le').ljust(520, b'\0') + struct.pack('<QQQQQ', pos, len(content), len(content), 0, 0)
        if prev is None:
            struct.pack_into('<Q', out, 784, len(out))
        else:
            struct.pack_into('<Q', out, prev + 24, len(out))  # previous block's "next"
        prev = len(out)
        out += struct.pack('<IIQQQ', 0, 1, 560, 560, 0)
    struct.pack_into('<Q', out, prev + 24, len(out))  # last block points at the end of the file
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(out)
    os.replace(tmp, path)


# ---------- FileDB v3 ----------

class FileDB:
    """Mutable tree: tag = [id, [children]], attribute = [id, bytes]. Name dictionaries are kept verbatim."""

    def __init__(self, data):
        self.packed = data[:2] == b'\x78\xda'
        d = zlib.decompress(data) if self.packed else data
        if d[-8:] != MAGIC:
            raise ValueError(t('Unbekanntes FileDB-Format'))
        self.count, toff, aoff = struct.unpack_from('<III', d, len(d) - 20)
        self.dicts, self.aoff = d[toff:len(d) - 20], aoff - toff
        self.names, self.ids = {1: 'None', 0x8000: 'None'}, {}
        for off in (toff, aoff):
            n = struct.unpack_from('<I', d, off)[0]
            p = off + 4 + 2 * n
            for i in struct.unpack_from(f'<{n}H', d, off + 4):
                e = d.index(b'\0', p)
                self.names[i] = name = d[p:e].decode('utf-8', 'replace')
                self.ids[name, i >= 0x8000] = i
                p = e + 1
        self.root = [0, []]
        stack, p = [self.root], 0
        while p < toff:
            size, nid = struct.unpack_from('<II', d, p)
            p += 8
            if nid == 0:
                stack.pop()
                if not stack:
                    break
            elif nid < 0x8000:
                node = [nid, []]
                stack[-1][1].append(node)
                stack.append(node)
            else:
                stack[-1][1].append([nid, d[p:p + size]])
                p += (size + 7) & ~7

    def tobytes(self):
        out = bytearray()

        def emit(node):
            for k in node[1]:
                if type(k[1]) is list:
                    out.extend(struct.pack('<II', 0, k[0]))
                    emit(k)
                    out.extend(bytes(8))
                else:
                    out.extend(struct.pack('<II', len(k[1]), k[0]))
                    out.extend(k[1])
                    out.extend(bytes(-len(k[1]) % 8))

        emit(self.root)
        out.extend(bytes(8))
        toff = len(out)
        out += self.dicts + struct.pack('<IIIIi', self.count, toff, toff + self.aoff, 8, -3)
        if not self.packed:
            return bytes(out)
        # the game appends an empty zlib stream and the unpacked size; without them it ignores the save
        return zlib.compress(bytes(out), 9) + zlib.compress(b'', 9) + struct.pack('<I', len(out))

    def name(self, node):
        return self.names.get(node[0], 'None')

    def tags(self, node, name):
        return [k for k in node[1] if type(k[1]) is list and self.name(k) == name]

    def path(self, *names):
        nodes = [self.root]
        for n in names:
            nodes = [k for x in nodes for k in self.tags(x, n)]
        return nodes

    def attr(self, node, name):
        return next((k for k in node[1] if type(k[1]) is bytes and self.name(k) == name), None)


# ---------- storages: [guid0][n-1 gaps (minus 1)][n amounts], u32/i32 in StrgLrg, u8 in StrgSmll ----------

def decode_storage(kind, v):
    if kind == 'StrgLrg':
        n = len(v) // 8
        head, amounts = struct.unpack_from(f'<{n}I', v), struct.unpack_from(f'<{n}i', v, 4 * n)
    else:
        n = (len(v) - 3) // 2
        head, amounts = (struct.unpack_from('<I', v)[0], *v[4:3 + n]), tuple(v[3 + n:])
    guids = []
    for d in head:
        guids.append(d if not guids else guids[-1] + d + 1)
    return dict(zip(guids, amounts))


def encode_storage(items, small):
    guids = sorted(items)
    gaps = [b - a - 1 for a, b in zip(guids, guids[1:])]
    amounts = [items[g] for g in guids]
    if small and all(0 <= x < 256 for x in gaps + amounts):
        return 'StrgSmll', struct.pack('<I', guids[0]) + bytes(gaps + amounts)
    return 'StrgLrg', struct.pack(f'<{len(guids)}I{len(guids)}i', guids[0], *gaps, *amounts)


# ---------- savegame ----------

class Save:
    def __init__(self, path):
        self.path = path
        self.head, self.files = read_rda(path)
        raw = dict(self.files)
        self.data, self.setup, self.header = (FileDB(raw[n]) for n in ('data.a7s', 'gamesetup.a7s', 'header.a7s'))
        self.changed = set()
        self.sessions = []  # (session guid, BinaryData attribute, FileDB)
        guid = None
        for k in self.data.path('MetaGameManager', 'GameSessions')[0][1]:
            if type(k[1]) is bytes:
                guid = struct.unpack('<I', k[1][:4])[0]
            else:
                for sd in self.data.tags(k, 'SessionData'):
                    blob = self.data.attr(sd, 'BinaryData')
                    self.sessions.append((guid, blob, FileDB(blob[1])))
        # setup values live in gamesetup.a7s and as a copy in header.a7s: {key: [(db, u16 id attribute)]}
        self.refs = {}
        for db, top in ((self.setup, 'GameSetupManager'), (self.header, 'CorporationProfile')):
            for parent in db.path(top):
                for k in parent[1]:
                    if type(k[1]) is not list:
                        continue
                    if db.name(k) != 'Pirates':
                        self._ref(db, db.name(k), k)
                        continue
                    profile = None
                    for p in k[1]:
                        if type(p[1]) is bytes and db.name(p) == 'Profile':
                            profile = struct.unpack('<I', p[1][:4])[0]
                        elif type(p[1]) is list and db.name(p) in PIRATE.values():
                            self._ref(db, f'Pirate:{profile}:{db.name(p)}', p)

    def _ref(self, db, key, tag):
        value = db.tags(tag, 'value')
        a = value and db.attr(value[0], 'id')
        if a and len(a[1]) == 2:
            self.refs.setdefault(key, []).append((db, a))

    def setting(self, key):
        return struct.unpack('<H', self.refs[key][0][1][1])[0]

    def set_setting(self, key, value):
        for db, a in self.refs[key]:
            a[1] = struct.pack('<H', value)
            self.changed.add(db)

    def islands(self, names):
        """[(label, db, AreaInfo entry)] for every player island."""
        return [(f'{self.area_name(db, area, names)} ({names["assets"].get(str(guid), guid)})', db, area)
                for guid, _, db in self.sessions for area in db.path('GameSessionManager', 'AreaInfo', 'None')
                if self.is_player(db, area)]

    @staticmethod
    def is_player(db, area):
        owner = db.attr(area, 'OwnerProfile')
        return bool(owner) and struct.unpack('<i', owner[1][:4])[0] == PLAYER

    @staticmethod
    def area_name(db, area, names):
        city, owner = db.attr(area, 'CityNameGuid'), db.attr(area, 'OwnerProfile')
        name = city and names['texts'].get(str(struct.unpack('<q', city[1][:8])[0])) or t('Insel')
        rival = owner and struct.unpack('<i', owner[1][:4])[0]
        return f'{name} ({names["assets"][str(rival)]})' if rival != PLAYER and str(rival) in names['assets'] else name

    @staticmethod
    def areas(db):
        """{map template element: [(AreaID, AreaInfo entry)]}. AreaID >> 6 = 129 + element + 128 * (area index - 1);
        an island can hold several areas (Aegyptus: one per sepat)."""
        out = {}
        for info in db.path('GameSessionManager', 'AreaInfo'):
            for k, v in zip(info[1][0::2], info[1][1::2]):
                aid = struct.unpack('<H', k[1][:2])[0]
                out.setdefault(((aid >> 6) - 129) % 128, []).append((aid, v))
        return out

    @staticmethod
    def template(db):
        """The map template's elements (each one island or start position), in AreaID order."""
        return [(db.tags(el, 'Element') or [el])[0] for el in db.path('GameSessionManager', 'MapTemplate', 'TemplateElement')]

    def map_islands(self, db):
        """[(element, x, y, rotation, .a7m path)]: islands of a session; x, y = corner of the island square in tiles."""
        out = []
        for i, e in enumerate(self.template(db)):
            path, rot = db.attr(e, 'MapFilePath'), db.attr(e, 'Rotation90')
            if path:
                out.append((i, *struct.unpack('<ii', db.attr(e, 'Position')[1][:8]), rot[1][0] if rot else 0,
                            path[1].decode('utf-16-le').rstrip('\0')))
        return out

    @staticmethod
    def buildings(db):
        """{AreaID: [(owner, x, y)]}: the objects standing in each area (AreaManager_<AreaID>) with their tile positions.
        owner None = the area's owner (what the player built); else a profile: the area's character, or 34 for rocks,
        mine and river sites and other things of nobody."""
        out = {}
        for am in (k for ams in db.path('GameSessionManager', 'AreaManagers') for k in ams[1] if type(k[1]) is list):
            spots = out.setdefault(int(db.name(am).rpartition('_')[2]), [])
            for o in (o for a in db.tags(am, 'AreaObjectManager') for g in db.tags(a, 'GameObject')
                      for objs in db.tags(g, 'objects') for o in objs[1] if type(o[1]) is list):
                owner, pos = db.attr(o, 'OwnerProfile'), db.attr(o, 'Position')
                if pos:
                    spots.append((owner and struct.unpack('<i', owner[1][:4])[0], *struct.unpack('<f4xf', pos[1][:12])))  # x, height, y
        return out

    def storages(self, names):
        """[(label, db, tag holding the storage)]: the empire storage (Denare) and every player island's warehouse."""
        out = [(t('Reich: Denare, Baurechte, Reserven'), self.data, e) for e in self.empire()]
        for lab, db, area in self.islands(names):
            econ = db.tags(area, 'AreaEconomy')
            if econ and self.storage_attr(db, econ[0]):
                out.append((lab, db, econ[0]))
        return out

    @staticmethod
    def fertilities(db, area):
        return [struct.unpack('<I', k[1][:4])[0] for k in db.tags(area, 'Fertility')[0][1]]

    @classmethod
    def template_fertilities(cls, db, aid):
        """The map template's u32 array of AreaID aid (FertilitiesPerAreaIndex: [u16 area index, array] pairs), or None."""
        mid = (aid >> 6) - 129
        for f in db.tags(cls.template(db)[mid % 128], 'FertilitiesPerAreaIndex'):
            for k, arr in zip(f[1][0::2], f[1][1::2]):
                if struct.unpack('<H', k[1][:2])[0] == mid // 128 + 1:
                    return arr
        return None

    def set_fertilities(self, db, aid, area, guids):
        """AreaInfo holds the island's fertilities, the map template the same set (other order): both are written."""
        db.tags(area, 'Fertility')[0][1][:] = [[0x8000, struct.pack('<I', g)] for g in guids]  # 0x8000 = unnamed list item
        arr = self.template_fertilities(db, aid)
        if arr:
            arr[1] = struct.pack(f'<{len(guids)}I', *guids)
        self.changed.add(db)

    def empire(self):
        """The player's MetaEconomy tags (Denare live in their storage)."""
        for pair in self.data.path('MetaGameManager', 'EconomyManager', 'Pair'):
            owner = self.data.attr(pair, 'ParticipantGUID')
            if owner and struct.unpack('<i', owner[1][:4])[0] == PLAYER:
                return self.data.tags(pair, 'MetaEconomy')
        return []

    @staticmethod
    def storage_attr(db, tag):
        return db.attr(tag, 'StrgLrg') or db.attr(tag, 'StrgSmll')

    def storage(self, db, tag):
        a = self.storage_attr(db, tag)
        return decode_storage(db.name(a), a[1])

    def set_storage(self, db, tag, items):
        a = self.storage_attr(db, tag)
        kind, value = encode_storage(items, db.name(a) == 'StrgSmll')
        if (kind, True) not in db.ids:
            raise ValueError(t('Mengen über 255 sind in diesem Lager nicht möglich (Spielstand kennt kein StrgLrg).'))
        a[0], a[1] = db.ids[kind, True], value
        self.changed.add(db)

    def write(self, path):
        # The load menu reads meta.a7s + header.a7s: give the copy its own name, save time and current Denare.
        # (A copy with the original's exact save time did not show up in the menu.)
        now = struct.pack('<Q', int(time.time()))
        profile = self.header.path('CorporationProfile')[0]
        self.header.attr(profile, 'WallTimeOnSave')[1] = now
        total, econ = self.header.attr(profile, 'TotalMoney'), self.empire()
        money = econ and self.storage(self.data, econ[0]).get(1010017)
        if total and money is not None:
            total[1] = struct.pack('<i', money) + total[1][4:]
        self.changed.add(self.header)
        for _, blob, db in self.sessions:
            if db in self.changed:
                blob[1] = db.tobytes()
                self.changed.add(self.data)
        dbs = {'data.a7s': self.data, 'gamesetup.a7s': self.setup, 'header.a7s': self.header}
        files = [(n, dbs[n].tobytes() if dbs.get(n) in self.changed else c) for n, c in self.files]
        meta = FileDB(dict(files)['meta.a7s'])
        meta.attr(meta.root, 'LastModTime')[1] = now
        meta.attr(meta.root, 'CorporationSaveGameName')[1] = os.path.splitext(os.path.basename(path))[0].encode('utf-16-le')
        files = [(n, meta.tobytes() if n == 'meta.a7s' else c) for n, c in files]
        write_rda(path, self.head, files)


# ---------- names and setting labels from the game files, per language (cached next to this script) ----------

def is_game_dir(path):
    return os.path.isfile(os.path.join(path, 'maindata', 'config.rda'))


def game_names(game, lang='de'):
    src = os.path.join(game, 'maindata', 'config.rda')
    stamp, cache_file = os.path.getmtime(src), CACHE.format(lang)
    try:
        with open(cache_file, encoding='utf-8') as f:
            cache = json.load(f)
        if cache['stamp'] == stamp and 'icons' in cache:
            return cache
    except (OSError, ValueError, KeyError):
        pass
    wanted = {'data/base/config/export/assets.xml': 'assets', f'data/base/config/gui/texts_{LANGS[lang][1]}.xml': 'texts'}
    raw = {}
    with open(src, 'rb') as f:
        for _, name, foff, csz in rda_dir(f):
            if name in wanted:
                f.seek(foff)
                raw[wanted[name]] = f.read(csz).decode('utf-8-sig', 'replace')
                if len(raw) == len(wanted):
                    break
    clean = lambda t: re.sub(r'<[^>]*>', '', html.unescape(t)).strip()
    texts = {k: clean(v) for k, v in re.findall(r'<LineId>(-?\d+)</LineId>\s*<Text>(.*?)</Text>', raw['texts'], re.S)}
    assets, descs, menus, slots, icons = {}, {}, {}, {}, {}
    for chunk in raw['assets'].split('<Asset>'):
        if '<Template>Fertility</Template>' in chunk and '<LimitedLodeMaximum>' not in chunk:  # limited lodes have an amount
            need, g = re.search(r'<NeedsSlot>(\w+)<', chunk), re.search(r'<GUID>(\d+)</GUID>', chunk).group(1)
            slots[g] = need.group(1) if need else ''
            icon = re.search(r'<IconFilename>data/ui/fhd/([^<]+)\.png<', chunk)  # the game ships it as data/ui/4k/…_0.dds
            if icon:
                icons[g] = f'data/ui/4k/{icon.group(1)}_0.dds'
        g, o = re.search(r'<GUID>(\d+)</GUID>', chunk), re.search(r'<OasisId>(-?\d+)</OasisId>', chunk)
        if g and o and o.group(1) in texts:
            assets[g.group(1)] = texts[o.group(1)]
        d = '<Template>Product</Template>' in chunk and re.search(r'<InfoDescription>(-?\d+)<', chunk)
        if g and d and texts.get(d.group(1)):
            descs[g.group(1)] = texts[d.group(1)]  # tooltip text for goods
        if g and '<Template>SettingsMenu</Template>' in chunk:
            menus[g.group(1)] = chunk

    def key_of(body):
        m = re.search(r'Textsource>GameSetup\.RelevantGameSetup[.:](\w+)(?:\((?:datasets\.DifficultyCategory\.)?(\w+)\))?<', body)
        fn, arg = m.groups() if m else (None, None)
        return arg if fn == 'DifficultyCategoryValue' else f'Pirate:{arg}:{PIRATE[fn]}' if fn in PIRATE else None if arg else fn

    # the setup menu as the game shows it: [tab, subheading, key], tabs in order, then one menu per DLC
    order = re.findall(r'<Content>(\d+)</Content>', re.search(r'<GameSetupAdvancedDifficultiesScene>.*?</Categories>', raw['assets'], re.S).group(0))
    dlcs = re.findall(r'<Dlc>(\d+)</Dlc>\s*<Settings>(\d+)</Settings>', re.search(r'<DlcDifficultyScene>.*?</DlcDifficultyScene>', raw['assets'], re.S).group(0))
    menu = []
    for g, title in [(g, texts.get(SECTIONS.get(g), '')) for g in order] + [(m, assets.get(d, '')) for d, m in dlcs]:
        sub = ''
        for el in re.findall(r'<Element>(.*?)</Element>', menus.get(g, ''), re.S):
            if re.search(r'<Template>\w*Headline</Template>', el):
                h = re.search(r'Headline>(-?\d+)<', el)
                sub = texts.get(h.group(1), '') if h else ''
            elif key_of(el):
                menu.append([title, sub, key_of(el)])
    settings = {}
    for kind, body in re.findall(r'<(OptionCombobox|OptionToggle)>(.*?)</\1>', raw['assets'], re.S):
        key = key_of(body)
        head = re.search(r'Headline>(-?\d+)<', body)
        if kind == 'OptionToggle':
            options = [re.search(rf'<{t}>(-?\d+)<', body) for t in ('ActivatedText', 'DeactivatedText')]  # 0 = Activated (checked in-game)
            options = [o.group(1) for o in options if o]
        else:
            options = re.findall(r'<Text>(-?\d+)</Text>', body)
        if key and head and options:
            settings[key] = [texts.get(head.group(1), key), [texts.get(o, o) for o in options]]
    # fertilities in the order of the game's map legend, with the slot they need (Mountain/River/Marsh or '')
    legend = re.findall(r'<GUID>(\d+)</GUID>', re.search(r'<FertilityOrder>.*?</FertilityOrder>', raw['assets'], re.S).group(0))
    ferts = [[int(g), slots[g]] for g in legend if g in slots]
    cache = {'stamp': stamp, 'texts': texts, 'assets': assets, 'descs': descs, 'settings': settings, 'menu': menu,
             'ferts': ferts, 'icons': icons}
    os.makedirs(DATA, exist_ok=True)
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)
    return cache


def rda_dir(f):
    """(block flags, name, offset, size) of every file in the plain blocks (not packed, not encrypted) of an open game archive."""
    off, size = struct.unpack_from('<Q', f.read(792), 784)[0], f.seek(0, 2)
    while off < size:
        f.seek(off)
        flags, n, dsize, _, nxt = struct.unpack('<IIQQQ', f.read(32))
        if not flags & 7:
            f.seek(off - dsize)
            d = f.read(dsize)
            for i in range(n):
                e = d[i * 560:(i + 1) * 560]
                yield (flags, e[:520].decode('utf-16-le').split('\0')[0], *struct.unpack_from('<QQ', e, 520))
        if nxt <= off:
            break
        off = nxt


# ---------- island maps and icons: read from the game's archives, never shipped with the editor ----------

@functools.lru_cache(maxsize=1)
def game_index(game):
    """{file name: [archive, offset, size]} of the island infos, island map images and goods icons (cached in DATA)."""
    arcs = sorted((p for p in glob.glob(os.path.join(glob.escape(game), 'maindata', '*.rda'))
                   if re.search(r'provinces|^ui\.rda$|^zz_patchfiles_', os.path.basename(p))), key=os.path.basename)
    stamp, cache_file = [[os.path.basename(p), os.path.getsize(p), os.path.getmtime(p)] for p in arcs], os.path.join(DATA, 'spieldateien.json')
    try:
        with open(cache_file, encoding='utf-8') as f:
            cache = json.load(f)
        if cache['stamp'] == stamp:
            return cache['files']
    except (OSError, ValueError, KeyError):
        pass
    files = {}
    for p in arcs:  # later archives (patches) win
        with open(p, 'rb') as f:
            for flags, name, off, size in rda_dir(f):
                if flags & 8:
                    files.pop(name, None)  # deleted by a patch
                elif re.search(r'\.a7minfo$|/gamemapimage_0\.dds$|/icon_content/.*_0\.dds$', name):
                    files[name] = [os.path.basename(p), off, size]
    os.makedirs(DATA, exist_ok=True)
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump({'stamp': stamp, 'files': files}, f)
    return files


def game_file(game, name):
    arc, off, size = game_index(game)[name]
    with open(os.path.join(game, 'maindata', arc), 'rb') as f:
        f.seek(off)
        return f.read(size)


# BC7 textures: pure-Python decoder
# per mode: subsets, partition bits, rotation bits, index-selection bit, color bits, alpha bits, p-bit per endpoint, p-bit per subset, index bits, 2nd index bits
BC7_MODES = ((3, 4, 0, 0, 4, 0, 1, 0, 3, 0), (2, 6, 0, 0, 6, 0, 0, 1, 3, 0), (3, 6, 0, 0, 5, 0, 0, 0, 2, 0), (2, 6, 0, 0, 7, 0, 1, 0, 2, 0),
             (1, 0, 2, 1, 5, 6, 0, 0, 2, 3), (1, 0, 2, 0, 7, 8, 0, 0, 2, 2), (1, 0, 0, 0, 7, 7, 1, 0, 4, 0), (2, 6, 0, 0, 5, 5, 1, 0, 2, 0))
BC7_P2 = (0xCCCC, 0x8888, 0xEEEE, 0xECC8, 0xC880, 0xFEEC, 0xFEC8, 0xEC80, 0xC800, 0xFFEC, 0xFE80, 0xE800, 0xFFE8, 0xFF00, 0xFFF0, 0xF000,
          0xF710, 0x008E, 0x7100, 0x08CE, 0x008C, 0x7310, 0x3100, 0x8CCE, 0x088C, 0x3110, 0x6666, 0x366C, 0x17E8, 0x0FF0, 0x718E, 0x399C,
          0xAAAA, 0xF0F0, 0x5A5A, 0x33CC, 0x3C3C, 0x55AA, 0x9696, 0xA55A, 0x73CE, 0x13C8, 0x324C, 0x3BDC, 0x6996, 0xC33C, 0x9966, 0x0660,
          0x0272, 0x04E4, 0x4E40, 0x2720, 0xC936, 0x936C, 0x39C6, 0x639C, 0x9336, 0x9CC6, 0x817E, 0xE718, 0xCCF0, 0x0FCC, 0x7744, 0xEE22)
BC7_P3 = (0xAA685050, 0x6A5A5040, 0x5A5A4200, 0x5450A0A8, 0xA5A50000, 0xA0A05050, 0x5555A0A0, 0x5A5A5050,
          0xAA550000, 0xAA555500, 0xAAAA5500, 0x90909090, 0x94949494, 0xA4A4A4A4, 0xA9A59450, 0x2A0A4250,
          0xA5945040, 0x0A425054, 0xA5A5A500, 0x55A0A0A0, 0xA8A85454, 0x6A6A4040, 0xA4A45000, 0x1A1A0500,
          0x0050A4A4, 0xAAA59090, 0x14696914, 0x69691400, 0xA08585A0, 0xAA821414, 0x50A4A450, 0x6A5A0200,
          0xA9A58000, 0x5090A0A8, 0xA8A09050, 0x24242424, 0x00AA5500, 0x24924924, 0x24499224, 0x50A50A50,
          0x500AA550, 0xAAAA4444, 0x66660000, 0xA5A0A5A0, 0x50A050A0, 0x69286928, 0x44AAAA44, 0x66666600,
          0xAA444444, 0x54A854A8, 0x95809580, 0x96969600, 0xA85454A8, 0x80959580, 0xAA141414, 0x96960000,
          0xAAAA1414, 0xA05050A0, 0xA0A5A5A0, 0x96000000, 0x40804080, 0xA9A8A9A8, 0xAAAAAA44, 0x2A4A5254)
# anchor pixel of subset 1 (2 subsets), of subsets 1 and 2 (3 subsets)
BC7_A2 = (15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 2, 8, 2, 2, 8, 8, 15, 2, 8, 2, 2, 8, 8, 2, 2,
          15, 15, 6, 8, 2, 8, 15, 15, 2, 8, 2, 2, 2, 15, 15, 6, 6, 2, 6, 8, 15, 15, 2, 2, 15, 15, 15, 15, 15, 2, 2, 15)
BC7_A3 = (3, 3, 15, 15, 8, 3, 15, 15, 8, 8, 6, 6, 6, 5, 3, 3, 3, 3, 8, 15, 3, 3, 6, 10, 5, 8, 8, 6, 8, 5, 15, 15,
          8, 15, 3, 5, 6, 10, 8, 15, 15, 3, 15, 5, 15, 15, 15, 15, 3, 15, 5, 5, 5, 8, 5, 10, 5, 10, 8, 13, 15, 12, 3, 3)
BC7_B3 = (15, 8, 8, 3, 15, 15, 3, 8, 15, 15, 15, 15, 15, 15, 15, 8, 15, 8, 15, 3, 15, 8, 15, 8, 3, 15, 6, 10, 15, 15, 10, 8,
          15, 3, 15, 10, 10, 8, 9, 10, 6, 15, 8, 15, 3, 6, 6, 8, 15, 3, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 3, 15, 15, 8)
BC7_W = {2: (0, 21, 43, 64), 3: (0, 9, 18, 27, 37, 46, 55, 64), 4: (0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64)}
# The 16 pixels of a block are computed at once, one big integer per colour channel with a 16-bit lane per pixel.
BC7_ONES = int.from_bytes(b'\1\0' * 16, 'little')  # 1 in every lane
BC7_HALF, BC7_BYTE = 32 * BC7_ONES, 255 * BC7_ONES
BC7_HEX, BC7_OCT = bytearray(256), bytearray(256)  # digit of '%x' / '%o' → weight of a 4-bit / 3-bit index
BC7_LO, BC7_HI = bytearray(256), bytearray(256)  # hex digit → weights of the two 2-bit indices in it
for _d, _c in enumerate(b'0123456789abcdef'):
    BC7_HEX[_c], BC7_OCT[_c], BC7_LO[_c], BC7_HI[_c] = BC7_W[4][_d], BC7_W[3][_d % 8], BC7_W[2][_d & 3], BC7_W[2][_d >> 2]
BC7_SUBSETS = {}  # (subsets, partition) → (anchor pixels in rising order, per subset: its lanes, 64 in each of them)


def bc7_subsets(ns, part):
    if (ns, part) not in BC7_SUBSETS:
        sub = [0] * 16 if ns == 1 else [BC7_P2[part] >> i & 1 for i in range(16)] if ns == 2 else [BC7_P3[part] >> 2 * i & 3 for i in range(16)]
        anchors = sorted(((0,), (0, BC7_A2[part]), (0, BC7_A3[part], BC7_B3[part]))[ns - 1])
        lanes = [sum(1 << 16 * i for i in range(16) if sub[i] == n) for n in range(ns)]
        BC7_SUBSETS[ns, part] = anchors, [(0xffff * x, 64 * x) for x in lanes]
    return BC7_SUBSETS[ns, part]


def bc7_weights(v, bits, anchors):
    """Index bits of the 16 pixels (anchors lack their top bit, which is 0) → their weights, one per lane."""
    for a in anchors:
        pos = a * bits + bits - 1
        v = v & (1 << pos) - 1 | v >> pos << pos + 1
    lanes = bytearray(32)
    if bits == 4:
        lanes[::2] = (b'%016x' % v).translate(BC7_HEX)[::-1]
    elif bits == 3:
        lanes[::2] = (b'%016o' % v).translate(BC7_OCT)[::-1]
    else:
        digits = (b'%08x' % v)[::-1]
        lanes[::4], lanes[2::4] = digits.translate(BC7_LO), digits.translate(BC7_HI)
    return int.from_bytes(lanes, 'little')


def bc7_block(block):
    """One 16-byte block → its 4 pixel rows (RGBA, 16 bytes each)."""
    v = int.from_bytes(block, 'little')
    m = (v & -v).bit_length() - 1
    if not 0 <= m <= 7:
        return (bytes(16),) * 4  # reserved mode: transparent black
    ns, pb, rb, isb, cb, ab, epb, spb, ib, ib2 = BC7_MODES[m]
    v >>= m + 1
    part, v = v & (1 << pb) - 1, v >> pb
    rot, v = v & (1 << rb) - 1, v >> rb
    sel, v = v & isb, v >> isb
    ne, ends = ns * 2, []  # per channel: the endpoints' values
    for bits in (cb, cb, cb, ab):
        ends.append([v >> bits * e & (1 << bits) - 1 for e in range(ne)])
        v >>= bits * ne
    if epb or spb:  # one more bit per endpoint or per subset
        for c in range(4 if ab else 3):
            ends[c] = [x << 1 | v >> (e if epb else e >> 1) & 1 for e, x in enumerate(ends[c])]
        v >>= ne if epb else ns
    anchors, lanes = bc7_subsets(ns, part)
    n = 16 * ib - ns
    wc = wa = bc7_weights(v & (1 << n) - 1, ib, anchors)
    if ib2:  # modes 4 and 5: colour and alpha have their own indices
        wa = bc7_weights(v >> n & (1 << 16 * ib2 - 1) - 1, ib2, (0,))
        if sel:
            wc, wa = wa, wc
    # per subset the weights of its two endpoints, lane by lane
    pc = pa = [(full - (w := wc & lane), w) for lane, full in lanes]
    if ib2:
        pa = [(lanes[0][1] - wa, wa)]
    planes = []
    for c, (bits, pairs) in enumerate(((cb, pc), (cb, pc), (cb, pc), (ab, pa))):
        if not bits:
            planes.append(b'\xff' * 16)  # no alpha: opaque
            continue
        bits += bool(epb or spb)
        up, down, total = 8 - bits, 2 * bits - 8, BC7_HALF  # endpoints to 8 bits
        for (w0, w1), e0, e1 in zip(pairs, ends[c][::2], ends[c][1::2]):
            total += (e0 << up | e0 >> down) * w0 + (e1 << up | e1 >> down) * w1
        planes.append((total >> 6 & BC7_BYTE).to_bytes(32, 'little')[::2])
    if rot:
        planes[rot - 1], planes[3] = planes[3], planes[rot - 1]
    px = bytearray(64)
    px[::4], px[1::4], px[2::4], px[3::4] = planes
    return bytes(px[:16]), bytes(px[16:32]), bytes(px[32:48]), bytes(px[48:])


def bc7(data, w, h):
    """BC7 blocks -> RGBA bytes (w, h multiples of 4). Equal blocks (sea, flat land: about half) are decoded once."""
    seen, rows, n = {}, [], w * 4  # a row of blocks: w / 4 blocks of 16 bytes
    for y in range(0, h // 4 * n, n):
        blocks = [seen.get(b) or seen.setdefault(b, bc7_block(b)) for b in (data[i:i + 16] for i in range(y, y + n, 16))]
        rows += map(b''.join, zip(*blocks))
    return b''.join(rows)


def dds(data, level=0):
    """(rgba, w, h) of one mip level of a BC7 .dds (sizes that are multiples of 4 down to that level)."""
    h, w = struct.unpack_from('<II', data, 12)
    off = 148  # DDS header + DX10 header
    for _ in range(level):
        off += w // 4 * (h // 4) * 16
        w, h = w // 2, h // 2
    return bc7(data[off:off + w // 4 * (h // 4) * 16], w, h), w, h


def png(rgba, w, h):
    raw = b''.join(b'\0' + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    chunk = lambda kind, d: struct.pack('>I', len(d)) + kind + d + struct.pack('>I', zlib.crc32(kind + d))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(raw), 1)) + chunk(b'IEND', b''))


def map_layout(game, isles):
    """{element: (image, width, height, turns, u, v)}: each island's map image, the tile size of the land it shows,
    its quarter turns and where its middle sits in the game's view. That view is the map turned 45° counter-clockwise:
    u = (x - y)·√½ points right, v = (x + y)·√½ points up. The image (gamemapimage) covers the island's
    ActiveMapRect, row 0 = north; the template turns islands counter-clockwise in their square, (x, y) -> (size - y, x)."""
    out = {}
    for i, x, y, turns, path in isles:
        base = path[:-4]  # …/<name>.a7m
        info = FileDB(game_file(game, base + '.a7minfo'))
        size = struct.unpack('<i', info.attr(info.root, 'MapSize')[1][:4])[0]
        x0, y0, x1, y1 = struct.unpack('<4i', info.attr(info.root, 'ActiveMapRect')[1][:16])
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for _ in range(turns):
            cx, cy = size - cy, cx
        d, n = base.rsplit('/', 1)
        out[i] = (f'{d}/_gamedata/{n}/gamemapimage_0.dds', x1 - x0, y1 - y0, turns,
                  (x + cx - y - cy) * DIAG, (x + cx + y + cy) * DIAG)
    return out


def map_fit(layout, w, h, pad=10):
    """(k, ox, oy) that fit the islands into a w × h canvas: k pixels per tile, canvas x = ox + u·k, y = oy - v·k."""
    r = [(u, v, (aw + ah) * DIAG / 2) for _, aw, ah, _, u, v in layout.values()]  # a turned island fills a square
    u0, u1 = min(u - d for u, _, d in r), max(u + d for u, _, d in r)
    v0, v1 = min(v - d for _, v, d in r), max(v + d for _, v, d in r)
    k = min((w - 2 * pad) / (u1 - u0), (h - 2 * pad) / (v1 - v0))
    return k, w / 2 - (u0 + u1) / 2 * k, h / 2 + (v0 + v1) / 2 * k


def map_dots(db, layout):
    """{element: ((u, v, colour), …)}: the buildings on each island, in tiles from its middle in the game's view;
    yellow = the player's, red = another owner's (rivals, traders, pirates)."""
    built, out = Save.buildings(db), {}
    for el, areas in Save.areas(db).items():
        for aid, area in areas:
            owner = db.attr(area, 'OwnerProfile')
            if el in layout and owner:
                *_, u, v = layout[el]
                colour = 0xff5ed7ff if Save.is_player(db, area) else 0xff5c7aff  # ABGR of #ffd75e, #ff7a5c
                out[el] = out.get(el, ()) + tuple(((x - y) * DIAG - u, (x + y) * DIAG - v, colour) for o, x, y in built.get(aid, ())
                                                  if o in (None, struct.unpack('<i', owner[1][:4])[0]))
    return out


@functools.lru_cache(maxsize=12)
def mip(game, img, level):
    """(pixels as array('I'), w, h) of one mip level of an island's map image; the last ones stay decoded."""
    # ponytail: decoded in this one process and kept only in memory (a region at zoom 4 takes about 2 s);
    # if that gets too slow, store decoded levels in DATA or decode in several processes
    rgba, w, h = dds(game_file(game, img), level)
    return array.array('I', rgba), w, h


@functools.lru_cache(maxsize=200)
def render_isle(game, img, aw, ah, turns, k, dots=()):
    """Square PNG of an island at k pixels per tile in the game's view (turned 45° + its quarter turns
    counter-clockwise), the island's middle in the middle of the image. dots = ((u, v, colour), …): buildings,
    in tiles from the middle. Only slices, no loop over pixels: the image is scaled to √2·k pixels per tile,
    then every row of the result is one diagonal of it."""
    mh, mw = struct.unpack_from('<II', game_file(game, img), 12)
    lvl = 0  # smallest mip level that is still at least as sharp as needed
    while lvl < 4 and mw >> lvl + 1 >= aw * k and mh >> lvl + 1 >= ah * k:
        lvl += 1
    px, mw, mh = mip(game, img, lvl)
    w, h = max(1, round(aw * k / DIAG)), max(1, round(ah * k / DIAG))
    rows = array.array('I')
    for y in range(h):
        y = (2 * y + 1) * mh // (2 * h) * mw
        rows += px[y:y + mw]
    big = array.array('I', bytes(4 * w * h))
    for x in range(w):
        big[x::w] = rows[(2 * x + 1) * mw // (2 * w)::mw]
    n = max(1, math.ceil((aw + ah) * k * DIAG))
    a, b = ((1, 1), (-1, 1), (-1, -1), (1, -1))[turns % 4]  # one pixel to the right = (a, b) in the scaled image
    out = array.array('I', bytes(4 * n * n))
    for j in range(n):
        qy, lo, hi = j - n // 2, -(n // 2), n - n // 2  # pixel qx from the middle shows big[h/2 + b·qx + a·qy][w/2 + a·qx - b·qy]
        x, y = w // 2 - b * qy, h // 2 + a * qy
        for at, sign, size in ((x, a, w), (y, b, h)):  # the part of the row that lies inside the image
            lo, hi = (max(lo, -at), min(hi, size - at)) if sign > 0 else (max(lo, at - size + 1), min(hi, at + 1))
        if lo < hi:
            start = (y + b * lo) * w + x + a * lo
            stop = start + (hi - lo) * (b * w + a)
            out[j * n + lo + n // 2:j * n + hi + n // 2] = big[start:stop if stop >= 0 else None:b * w + a]
    r = max(1, round(k))  # ponytail: every building is a dot of about 2 tiles; real footprints are in the game's .ifo files
    for u, v, colour in dots:
        x, y = round(n / 2 + u * k), round(n / 2 - v * k)
        x0, x1 = max(0, x - r), min(n, x + r)
        for y in range(max(0, y - r), min(n, y + r)) if x0 < x1 else ():
            out[y * n + x0:y * n + x1] = array.array('I', [colour]) * (x1 - x0)
    return png(out.tobytes(), n, n)


def menu_key(key):
    """Save tag -> key used in assets.xml."""
    return ALIAS.get(key, key.removeprefix('Setup'))


def label(names, key):
    """[headline, options] for a setting key, or None if the game has no menu text for it."""
    return names['settings'].get(menu_key(key))


def grouped(names, keys):
    """[(tab, subheading, key)] in the game's menu order; keys the menu lacks go last, alphabetically."""
    first = {}
    for i, (tab, sub, k) in enumerate(names['menu']):
        first.setdefault(k, (i, tab, sub))
    rest = (len(names['menu']), t('Ohne Menütext im Spiel (Rohwerte)'), '')
    return [(tab, sub, k) for (_, tab, sub), _, k in sorted((first.get(menu_key(k), rest), menu_key(k), k) for k in keys)]


# ---------- updates from the GitHub releases ----------

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Anno117-Savegame-Editor'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def version(tag):
    return tuple(int(n) for n in re.findall(r'\d+', tag))


def newer_release():
    """The latest release on GitHub if it is newer than this program, else None."""
    rel = json.loads(fetch(UPDATE_API))
    return rel if version(rel['tag_name']) > version(VERSION) else None


def install_update(asset, exe):
    """Download the new exe, check its SHA-256 and swap it in (a running exe can be renamed, not overwritten)."""
    data = fetch(asset['browser_download_url'])
    if asset.get('digest') != 'sha256:' + hashlib.sha256(data).hexdigest():
        raise ValueError(t('Prüfsumme des Downloads stimmt nicht.'))
    new, old = exe + '.new', exe + '.old'
    with open(new, 'wb') as f:
        f.write(data)
    if os.path.exists(old):
        os.remove(old)
    os.replace(exe, old)
    try:
        os.replace(new, exe)
    except OSError:
        os.replace(old, exe)  # keep the running version in place
        raise


# ---------- window ----------

def load_prefs():
    try:
        with open(PREFS, encoding='utf-8') as f:
            prefs = json.load(f)
        return prefs if isinstance(prefs, dict) else {}
    except (OSError, ValueError):
        return {}


def documents():
    """The real Documents folder (follows a OneDrive redirect)."""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)  # CSIDL_PERSONAL
        return buf.value or os.path.expanduser('~')
    except (AttributeError, OSError):
        return os.path.expanduser('~')


def windows_dark():
    """True if Windows apps are set to dark mode (default before the user picks one)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as k:
            return winreg.QueryValueEx(k, 'AppsUseLightTheme')[0] == 0
    except OSError:
        return False


def windows_lang():
    """'de' if Windows runs in German, else 'en' (default before the user picks one)."""
    try:
        import ctypes
        return 'de' if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3ff == 0x07 else 'en'
    except (AttributeError, OSError):
        return 'de'


def run_ui():
    global LANG
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog, font as tkfont

    prefs = load_prefs()
    LANG = prefs['lang'] if prefs.get('lang') in LANGS else windows_lang()
    # While islands render in the background, every call into Tk waits for the interpreter: up to one switch interval
    # (5 ms by default), a hundred times per redraw. A short interval keeps the window fluid. Not below 1 ms: measured
    # with 0.5 ms, two rendering threads slowed each other down sevenfold.
    sys.setswitchinterval(.001)
    root = tk.Tk()
    root.title(TITLE)
    root.geometry('860x660')
    root.report_callback_exception = lambda typ, err, tb: messagebox.showerror(TITLE, f'{typ.__name__}: {err}')
    status = tk.StringVar(value=t('Lade Namen aus den Spieldateien …'))
    s = {'save': None, 'storages': [], 'regions': [], 'maps': {}, 'dots': {}}
    names = {'descs': {}}  # game names; loaded once the game folder is known (the tooltip may fire before)
    texts = []  # (widget, German text), re-translated when the language changes

    def tr(widget, text):
        texts.append((widget, text))
        widget.configure(text=t(text))
        return widget

    def table(parent, cols, widths):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, pady=6)
        tv = ttk.Treeview(frame, columns=cols, show='headings')
        for c, w in zip(cols, widths):
            tv.column(c, width=w, anchor='w' if c == cols[0] else 'e')
        sb = ttk.Scrollbar(frame, command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        return tv

    def search(parent, show):
        """Search field in front of a table; returns the test whether a row with these texts is to be shown."""
        text = tk.StringVar()
        tr(ttk.Label(parent), 'Suche:').pack(side='left')
        ttk.Entry(parent, textvariable=text, width=24).pack(side='left', padx=4)
        text.trace_add('write', lambda *_: s['save'] and show())
        return lambda *words: text.get().strip().casefold() in ' '.join(map(str, words)).casefold()

    bar = ttk.Frame(root, padding=6)
    bar.pack(fill='x')
    nb = ttk.Notebook(root)
    nb.pack(fill='both', expand=True, padx=6)
    ttk.Label(root, textvariable=status, padding=6).pack(fill='x')

    tab1 = ttk.Frame(nb, padding=6)
    nb.add(tab1, text=t('Denare & Lager'))
    top1 = ttk.Frame(tab1)
    top1.pack(fill='x')
    pick = ttk.Combobox(top1, state='readonly', width=60)
    pick.pack(side='left', padx=(0, 10))
    goods_match = search(top1, lambda: show_storage())
    goods = table(tab1, ('Ware', 'Menge', 'GUID'), (440, 160, 100))
    row = ttk.Frame(tab1)
    row.pack(fill='x')
    tr(ttk.Label(row), 'Doppelklick ändert eine Menge. Mehrere Zeilen mit Strg/Umschalt markieren und').pack(side='left')
    tr(ttk.Button(row, command=lambda: edit_goods(goods.selection())), 'Auswahl setzen …').pack(side='left', padx=6)

    tab2 = ttk.Frame(nb, padding=6)
    nb.add(tab2, text=t('Spieleinstellungen'))
    tr(ttk.Label(tab2, wraplength=800), 'Doppelklick zum Ändern. Gruppen und Reihenfolge wie im Spielmenü. Grau = '
       'Startoptionen und Kartenerzeugung: Sie wirken nur beim Spielbeginn und sind darum gesperrt.').pack(anchor='w')
    top2 = ttk.Frame(tab2)
    top2.pack(fill='x', pady=(6, 0))
    sets_match = search(top2, lambda: show_settings())
    sets = table(tab2, ('Wert',), (320,))
    sets.configure(show='tree headings')  # setting names in the tree column, grouped like the game menu
    sets.column('#0', width=440)
    sets.column('Wert', anchor='e')
    bold = tkfont.nametofont('TkDefaultFont').copy()
    bold.configure(weight='bold')
    sets.tag_configure('group', font=bold)
    sets.tag_configure('locked', foreground='#888888')  # readable on light and dark

    tab3 = ttk.Frame(nb, padding=6)
    nb.add(tab3, text=t('Fruchtbarkeiten'))
    row3 = ttk.Frame(tab3)
    row3.pack(fill='x')
    region = ttk.Combobox(row3, state='readonly', width=20)
    region.pack(side='left')
    houses = tk.BooleanVar(value=True)
    tr(ttk.Checkbutton(row3, variable=houses, command=lambda: view['lay'] and (sharp.clear(), fill())),
       'Gebäude zeigen').pack(side='left', padx=10)
    tr(ttk.Label(tab3, wraplength=820), 'Maus auf einer Insel zeigt ihre Fruchtbarkeiten, ein Klick ändert sie. '
       'Gelb = deins, Rot = andere Parteien. Mausrad zoomt, Ziehen verschiebt.').pack(anchor='w', pady=(4, 0))
    cv = tk.Canvas(tab3, bg='#1d4a6b', highlightthickness=0)  # sea
    cv.pack(fill='both', expand=True, pady=(6, 0))
    SLOT = {'Mountain': 'Berg', 'River': 'Fluss', 'Marsh': 'Sumpf'}

    # sorting: click a heading → ascending, again → descending, a third time → original order
    order = {}  # table → (column, descending)

    def heads(tv):
        col, desc = order.get(tv, (None, False))
        for c in ('#0',) * (tv is sets) + tv['columns']:
            tv.heading(c, text=t('Einstellung' if c == '#0' else c) + (' ▼' if desc else ' ▲') * (c == col),
                       command=lambda c=c: click_head(tv, c))

    def sort_key(tv, col):
        def key(iid):
            v = tv.item(iid, 'text') if col == '#0' else str(tv.set(iid, col))
            n = v.replace('.', '').replace(',', '')  # amounts carry thousands separators
            # numbers before texts; texts case-insensitive, Ä/Ö/Ü as A/O/U, quotes and hyphens ignored
            text = ''.join(ch for ch in unicodedata.normalize('NFD', v.casefold()) if ch.isalnum() or ch == ' ')
            return (0, int(n), '') if n.isdigit() else (1, 0, text)
        return key

    def resort(tv, parent=''):
        """Apply the clicked sort; in the settings only rows move, groups keep the menu order."""
        if tv not in order:
            return
        col, desc = order[tv]
        kids = tv.get_children(parent)
        groups = [k for k in kids if tv.get_children(k)]
        rows = sorted((k for k in kids if k not in groups), key=sort_key(tv, col), reverse=desc)
        for i, k in enumerate(rows + groups):
            tv.move(k, parent, i)
        for g in groups:
            resort(tv, g)

    def click_head(tv, col):
        c, desc = order.get(tv, (None, False))
        if c != col or not desc:
            order[tv] = (col, c == col)
        else:
            del order[tv]
        heads(tv)
        if tv in order:
            resort(tv)
        elif s['save']:
            {goods: show_storage, sets: show_settings}[tv]()

    for tv in (goods, sets):
        heads(tv)

    def dirty():
        root.title(TITLE + ' *')

    def show_storage(*_):
        _, db, tag = s['storages'][pick.current()]
        goods.delete(*goods.get_children())
        for guid, amount in s['save'].storage(db, tag).items():
            name = names['assets'].get(str(guid), f'GUID {guid}')
            if goods_match(name, guid):
                goods.insert('', 'end', iid=str(guid), values=(name, f'{amount:,}'.replace(',', '.' if LANG == 'de' else ','), guid))
        resort(goods)

    def edit_goods(rows):
        if not rows:
            return
        _, db, tag = s['storages'][pick.current()]
        items = s['save'].storage(db, tag)
        what = goods.set(rows[0], 'Ware') if len(rows) == 1 else t('{} markierte Waren').format(len(rows))
        v = simpledialog.askinteger(TITLE, t('Neue Menge für {}:').format(what), initialvalue=items[int(rows[0])],
                                    minvalue=0, maxvalue=2 ** 31 - 1, parent=root)
        if v is None:
            return
        for r in rows:
            items[int(r)] = v
        s['save'].set_storage(db, tag, items)
        dirty()
        show_storage()
        goods.selection_set(rows)

    # region map in the game's 45° view: island images from the game files, rendered in the background.
    # The wheel zooms, dragging moves the map, a click opens the fertility window.
    shown = {}  # canvas image → (template element, photo, left, top)
    items = {}  # template element → canvas image
    sharp = set()  # template elements whose image is rendered for this zoom (others show a scaled stand-in)
    view = {'zoom': 1, 'job': 0, 'timer': None, 'press': None, 'lay': {}}

    def spot(i, f=1):
        """Canvas x, y of an island's middle and half the side of its image (f: as if everything were f times as big)."""
        _, aw, ah, _, u, v = view['lay'][i]
        k = view['k'] * f
        return view['ox'] * f + u * k, view['oy'] * f - v * k, (aw + ah) * k * DIAG / 2

    def in_view(i, f=1):
        x, y, r = spot(i, f)
        x0, y0 = cv.canvasx(0), cv.canvasy(0)
        return x + r > x0 and x - r < x0 + cv.winfo_width() and y + r > y0 and y - r < y0 + cv.winfo_height()

    def put(i, img, final):
        if i in items:
            del shown[items[i]]
            cv.delete(items[i])
        x, y, _ = spot(i)
        left, top = round(x - img.width() / 2), round(y - img.height() / 2)
        items[i] = cv.create_image(left, top, anchor='nw', image=img)
        shown[items[i]] = (i, img, left, top)
        cv.tag_raise('name')
        cv.tag_raise('tip')
        if final:
            sharp.add(i)

    def fill():
        """Render the islands in view that have no sharp image yet, the ones in the middle first."""
        view['job'] += 1
        me, k, game, lay = view['job'], view['k'], prefs['game'], view['lay']
        mx, my = cv.canvasx(cv.winfo_width() / 2), cv.canvasy(cv.winfo_height() / 2)
        todo = sorted((i for i in lay if i not in sharp and in_view(i)),
                      key=lambda i: (spot(i)[0] - mx) ** 2 + (spot(i)[1] - my) ** 2)
        done, dots = collections.deque(), view['dots'] if houses.get() else {}

        def work():
            for i in todo:
                if me != view['job']:
                    return  # zoomed, moved or switched meanwhile
                try:
                    done.append((i, render_isle(game, *lay[i][:4], k, dots.get(i, ()))))
                except Exception as e:  # game files missing or changed
                    done.append((i, e))

        def poll():
            if done and me == view['job']:  # one image per turn (Tk takes 0.15 s to load a big one): events come in between
                i, data = done.popleft()
                if isinstance(data, Exception):
                    cv.create_text(mx, my, text=t('Karte nicht lesbar: {}').format(data), fill='white', width=cv.winfo_width() - 40)
                    return
                put(i, tk.PhotoImage(data=data), True)
            if me == view['job'] and (worker.is_alive() or done):
                root.after(1 if done else 40, poll)

        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        poll()

    def isle_areas(db, i):
        """[(name, the player's?, AreaInfo entry)] of an island's areas, the player's first. Areas sharing a city name
        (a character's plot on your island) count once."""
        out = {}
        for _, a in sorted(Save.areas(db).get(i, ()), key=lambda x: not Save.is_player(db, x[1])):
            city = db.attr(a, 'CityNameGuid')
            out.setdefault(city[1] if city else id(a), (Save.area_name(db, a, names), Save.is_player(db, a), a))
        return list(out.values())

    def draw_map(*_, old=()):
        """Lay the region out for the canvas size and zoom; old = [(element, image)] to show until the sharp ones are there."""
        w, h = cv.winfo_width(), cv.winfo_height()
        if not s['save'] or w < 100 or h < 100:
            return  # tab not shown yet: <Configure> calls again
        guid, db = s['regions'][region.current()]
        view['job'] += 1
        cv.delete('all')
        for d in (shown, items, sharp):
            d.clear()
        try:
            if guid not in s['maps']:
                s['maps'][guid] = map_layout(prefs['game'], s['save'].map_islands(db))
                s['dots'][guid] = map_dots(db, s['maps'][guid])
            k, ox, oy = map_fit(s['maps'][guid], w, h)
        except Exception as e:  # game files missing or changed
            cv.create_text(w // 2, h // 2, text=t('Karte nicht lesbar: {}').format(e), fill='white', width=w - 40)
            view['lay'] = {}
            return
        z = view['zoom']
        view.update(lay=s['maps'][guid], dots=s['dots'][guid], tip=None, k=k * z, ox=ox * z, oy=oy * z)
        cv.configure(scrollregion=(0, 0, w * z, h * z))
        # the names of an island's areas, one below the other; the player's first, then other owners', then free ones
        # where there is room left
        line, labels = bold.metrics('linespace'), []
        for i in view['lay']:
            areas = isle_areas(db, i)
            labels += [(0 if mine else 1 if db.attr(a, 'OwnerProfile') else 2, spot(i)[0], spot(i)[1] + (n - (len(areas) - 1) / 2) * line, name)
                       for n, (name, mine, a) in enumerate(areas)]
        for other, x, y, name in sorted(labels, key=lambda lab: lab[0]):
            font, before = 'TkDefaultFont' if other else bold, set(cv.find_withtag('name'))
            new = [cv.create_text(x + d, y + d, text=name, fill=colour, font=font, tags='name')
                   for d, colour in ((1, 'black'), (0, 'white' if other else '#ffd75e'))]  # shadow, then text
            if before & set(cv.find_overlapping(*cv.bbox(new[0]))):
                cv.delete(*new)
        for i, img in old:
            put(i, img, False)
        fill()

    def zoom_map(e):
        z = min(8, max(1, view['zoom'] * (2 if e.delta > 0 else .5)))
        if not view['lay'] or z == view['zoom']:
            return
        f = z / view['zoom']
        w, h = cv.winfo_width() * z, cv.winfo_height() * z
        x, y = cv.canvasx(e.x) * f - e.x, cv.canvasy(e.y) * f - e.y  # new corner: the spot under the mouse stays
        cv.configure(scrollregion=(0, 0, w, h))
        cv.xview_moveto(x / w)
        cv.yview_moveto(y / h)
        view['zoom'] = z  # stand-ins from the images shown so far, only for what stays in view
        draw_map(old=[(i, img.zoom(2) if f > 1 else img.subsample(2)) for i, img, *_ in shown.values() if in_view(i, f)])

    def map_press(e):
        tip_off()
        view['press'] = (e.x, e.y)
        cv.scan_mark(e.x, e.y)

    def map_drag(e):
        if view['press'] and abs(e.x - view['press'][0]) + abs(e.y - view['press'][1]) > 4:
            view['press'] = None  # moving the map, not a click
        if not view['press']:
            cv.scan_dragto(e.x, e.y, gain=1)

    def map_release(e):
        if not view['press']:
            fill()
        elif (i := isle_at(e)) is not None:
            fert_window(i)

    def isle_at(e):
        """Template element under the mouse if that island has areas (settleable), else None."""
        x, y = cv.canvasx(e.x), cv.canvasy(e.y)
        for item in reversed(cv.find_overlapping(x, y, x, y)):
            i, img, left, top = shown.get(item, (None,) * 4)
            if img and not img.transparency_get(int(x - left), int(y - top)):
                return i if i in Save.areas(s['regions'][region.current()][1]) else None
        return None

    def tip_off(*_):
        cv.delete('tip')
        view['tip'] = None

    def map_hover(e):
        """Next to the mouse: the areas of the island under it, each with the icons of its fertilities and deposits."""
        i = isle_at(e)
        cv.configure(cursor='hand2' if i is not None else '')
        if i != view.get('tip'):
            tip_off()
        if i is None:
            return
        if view['tip'] is None:
            view['tip'], db, y = i, s['regions'][region.current()][1], 0
            box = cv.create_rectangle(0, 0, 0, 0, fill='#202020', outline='#ffd75e', tags='tip')
            legend = [g for g, _ in names['ferts']]
            for name, _, a in isle_areas(db, i):
                cv.create_text(0, y, anchor='nw', text=name, fill='white', font=bold, tags='tip')
                y += bold.metrics('linespace') + 2
                have = sorted(Save.fertilities(db, a), key=lambda g: legend.index(g) if g in legend else len(legend))
                for n, g in enumerate(have):
                    cv.create_image(n % 8 * 34, y + n // 8 * 34, anchor='nw', image=icon(g, 4), tags='tip')
                y += -(-len(have) // 8) * 34 + 4
            x0, y0, x1, y1 = cv.bbox('tip')
            cv.coords(box, x0 - 5, y0 - 5, x1 + 5, y1 + 1)
        x0, y0, x1, y1 = cv.bbox('tip')  # below right of the mouse, but inside the view
        left, top = cv.canvasx(0), cv.canvasy(0)
        x = max(left, min(cv.canvasx(e.x) + 16, left + cv.winfo_width() - (x1 - x0)))
        y = cv.canvasy(e.y) + 20
        if y + y1 - y0 > top + cv.winfo_height():
            y = cv.canvasy(e.y) - 12 - (y1 - y0)
        cv.move('tip', x - x0, y - y0)

    icons = {}

    def icon(g, level=3):
        """The fertility's goods icon (mip of the game's 512 px texture: level 3 = 64 px, 4 = 32 px), '' if the game has none."""
        if (g, level) not in icons:
            try:
                icons[g, level] = tk.PhotoImage(data=png(*dds(game_file(prefs['game'], names['icons'][str(g)]), level)))
            except (KeyError, OSError):
                icons[g, level] = ''
        return icons[g, level]

    def fert_window(i):
        guid, db = s['regions'][region.current()]
        areas, slot = Save.areas(db)[i], dict(names['ferts'])
        here = {g for lst in Save.areas(db).values() for _, a in lst for g in Save.fertilities(db, a)}  # anywhere in this region
        legend = list(slot) + sorted(here - set(slot))
        win = tk.Toplevel(root)
        win.title(' · '.join(Save.area_name(db, a, names) for _, a in areas) + ' – ' + t('Fruchtbarkeiten'))
        win.transient(root)
        win.grab_set()
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill='both', expand=True)
        which = ttk.Combobox(frame, state='readonly', width=40, values=[Save.area_name(db, a, names) for _, a in areas])
        which.current(next((n for n, (_, a) in enumerate(areas) if Save.is_player(db, a)), 0))
        if len(areas) > 1:  # Aegyptus: several sepats on one piece of land
            which.pack(anchor='w')
        ttk.Label(frame, wraplength=820, text=t('Haken setzen oder entfernen. Steht ein Bauplatz dabei (Berg, Fluss, Sumpf), '
                                                'wirkt sie nur, wenn die Insel so einen Bauplatz hat.')).pack(anchor='w', pady=(6, 0))
        marks = {}

        def toggle(g):
            aid, a = areas[which.current()]
            have = Save.fertilities(db, a)
            s['save'].set_fertilities(db, aid, a, [x for x in have if x != g] if g in have else have + [g])
            dirty()

        for title, gs in ((names['assets'].get(str(guid), ''), [g for g in legend if g in here]),
                          (t('Andere Regionen'), [g for g in legend if g not in here])):
            if gs:
                ttk.Label(frame, text=title, font=bold).pack(anchor='w', pady=(10, 2))
                grid = ttk.Frame(frame)
                grid.pack(anchor='w')
            for n, g in enumerate(gs):
                marks[g] = tk.BooleanVar()
                text = names['assets'].get(str(g), f'GUID {g}') + (f' ({t(SLOT[slot[g]])})' if slot.get(g) in SLOT else '')
                ttk.Checkbutton(grid, text=text, image=icon(g), compound='left', variable=marks[g],
                                command=lambda g=g: toggle(g)).grid(row=n // 5, column=n % 5, sticky='w', padx=4, pady=1)

        def load(*_):
            have = Save.fertilities(db, areas[which.current()][1])
            for g, v in marks.items():
                v.set(g in have)

        which.bind('<<ComboboxSelected>>', load)
        load()
        ttk.Button(frame, text=t('Schließen'), command=win.destroy).pack(anchor='e', pady=(10, 0))

    def value_text(key):
        v, lab = s['save'].setting(key), label(names, key)
        if not lab:
            return v
        return lab[1][v] if v < len(lab[1]) else t('Wert {} (unbekannt)').format(v)

    def show_settings():
        sets.delete(*sets.get_children())
        for tab, sub, key in grouped(names, s['save'].refs):
            lab, parent = label(names, key), ''
            if not sets_match(tab, sub, lab[0] if lab else menu_key(key)):
                continue
            for title in (tab, sub):  # group rows: '/tab' and '/tab/sub' (setting keys never start with '/')
                if title:
                    iid = f'{parent}/{title}'
                    if not sets.exists(iid):
                        sets.insert(parent, 'end', iid=iid, text=title, open=True, tags=('group',))
                    parent = iid
            sets.insert(parent, 'end', iid=key, text=lab[0] if lab else menu_key(key), values=(value_text(key),),
                        tags=('locked',) * (key in START_ONLY))
        resort(sets)

    def choose(title, options, current):
        win = tk.Toplevel(root)
        win.title(title)
        win.transient(root)
        win.grab_set()
        lb = tk.Listbox(win, height=len(options), width=45, exportselection=False)
        for o in options:
            lb.insert('end', o)
        if current < len(options):
            lb.selection_set(current)
        lb.pack(padx=10, pady=10)
        res = []

        def ok(*_):
            res.extend(lb.curselection())
            win.destroy()

        lb.bind('<Double-1>', ok)
        ttk.Button(win, text=t('Übernehmen'), command=ok).pack(pady=(0, 10))
        win.wait_window()
        return res[0] if res else None

    def edit_setting(key):
        if key in START_ONLY:
            status.set(t('Nur beim Spielbeginn wirksam, darum gesperrt: {}').format(sets.item(key, 'text')))
            return
        v, lab = s['save'].setting(key), label(names, key)
        if lab:
            nv = choose(lab[0], lab[1], v)
        else:
            nv = simpledialog.askinteger(TITLE, t('{} (Rohwert)').format(key) + ':', initialvalue=v, minvalue=0, maxvalue=65535, parent=root)
        if nv is not None and nv != v:
            s['save'].set_setting(key, nv)
            dirty()
            sets.item(key, values=(value_text(key),))
            resort(sets, sets.parent(key))

    def open_save():
        saves = [p for p in glob.glob(os.path.join(glob.escape(prefs['saves']), '**', '*.a8s'), recursive=True)
                 if os.path.basename(p).lower() != 'accountdata.a8s']  # account file, not a save
        newest = max(saves, key=os.path.getmtime, default=None)
        path = filedialog.askopenfilename(title=t('Spielstand öffnen'), filetypes=[(t('Anno 117 Spielstand'), '*.a8s')],
                                          initialdir=os.path.dirname(newest) if newest else prefs['saves'],
                                          initialfile=newest and os.path.basename(newest))
        if not path:
            return
        status.set(t('Lade Spielstand …'))
        root.update()
        save = Save(path)
        view['zoom'] = 1
        s.update(save=save, storages=save.storages(names), maps={}, dots={},
                 regions=[(g, db) for g, _, db in save.sessions if db.path('GameSessionManager', 'MapTemplate')])
        pick['values'] = [x[0] for x in s['storages']]
        pick.current(0)
        region['values'] = [names['assets'].get(str(g), g) for g, _ in s['regions']]
        region.current(0)
        show_storage()
        show_settings()
        save_btn['state'] = 'normal'
        root.title(TITLE)
        status.set(t('Geladen: {}').format(path))
        draw_map()

    def save_as():
        src = s['save'].path
        path = filedialog.asksaveasfilename(
            title=t('Speichern unter'), initialdir=os.path.dirname(src), defaultextension='.a8s',
            initialfile=os.path.splitext(os.path.basename(src))[0] + t(' bearbeitet') + '.a8s',
            filetypes=[(t('Anno 117 Spielstand'), '*.a8s')])
        if not path:
            return
        if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(src)):
            messagebox.showerror(TITLE, t('Bitte unter neuem Namen speichern, das Original bleibt unangetastet.'))
            return
        status.set(t('Speichere …'))
        root.update()
        s['save'].write(path)
        root.title(TITLE)
        status.set(t('Gespeichert: {}').format(path))

    tr(ttk.Button(bar, command=open_save), 'Spielstand öffnen …').pack(side='left')
    save_btn = tr(ttk.Button(bar, command=save_as, state='disabled'), 'Speichern unter …')
    save_btn.pack(side='left', padx=6)
    pick.bind('<<ComboboxSelected>>', show_storage)
    region.bind('<<ComboboxSelected>>', lambda e: (view.update(zoom=1), draw_map()))
    cv.bind('<Configure>', lambda e: (view['timer'] and root.after_cancel(view['timer']), view.update(timer=root.after(300, draw_map))))
    cv.bind('<Motion>', map_hover)
    cv.bind('<Leave>', tip_off)
    cv.bind('<MouseWheel>', zoom_map)
    cv.bind('<Button-1>', map_press)
    cv.bind('<B1-Motion>', map_drag)
    cv.bind('<ButtonRelease-1>', map_release)
    goods.bind('<Double-1>', lambda e: goods.identify_row(e.y) and edit_goods((goods.identify_row(e.y),)))

    # tooltip with the game's description of the good under the mouse
    tip = tk.Label(root, bg='#ffffe1', fg='black', relief='solid', bd=1, wraplength=340, justify='left', padx=6, pady=3)

    def hover(e):
        text = names['descs'].get(goods.identify_row(e.y))
        if not text:
            tip.place_forget()
            return
        tip.config(text=text)
        tip.update_idletasks()
        x = min(e.x_root - root.winfo_rootx() + 16, root.winfo_width() - tip.winfo_reqwidth() - 4)
        tip.place(x=max(x, 0), y=e.y_root - root.winfo_rooty() + 16)
        tip.lift()

    goods.bind('<Motion>', hover)
    goods.bind('<Leave>', lambda e: tip.place_forget())
    sets.bind('<Double-1>', lambda e: (r := sets.identify_row(e.y)) and r in s['save'].refs and edit_setting(r))  # not on group rows

    dark = tk.BooleanVar(value=prefs.get('dark', windows_dark()))

    def save_prefs():
        prefs.update(dark=dark.get(), lang=LANG)
        try:
            os.makedirs(DATA, exist_ok=True)
            with open(PREFS, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def ask_folders():
        """First start (or the game moved): ask for the game folder and the save folder. False = cancelled."""
        msg = ('Bitte wähle den Installationsordner von Anno 117 (der Ordner mit „maindata“), '
               'z. B. …\\steamapps\\common\\Anno 117 - Pax Romana.')
        while not is_game_dir(prefs.get('game', '')):
            messagebox.showinfo(TITLE, t(msg), parent=root)
            path = filedialog.askdirectory(title=t('Anno 117 Installationsordner'), mustexist=True, parent=root)
            if not path:
                return False
            prefs['game'] = os.path.normpath(path)
            msg = 'In diesem Ordner fehlt „maindata\\config.rda“. Bitte den Installationsordner von Anno 117 wählen.'
        if not os.path.isdir(prefs.get('saves', '')):
            guess = os.path.join(documents(), 'Anno 117 - Pax Romana')
            messagebox.showinfo(TITLE, t('Bitte wähle den Ordner mit deinen Spielständen, meist Dokumente\\Anno 117 - Pax Romana.'),
                                parent=root)
            path = filedialog.askdirectory(title=t('Ordner mit den Spielständen'), mustexist=True, parent=root,
                                           initialdir=guess if os.path.isdir(guess) else documents())
            prefs['saves'] = os.path.normpath(path or guess)
        save_prefs()
        return True

    # language: UI texts from EN, names of goods/islands/settings from the game's texts_<language>.xml
    lang_box = ttk.Combobox(bar, state='readonly', width=9, values=[v[0] for v in LANGS.values()])
    lang_box.current(list(LANGS).index(LANG))
    lang_box.pack(side='right', padx=(10, 0))

    def set_lang(*_):
        global LANG
        nonlocal names
        LANG = list(LANGS)[lang_box.current()]
        save_prefs()
        for w, text in texts:
            w.configure(text=t(text))
        nb.tab(tab1, text=t('Denare & Lager'))
        nb.tab(tab2, text=t('Spieleinstellungen'))
        nb.tab(tab3, text=t('Fruchtbarkeiten'))
        for tv in (goods, sets):
            heads(tv)
        status.set(t('Lade Namen aus den Spieldateien …'))
        root.update()
        names = game_names(prefs['game'], LANG)
        if not s['save']:
            status.set(t('Spielstand öffnen, um zu beginnen.'))
            return
        i = pick.current()
        s['storages'] = s['save'].storages(names)
        pick['values'] = [x[0] for x in s['storages']]
        pick.current(i)
        region['values'] = [names['assets'].get(str(g), g) for g, _ in s['regions']]
        show_storage()
        show_settings()
        status.set(t('Geladen: {}').format(s['save'].path))
        draw_map()

    lang_box.bind('<<ComboboxSelected>>', set_lang)

    # dark mode: ttk 'clam' recoloured; plain tk widgets (dialogs, lists) via the option database
    style = ttk.Style()
    light_theme = style.theme_use()

    def apply_theme():
        d = dark.get()
        bg, fg, field, sel, head = '#202020', '#e8e8e8', '#2b2b2b', '#3d5a80', '#333333'
        root.option_clear()
        if d:
            style.theme_use('clam')
            style.configure('.', background=bg, foreground=fg, fieldbackground=field, bordercolor='#444444',
                            lightcolor=bg, darkcolor=bg, troughcolor=bg, arrowcolor=fg, insertcolor=fg,
                            selectbackground=sel, selectforeground='white')
            style.map('.', foreground=[('disabled', '#777777')])
            style.configure('Treeview', background=field, fieldbackground=field)
            style.map('Treeview', background=[('selected', sel)], foreground=[('selected', 'white')])
            style.configure('Treeview.Heading', background=head)
            style.map('Treeview.Heading', background=[('active', '#3c3c3c')])
            style.configure('TNotebook.Tab', background=head, padding=(10, 3))
            style.map('TNotebook.Tab', background=[('selected', bg)])
            style.configure('TButton', background=head)
            style.map('TButton', background=[('active', '#3c3c3c'), ('disabled', bg)])
            style.configure('TCheckbutton', indicatorforeground=fg)
            style.map('TCheckbutton', background=[('active', bg)], indicatorbackground=[('!active', field)])
            style.configure('Vertical.TScrollbar', background=head, lightcolor=head, darkcolor=head,
                            troughcolor=bg, bordercolor='#444444', arrowcolor=fg)
            style.map('Vertical.TScrollbar', background=[('active', '#4a4a4a')])
            style.map('TCombobox', fieldbackground=[('readonly', field)], foreground=[('readonly', fg)],
                      selectbackground=[('readonly', field)], selectforeground=[('readonly', fg)])
            for k, v in (('*Background', bg), ('*Foreground', fg), ('*Entry.Background', field),
                         ('*Listbox.Background', field), ('*selectBackground', sel), ('*selectForeground', 'white'), ('*insertBackground', fg)):
                root.option_add(k, v)
        else:
            style.theme_use(light_theme)
        root.configure(bg=bg if d else 'SystemButtonFace')
        tip.configure(bg='#3a3a3a' if d else '#ffffe1', fg=fg if d else 'black')
        for box in (pick, region, lang_box):  # combobox drop-down lists are plain tk listboxes
            try:
                pop = root.tk.eval(f'ttk::combobox::PopdownWindow {box}')
                root.tk.call(f'{pop}.f.l', 'configure', '-background', field if d else 'SystemWindow',
                             '-foreground', fg if d else 'SystemWindowText', '-selectbackground', sel if d else 'SystemHighlight')
            except tk.TclError:
                pass
        try:  # dark Windows title bar (DWMWA_USE_IMMERSIVE_DARK_MODE), then force a frame redraw
            import ctypes
            root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(d)), 4)
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x27)
        except (AttributeError, OSError):
            pass

    def toggle_theme():
        apply_theme()
        save_prefs()

    tr(ttk.Checkbutton(bar, variable=dark, command=toggle_theme), 'Dunkler Modus').pack(side='right')
    apply_theme()

    def background(work, done):
        """work() in a thread (network), then done(result, error) back in the Tk thread."""
        res = []

        def run():
            try:
                res.append((work(), None))
            except Exception as e:  # offline, GitHub down, …
                res.append((None, e))

        def poll():
            if res:
                done(*res[0])
            else:
                root.after(300, poll)

        threading.Thread(target=run, daemon=True).start()
        poll()

    def offer_update(rel, err):
        if err or not rel or rel['tag_name'] == prefs.get('skip'):
            return  # offline, nothing new or declined before: stay quiet
        asset = next((a for a in rel['assets'] if a['name'] == EXE), None)
        frozen = getattr(sys, 'frozen', False) and asset  # the .exe can replace itself; the .pyw only points to the page
        msg = t('Version {} ist verfügbar (du hast {}).').format(rel['tag_name'].lstrip('v'), VERSION) + '\n\n'
        msg += t('Jetzt herunterladen und neu starten?') if frozen else t('Download-Seite öffnen?')
        if frozen and root.title().endswith('*'):
            msg += '\n' + t('Ungespeicherte Änderungen gehen dabei verloren.')
        if not messagebox.askyesno(TITLE, msg, parent=root):
            prefs['skip'] = rel['tag_name']  # don't ask again for this version
            save_prefs()
        elif not frozen:
            webbrowser.open(rel['html_url'])
        else:
            before = status.get()
            status.set(t('Lade Update …'))
            background(lambda: install_update(asset, sys.executable), lambda _, e: restart(e, before))

    def restart(err, before):
        if err:
            status.set(before)
            messagebox.showerror(TITLE, t('Update fehlgeschlagen: {}').format(err), parent=root)
            return
        # PYINSTALLER_RESET_ENVIRONMENT: start the new exe as its own program, not as a child of this one
        subprocess.Popen([sys.executable], env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT='1'))
        root.destroy()

    if getattr(sys, 'frozen', False):
        try:
            os.remove(sys.executable + '.old')  # left over from the last update
        except OSError:
            pass
    root.update()
    if not ask_folders():
        root.destroy()
        return
    names = game_names(prefs['game'], LANG)
    status.set(t('Spielstand öffnen, um zu beginnen.'))
    background(newer_release, offer_update)
    root.mainloop()


# ---------- self-check ----------

def selftest(path):
    game = load_prefs().get('game', '')
    assert is_game_dir(game), 'Spielordner unbekannt: den Editor erst einmal normal starten'
    small = {2063: 3, 2069: 200, 2300: 0}
    assert decode_storage(*encode_storage(small, True)) == small and encode_storage(small, True)[0] == 'StrgSmll'
    assert encode_storage({2063: 300}, True)[0] == 'StrgLrg'
    head, files = read_rda(path)
    tmp =os.path.join(tempfile.gettempdir(), 'anno117_editor_selftest.a8s')
    write_rda(tmp, head, files)
    assert open(tmp, 'rb').read() == open(path, 'rb').read(), 'RDA nicht identisch'
    s = Save(path)
    for _, blob, db in s.sessions:
        assert db.tobytes() == blob[1], 'Session nicht identisch'
    for name, content in files:
        packed = FileDB(content).tobytes()
        assert zlib.decompress(packed) == zlib.decompress(content), name
        assert packed[-12:] == content[-12:], name + ': Anhang nach dem zlib-Strom weicht ab'
    names = game_names(game)
    stores = s.storages(names)
    for lab, db, tag in stores:
        a = s.storage_attr(db, tag)
        assert encode_storage(decode_storage(db.name(a), a[1]), db.name(a) == 'StrgSmll') == (db.name(a), a[1]), lab
        print(lab, len(s.storage(db, tag)), 'Waren')
    money = s.storage(stores[0][1], stores[0][2]).get(1010017)
    print('Denare:', money)
    # full rewrite with every part re-serialised must read back identically
    s.changed = {s.data, s.setup, s.header, *(db for _, _, db in s.sessions)}
    s.write(tmp)
    t = Save(tmp)
    unpack = lambda fs: [zlib.decompress(c) if c[:2] == b'\x78\xda' else c for n, c in fs if n not in ('meta.a7s', 'header.a7s')]
    assert unpack(t.files) == unpack(files), 'Neuschreiben nicht identisch'
    meta = FileDB(dict(t.files)['meta.a7s'])
    assert meta.attr(meta.root, 'CorporationSaveGameName')[1].decode('utf-16-le') == 'anno117_editor_selftest'
    assert t.storage(*t.storages(names)[0][1:]).get(1010017) == money
    # fertilities: each area's set must equal its map template array (checks the AreaID → element formula);
    # then drop the first of one area and add one it lacks: AreaInfo and template must read back changed
    u32s = lambda arr: sorted(struct.unpack(f'<{len(arr[1]) // 4}I', arr[1]))
    flat = lambda db: {aid: a for lst in Save.areas(db).values() for aid, a in lst}
    for _, _, db in s.sessions:
        for aid, a in flat(db).items():
            arr = Save.template_fertilities(db, aid)
            assert arr is None or u32s(arr) == sorted(Save.fertilities(db, a)), f'Kartenvorlage passt nicht zu Bereich {aid}'
    n, aid, area = next((n, aid, a) for n, (_, _, db) in enumerate(s.sessions) for aid, a in flat(db).items()
                        if Save.template_fertilities(db, aid) is not None)
    db = s.sessions[n][2]
    have = s.fertilities(db, area)
    new = have[1:] + [next(g for g, _ in names['ferts'] if g not in have)]
    s.set_fertilities(db, aid, area, new)
    s.write(tmp)
    db = Save(tmp).sessions[n][2]
    assert Save.fertilities(db, flat(db)[aid]) == new, 'Fruchtbarkeiten nicht übernommen'
    assert u32s(Save.template_fertilities(db, aid)) == sorted(new), 'Kartenvorlage nicht angepasst'
    print('Fruchtbarkeiten:', len(have), '->', len(new), '(samt Kartenvorlage)')
    # map: every island of the first region becomes a PNG; an icon decodes with transparent and opaque pixels
    lay = map_layout(game, s.map_islands(s.sessions[0][2]))
    k = map_fit(lay, 300, 200)[0]
    res = [(render_isle(game, *a[:4], k),) for a in lay.values()]
    assert res and all(p.startswith(b'\x89PNG') for *_, p in res), 'Karte'
    dots = map_dots(s.sessions[0][2], lay)  # buildings: the player has some, and they change the island's picture
    assert any(c == 0xff5ed7ff for d in dots.values() for *_, c in d), 'keine Gebäude des Spielers gefunden'
    assert all(render_isle(game, *lay[i][:4], k, d) != render_isle(game, *lay[i][:4], k) for i, d in dots.items() if d), 'Gebäude'
    rgba, w, h = dds(game_file(game, names['icons'][str(names['ferts'][0][0])]), 3)
    assert (w, h) == (64, 64) and rgba[3::4].count(0) and rgba[3::4].count(255), 'Symbol'
    print('Karte:', len(res), 'Inseln,', sum(map(len, dots.values())), 'Gebäude, Symbole lesbar')
    os.remove(tmp)
    print(len(s.refs), 'Einstellungen,', sum(label(names, k) is not None for k in s.refs), 'mit Menütext')
    assert version('v1.10.0') > version('1.9.2') > version('v1.9'), 'Versionsvergleich'
    groups = grouped(names, s.refs)
    assert sorted(k for *_, k in groups) == sorted(s.refs), 'Gruppierung verliert Einstellungen'
    print(len({g[:2] for g in groups}), 'Gruppen:', ', '.join(dict.fromkeys(g[0] for g in groups)))
    print('Selbsttest OK')


if __name__ == '__main__':
    if sys.argv[1:2] == ['--selftest']:
        selftest(sys.argv[2])
    else:
        run_ui()
