"""Anno 117 Savegame-Editor: Denare und Reichsgueter, Insellager, Spieleinstellungen (inkl. DLC-Optionen).

Speichert immer als neue Datei, das Original bleibt unangetastet. Formatnotizen: STAND.md

  savegame_editor.pyw                       Fenster (Doppelklick)
  python savegame_editor.pyw --selftest X   prueft, dass Spielstand X unveraendert identisch neu geschrieben wird
"""
import glob, html, json, os, re, struct, sys, tempfile, time, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = r'F:\Launcher\Steam\steamapps\common\Anno 117 - Pax Romana'
SAVES = os.path.join(os.environ['USERPROFILE'], 'OneDrive', 'Dokumente', 'Anno 117 - Pax Romana', 'accounts')
CACHE = os.path.join(HERE, 'namen_de.json')
PREFS = os.path.join(HERE, 'einstellungen.json')  # remembers the dark-mode choice
TITLE = 'Anno 117 Savegame-Editor'
PLAYER = 41  # OwnerProfile / ParticipantGUID of the human player
MAGIC = b'\x08\x00\x00\x00\xfd\xff\xff\xff'
# setup tags whose UI category is spelled differently in assets.xml
ALIAS = {'SetupTraderTraderPrices': 'TraderTradePrices',
         'SetupVolcanoSchedulerIntervalDuration': 'VolcanoSchedulerIntervalLength',
         'SetupContinetnalIslandSettlementCosts': 'ContinentalIslandSettlementCosts'}
# pirate comboboxes -> field tag in the save (Dormancy left out on purpose: 2 = defeated has no menu entry)
PIRATE = {'PirateRaidDifficulty': 'RaidDifficulty', 'PirateWarFleetDifficulty': 'WarFleetDifficulty',
          'PiratePatrolsDifficulty': 'PatrolDifficulty', 'PirateWarThreatsDifficulty': 'WarThreats'}


# ---------- RDA container (.a8s): per inner file [data][560 B directory entry][32 B block header] ----------

def read_rda(path):
    data = open(path, 'rb').read()
    if data[:18] != b'Resource File V2.2':
        raise ValueError('Kein Anno-Spielstand')
    off, files = struct.unpack_from('<Q', data, 784)[0], []
    while off < len(data):
        flags, n, dsize, _, nxt = struct.unpack_from('<IIQQQ', data, off)
        if flags:
            raise ValueError(f'Unerwartetes Spielstandformat (Block-Flags {flags})')
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
            raise ValueError('Unbekanntes FileDB-Format')
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

    def storages(self, names):
        """[(label, db, tag holding the storage)]: the empire storage (Denare) and every player island's warehouse."""
        out = [('Reich: Denare, Baurechte, Reserven', self.data, t) for t in self.empire()]
        for guid, _, db in self.sessions:
            for area in db.path('GameSessionManager', 'AreaInfo', 'None'):
                owner, city, econ = db.attr(area, 'OwnerProfile'), db.attr(area, 'CityNameGuid'), db.tags(area, 'AreaEconomy')
                if owner and econ and struct.unpack('<i', owner[1][:4])[0] == PLAYER and self.storage_attr(db, econ[0]):
                    name = city and names['texts'].get(str(struct.unpack('<q', city[1][:8])[0]))
                    out.append((f'{name or "Insel"} ({names["assets"].get(str(guid), guid)})', db, econ[0]))
        return out

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
            raise ValueError('Mengen über 255 sind in diesem Lager nicht möglich (Spielstand kennt kein StrgLrg).')
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


# ---------- German names and setting labels from the game files (cached next to this script) ----------

def game_names():
    src = os.path.join(GAME, 'maindata', 'config.rda')
    stamp = os.path.getmtime(src)
    try:
        with open(CACHE, encoding='utf-8') as f:
            cache = json.load(f)
        if cache['stamp'] == stamp and 'descs' in cache:
            return cache
    except (OSError, ValueError, KeyError):
        pass
    wanted = {'data/base/config/export/assets.xml': 'assets', 'data/base/config/gui/texts_german.xml': 'texts'}
    raw = {}
    with open(src, 'rb') as f:
        off, size = struct.unpack_from('<Q', f.read(792), 784)[0], f.seek(0, 2)
        while off < size and len(raw) < len(wanted):
            f.seek(off)
            flags, n, dsize, _, nxt = struct.unpack('<IIQQQ', f.read(32))
            if not flags & 7:  # plain block; the two files sit in one of those
                f.seek(off - dsize)
                d = f.read(dsize)
                for i in range(n):
                    e = d[i * 560:(i + 1) * 560]
                    name = e[:520].decode('utf-16-le').split('\0')[0]
                    if name in wanted:
                        foff, csz = struct.unpack_from('<QQ', e, 520)
                        f.seek(foff)
                        raw[wanted[name]] = f.read(csz).decode('utf-8-sig', 'replace')
            if nxt <= off:
                break
            off = nxt
    clean = lambda t: re.sub(r'<[^>]*>', '', html.unescape(t)).strip()
    texts = {k: clean(v) for k, v in re.findall(r'<LineId>(-?\d+)</LineId>\s*<Text>(.*?)</Text>', raw['texts'], re.S)}
    assets, descs = {}, {}
    for chunk in raw['assets'].split('<Asset>'):
        g, o = re.search(r'<GUID>(\d+)</GUID>', chunk), re.search(r'<OasisId>(-?\d+)</OasisId>', chunk)
        if g and o and o.group(1) in texts:
            assets[g.group(1)] = texts[o.group(1)]
        d = '<Template>Product</Template>' in chunk and re.search(r'<InfoDescription>(-?\d+)<', chunk)
        if g and d and texts.get(d.group(1)):
            descs[g.group(1)] = texts[d.group(1)]  # tooltip text for goods
    settings = {}
    for kind, body in re.findall(r'<(OptionCombobox|OptionToggle)>(.*?)</\1>', raw['assets'], re.S):
        m = re.search(r'Textsource>GameSetup\.RelevantGameSetup[.:](\w+)(?:\((?:datasets\.DifficultyCategory\.)?(\w+)\))?<', body)
        if not m:
            continue
        fn, arg = m.groups()
        key = arg if fn == 'DifficultyCategoryValue' else f'Pirate:{arg}:{PIRATE[fn]}' if fn in PIRATE else None if arg else fn
        head = re.search(r'Headline>(-?\d+)<', body)
        if kind == 'OptionToggle':
            options = [re.search(rf'<{t}>(-?\d+)<', body) for t in ('ActivatedText', 'DeactivatedText')]  # 0 = Activated (checked in-game)
            options = [o.group(1) for o in options if o]
        else:
            options = re.findall(r'<Text>(-?\d+)</Text>', body)
        if key and head and options:
            settings[key] = [texts.get(head.group(1), key), [texts.get(o, o) for o in options]]
    cache = {'stamp': stamp, 'texts': texts, 'assets': assets, 'descs': descs, 'settings': settings}
    with open(CACHE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)
    return cache


def label(names, key):
    """[headline, options] for a setting key, or None if the game has no menu text for it."""
    return names['settings'].get(ALIAS.get(key, key.removeprefix('Setup')))


# ---------- window ----------

def windows_dark():
    """True if Windows apps are set to dark mode (default before the user picks one)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as k:
            return winreg.QueryValueEx(k, 'AppsUseLightTheme')[0] == 0
    except OSError:
        return False


def run_ui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog

    root = tk.Tk()
    root.title(TITLE)
    root.geometry('860x660')
    root.report_callback_exception = lambda typ, err, tb: messagebox.showerror(TITLE, f'{typ.__name__}: {err}')
    status = tk.StringVar(value='Lade Namen aus den Spieldateien …')
    s = {'save': None, 'storages': []}

    def table(parent, cols, widths):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, pady=6)
        t = ttk.Treeview(frame, columns=cols, show='headings')
        for c, w in zip(cols, widths):
            t.heading(c, text=c)
            t.column(c, width=w, anchor='w' if c == cols[0] else 'e')
        sb = ttk.Scrollbar(frame, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        return t

    bar = ttk.Frame(root, padding=6)
    bar.pack(fill='x')
    nb = ttk.Notebook(root)
    nb.pack(fill='both', expand=True, padx=6)
    ttk.Label(root, textvariable=status, padding=6).pack(fill='x')

    tab1 = ttk.Frame(nb, padding=6)
    nb.add(tab1, text='Denare & Lager')
    pick = ttk.Combobox(tab1, state='readonly', width=60)
    pick.pack(anchor='w')
    goods = table(tab1, ('Ware', 'Menge', 'GUID'), (440, 160, 100))
    row = ttk.Frame(tab1)
    row.pack(fill='x')
    ttk.Label(row, text='Doppelklick ändert eine Menge. Mehrere Zeilen mit Strg/Umschalt markieren und').pack(side='left')
    ttk.Button(row, text='Auswahl setzen …', command=lambda: edit_goods(goods.selection())).pack(side='left', padx=6)

    tab2 = ttk.Frame(nb, padding=6)
    nb.add(tab2, text='Spieleinstellungen')
    ttk.Label(tab2, wraplength=800, text='Doppelklick zum Ändern. Startoptionen (Startkapital, Inselgröße, Startschiffe …) '
              'wirken nach Spielbeginn nicht mehr. „Rohwert“ = das Spiel hat dafür keinen Menütext.'
              ).pack(anchor='w')
    sets = table(tab2, ('Einstellung', 'Wert'), (440, 320))

    def dirty():
        root.title(TITLE + ' *')

    def show_storage(*_):
        _, db, tag = s['storages'][pick.current()]
        goods.delete(*goods.get_children())
        for guid, amount in s['save'].storage(db, tag).items():
            goods.insert('', 'end', iid=str(guid), values=(
                names['assets'].get(str(guid), f'GUID {guid}'), f'{amount:,}'.replace(',', '.'), guid))

    def edit_goods(rows):
        if not rows:
            return
        _, db, tag = s['storages'][pick.current()]
        items = s['save'].storage(db, tag)
        what = goods.set(rows[0], 'Ware') if len(rows) == 1 else f'{len(rows)} markierte Waren'
        v = simpledialog.askinteger(TITLE, f'Neue Menge für {what}:', initialvalue=items[int(rows[0])],
                                    minvalue=0, maxvalue=2 ** 31 - 1, parent=root)
        if v is None:
            return
        for r in rows:
            items[int(r)] = v
        s['save'].set_storage(db, tag, items)
        dirty()
        show_storage()
        goods.selection_set(rows)

    def show_settings():
        sets.delete(*sets.get_children())
        for key in sorted(s['save'].refs, key=lambda k: label(names, k) is None):  # menu settings first
            v, lab = s['save'].setting(key), label(names, key)
            if lab:
                text = lab[1][v] if v < len(lab[1]) else f'Wert {v} (unbekannt)'
                sets.insert('', 'end', iid=key, values=(lab[0], text))
            else:
                sets.insert('', 'end', iid=key, values=(f'{key} (Rohwert)', v))

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
        ttk.Button(win, text='Übernehmen', command=ok).pack(pady=(0, 10))
        win.wait_window()
        return res[0] if res else None

    def edit_setting(key):
        v, lab = s['save'].setting(key), label(names, key)
        if lab:
            nv = choose(lab[0], lab[1], v)
        else:
            nv = simpledialog.askinteger(TITLE, f'{key} (Rohwert):', initialvalue=v, minvalue=0, maxvalue=65535, parent=root)
        if nv is not None and nv != v:
            s['save'].set_setting(key, nv)
            dirty()
            show_settings()

    def open_save():
        newest = max(glob.glob(os.path.join(SAVES, '*', '*', '*.a8s')), key=os.path.getmtime, default=None)
        path = filedialog.askopenfilename(title='Spielstand öffnen', filetypes=[('Anno 117 Spielstand', '*.a8s')],
                                          initialdir=newest and os.path.dirname(newest),
                                          initialfile=newest and os.path.basename(newest))
        if not path:
            return
        status.set('Lade Spielstand …')
        root.update()
        save = Save(path)
        s.update(save=save, storages=save.storages(names))
        pick['values'] = [x[0] for x in s['storages']]
        pick.current(0)
        show_storage()
        show_settings()
        save_btn['state'] = 'normal'
        root.title(TITLE)
        status.set(f'Geladen: {path}')

    def save_as():
        src = s['save'].path
        path = filedialog.asksaveasfilename(
            title='Speichern unter', initialdir=os.path.dirname(src), defaultextension='.a8s',
            initialfile=os.path.splitext(os.path.basename(src))[0] + ' bearbeitet.a8s',
            filetypes=[('Anno 117 Spielstand', '*.a8s')])
        if not path:
            return
        if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(src)):
            messagebox.showerror(TITLE, 'Bitte unter neuem Namen speichern, das Original bleibt unangetastet.')
            return
        status.set('Speichere …')
        root.update()
        s['save'].write(path)
        root.title(TITLE)
        status.set(f'Gespeichert: {path}')

    ttk.Button(bar, text='Spielstand öffnen …', command=open_save).pack(side='left')
    save_btn = ttk.Button(bar, text='Speichern unter …', command=save_as, state='disabled')
    save_btn.pack(side='left', padx=6)
    pick.bind('<<ComboboxSelected>>', show_storage)
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
    sets.bind('<Double-1>', lambda e: sets.identify_row(e.y) and edit_setting(sets.identify_row(e.y)))

    # dark mode: ttk 'clam' recoloured; plain tk widgets (dialogs, lists) via the option database
    style = ttk.Style()
    light_theme = style.theme_use()
    try:
        with open(PREFS, encoding='utf-8') as f:
            dark = tk.BooleanVar(value=json.load(f)['dark'])
    except (OSError, ValueError, KeyError):
        dark = tk.BooleanVar(value=windows_dark())

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
        try:  # the combobox drop-down list is a plain tk listbox
            pop = root.tk.eval(f'ttk::combobox::PopdownWindow {pick}')
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
        try:
            with open(PREFS, 'w', encoding='utf-8') as f:
                json.dump({'dark': dark.get()}, f)
        except OSError:
            pass

    ttk.Checkbutton(bar, text='Dunkler Modus', variable=dark, command=toggle_theme).pack(side='right')
    apply_theme()

    root.update()
    names = game_names()
    status.set('Spielstand öffnen, um zu beginnen.')
    root.mainloop()


# ---------- self-check ----------

def selftest(path):
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
    names = game_names()
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
    os.remove(tmp)
    print(len(s.refs), 'Einstellungen,', sum(label(names, k) is not None for k in s.refs), 'mit Menütext')
    print('Selbsttest OK')


if __name__ == '__main__':
    if sys.argv[1:2] == ['--selftest']:
        selftest(sys.argv[2])
    else:
        run_ui()
