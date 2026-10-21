"""PCの片隅で使う音楽理論トレーニングツール。

モード: 音程 / コード構成音 / ディグリー / 調号 / 移調楽器 / 五度圏（設定で切り替え）
答えの入力: 音名 A-G に続けて ♯ / ♭ を付ける
  ♯: #  +  音名キーの右隣のキー（例: e→r）  →  ↑
  ♭: b  -  音名キーの左隣のキー（例: e→w）  ←  ↓
  ダブル♯: x（または ♯ を2回）
Space: 次へ（コード構成音では音の区切り） / Enter: 判定（未入力なら答え表示、表示後なら次へ）
Backspace: 1文字消す / Tab: 自動の開始・停止 / Esc: 設定の開閉 / 右クリック: メニュー / ドラッグで移動
"""
import json
import os
import random
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

try:
    import winsound
except ImportError:  # Windows 以外では音なし
    winsound = None

if getattr(sys, "frozen", False):
    # EXE 版は展開先が毎回変わるので、設定は %APPDATA% に置く
    _dir = Path(os.environ.get("APPDATA", Path.home())) / "BlindIntervalPractice"
    _dir.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE = _dir / "interval_trainer.json"
else:
    SETTINGS_FILE = Path(__file__).with_name("interval_trainer.json")

LETTERS = ["C", "D", "E", "F", "G", "A", "B"]
NATURAL_PC = [0, 2, 4, 5, 7, 9, 11]
# ダブル♯・ダブル♭は Tk で描けない文字（𝄪 𝄫）なので ♯♯ ♭♭ と書く
ACC = {-2: "♭♭", -1: "♭", 0: "", 1: "♯", 2: "♯♯"}
MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]

# ルート候補（表記, 文字index, ピッチクラス）
ROOTS = [
    ("C", 0, 0), ("C♯", 0, 1), ("D♭", 1, 1), ("D", 1, 2), ("D♯", 1, 3), ("E♭", 2, 3),
    ("E", 2, 4), ("F", 3, 5), ("F♯", 3, 6), ("G♭", 4, 6), ("G", 4, 7), ("G♯", 4, 8),
    ("A♭", 5, 8), ("A", 5, 9), ("A♯", 5, 10), ("B♭", 6, 10), ("B", 6, 11),
]

# (表示名, 略号, 半音数, 度数-1)
INTERVALS = [
    ("短2度", "m2", 1, 1), ("長2度", "M2", 2, 1),
    ("短3度", "m3", 3, 2), ("長3度", "M3", 4, 2),
    ("完全4度", "P4", 5, 3), ("増4度", "A4", 6, 3),
    ("減5度", "d5", 6, 4), ("完全5度", "P5", 7, 4),
    ("短6度", "m6", 8, 5), ("長6度", "M6", 9, 5),
    ("短7度", "m7", 10, 6), ("長7度", "M7", 11, 6),
    ("完全8度", "P8", 12, 7),
]

# (コード記号, 半音数のリスト, 度数-1 のリスト)
CHORDS = [
    ("", [0, 4, 7], [0, 2, 4]), ("m", [0, 3, 7], [0, 2, 4]),
    ("dim", [0, 3, 6], [0, 2, 4]), ("aug", [0, 4, 8], [0, 2, 4]),
    ("sus4", [0, 5, 7], [0, 3, 4]), ("6", [0, 4, 7, 9], [0, 2, 4, 5]),
    ("7", [0, 4, 7, 10], [0, 2, 4, 6]), ("M7", [0, 4, 7, 11], [0, 2, 4, 6]),
    ("m7", [0, 3, 7, 10], [0, 2, 4, 6]), ("mM7", [0, 3, 7, 11], [0, 2, 4, 6]),
    ("m7♭5", [0, 3, 6, 10], [0, 2, 4, 6]), ("dim7", [0, 3, 6, 9], [0, 2, 4, 6]),
]
CHORD_BY_SYM = {c[0]: c for c in CHORDS}

# ディグリー（長調）: (ローマ数字, コードの種類)
DEGREE_TRIADS = [("Ⅰ", ""), ("Ⅱm", "m"), ("Ⅲm", "m"), ("Ⅳ", ""), ("Ⅴ", ""), ("Ⅵm", "m"), ("Ⅶdim", "dim")]
DEGREE_SEVENTHS = [("ⅠM7", "M7"), ("Ⅱm7", "m7"), ("Ⅲm7", "m7"), ("ⅣM7", "M7"),
                   ("Ⅴ7", "7"), ("Ⅵm7", "m7"), ("Ⅶm7♭5", "m7♭5")]

# 長調と調号: (調名, 文字index, ピッチクラス, 記号の数, "#" or "b")
KEYSIGS = [
    ("C", 0, 0, 0, ""), ("G", 4, 7, 1, "#"), ("D", 1, 2, 2, "#"), ("A", 5, 9, 3, "#"),
    ("E", 2, 4, 4, "#"), ("B", 6, 11, 5, "#"), ("F♯", 3, 6, 6, "#"), ("C♯", 0, 1, 7, "#"),
    ("F", 3, 5, 1, "b"), ("B♭", 6, 10, 2, "b"), ("E♭", 2, 3, 3, "b"), ("A♭", 5, 8, 4, "b"),
    ("D♭", 1, 1, 5, "b"), ("G♭", 4, 6, 6, "b"), ("C♭", 0, 11, 7, "b"),
]

# 移調楽器: (表示名, 記譜→実音で下がる半音数, 度数-1)
INSTRUMENTS = [("B♭", 2, 1), ("E♭", 9, 5), ("F", 7, 4), ("A", 3, 2)]

MODES = [("interval", "音程"), ("chord", "コード構成音"), ("degree", "ディグリー"),
         ("keysig", "調号"), ("transpose", "移調楽器"), ("circle", "五度圏")]

# 音名キーの左隣・右隣のキー（QWERTY / JIS 共通）。左＝♭、右＝♯
NEIGHBORS = {"a": ("", "s"), "b": ("v", "n"), "c": ("x", "v"), "d": ("s", "f"),
             "e": ("w", "r"), "f": ("d", "g"), "g": ("f", "h")}
ARROWS = {"Right": "#", "Up": "#", "Left": "b", "Down": "b"}

DEFAULTS = {
    "mode": "interval",
    "intervals": ["m3", "M3", "P4", "P5"],
    "direction": "up",  # up / down / random
    "chords": ["", "m", "7", "M7", "m7"],
    "degree_type": "triad",  # triad / seventh / both
    "keysig_dir": "both",  # sig2key / key2sig / both
    "instruments": ["B♭", "E♭", "F"],
    "transpose_dir": "w2c",  # w2c / c2w / both
    "circle_dir": "both",  # up5 / up4 / both
    "weak_focus": True,
    "stats": {},
    "auto_sec": 6.0,
    "reveal_sec": 3.0,
    "sound": True,
    "topmost": True,
    "avoid_double": True,
    "enharmonic_ok": False,
    "idle_alpha": 0.7,
    "clear_bg": True,
    "root_sharp": True,
    "root_flat": True,
    "geometry": "",
}


# ---------- 音名の計算 ----------
def spell(root_letter, root_pc, semis, steps, up=True):
    sign = 1 if up else -1
    letter = (root_letter + sign * steps) % 7
    pc = (root_pc + sign * semis) % 12
    diff = (pc - NATURAL_PC[letter] + 6) % 12 - 6  # -6..5
    return LETTERS[letter] + ACC.get(diff, "?"), abs(diff) >= 2


def parse_lead(text):
    """先頭の音名を読む。'ebm7' → ('E♭', 3, 'm7')。読めなければ None。"""
    text = text.strip().lower()
    if not text or text[0] not in "cdefgab":
        return None
    letter = "cdefgab".index(text[0])
    offset, i = 0, 1
    while i < len(text) and text[i] in "#+b-x":
        offset += {"#": 1, "+": 1, "b": -1, "-": -1, "x": 2}[text[i]]
        i += 1
    if abs(offset) > 2:
        return None
    return LETTERS[letter] + ACC[offset], (NATURAL_PC[letter] + offset) % 12, text[i:]


def parse_note(text):
    """'eb' → ('E♭', ピッチクラス)。音名以外が混じれば None。"""
    p = parse_lead(text)
    return (p[0], p[1]) if p and not p[2] else None


def name_pc(name):
    """表示用の音名 'E♭' / 'C♯♯' → ピッチクラス。"""
    offset = name.count("♯") - name.count("♭")
    return (NATURAL_PC["CDEFGAB".index(name[0])] + offset) % 12


def parse_keysig(text):
    """'4#' / 'b3' / '0' → (数, '#' or 'b' or '')。読めなければ None。"""
    digits = "".join(ch for ch in text if ch.isdigit())
    signs = {("#" if ch in "#+" else "b") for ch in text if ch in "#+b-"}
    if not digits or len(signs) > 1:
        return None
    n = int(digits)
    if n > 7 or (n and not signs):
        return None
    return n, (signs.pop() if n else "")


def sig_text(n, sign):
    return "調号なし" if n == 0 else f"{'♯' if sign == '#' else '♭'}×{n}"


def has_double(names):
    return any("♯♯" in n or "♭♭" in n for n in names)


def midi_freq(m):
    return int(440 * 2 ** ((m - 69) / 12))


# ---------- 出題 ----------
# 問題は dict:
#   main / line1 / line2: 表示する文字（大きく / 右上 / 右下）
#   kind: 答えの形 note / notes / keyname / keysig
#   answer: 正解の表示, expect: 判定用の値, tags: 苦手集計用, sound: 鳴らす MIDI 番号
def pick_roots(cfg):
    return [r for r in ROOTS
            if len(r[0]) == 1 or (cfg["root_sharp"] and "♯" in r[0]) or (cfg["root_flat"] and "♭" in r[0])]


def pick_dir(setting, a, b):
    return setting == a or (setting == "both" and random.random() < 0.5)


def gen_interval(cfg):
    pool = [iv for iv in INTERVALS if iv[1] in cfg["intervals"]] or INTERVALS
    root, iv = random.choice(pick_roots(cfg)), random.choice(pool)
    d = cfg["direction"]
    up = d == "up" or (d == "random" and random.random() < 0.5)
    answer, _ = spell(root[1], root[2], iv[2], iv[3], up)
    base = 60 + root[2] if up else 72 + root[2]
    if base > 76:
        base -= 12
    return dict(main=root[0], line1=iv[0], line2=f"{'↑' if up else '↓'}  {iv[1]}",
                kind="note", answer=answer, expect=[answer],
                tags=[f"音程:{iv[0]}{'↑' if up else '↓'}", f"ルート:{root[0]}"],
                sound=[base, base + (iv[2] if up else -iv[2])])


def gen_chord(cfg):
    pool = [c for c in CHORDS if c[0] in cfg["chords"]] or CHORDS
    root, (sym, semis, steps) = random.choice(pick_roots(cfg)), random.choice(pool)
    names = [spell(root[1], root[2], s, st)[0] for s, st in zip(semis, steps)]
    base = 60 + root[2]
    return dict(main=root[0] + sym, line1="構成音", line2="スペース区切り",
                kind="notes", answer=" ".join(names), expect=names,
                tags=[f"コード:{sym or 'M'}", f"ルート:{root[0]}"],
                sound=[base + s for s in semis])


def gen_degree(cfg):
    t = cfg["degree_type"]
    table = DEGREE_TRIADS if t == "triad" else DEGREE_SEVENTHS if t == "seventh" \
        else random.choice([DEGREE_TRIADS, DEGREE_SEVENTHS])
    key = random.choice(pick_roots(cfg))
    d = random.randrange(7)
    numeral, quality = table[d]
    root = spell(key[1], key[2], MAJOR_SCALE[d], d)[0]
    base = 60 + (key[2] + MAJOR_SCALE[d]) % 12
    return dict(main=numeral, line1=f"キー {key[0]}", line2="ルート音を入力",
                kind="note", lenient=True, answer=root + quality, expect=[root],
                tags=[f"ディグリー:{numeral}", f"キー:{key[0]}"],
                sound=[base + s for s in CHORD_BY_SYM[quality][1]])


def gen_keysig(cfg):
    name, letter, pc, n, sign = random.choice(KEYSIGS)
    minor = spell(letter, pc, 9, 5)[0] + "m"
    tonic = [60 + pc + s for s in (0, 4, 7)]
    if pick_dir(cfg["keysig_dir"], "sig2key", "key2sig"):
        return dict(main=sig_text(n, sign), line1="何調？", line2="短調は m を付ける",
                    kind="keyname", answer=f"{name} / {minor}", expect=(name, minor),
                    tags=[f"調号:{sig_text(n, sign)}→調"], sound=tonic)
    is_minor = random.random() < 0.5
    tonic_minor = [60 + (pc + 9) % 12 + s for s in (0, 3, 7)]
    return dict(main=minor if is_minor else name, line1="調号は？", line2="例: 4#  3b  0",
                kind="keysig", answer=sig_text(n, sign), expect=(n, sign),
                tags=[f"調号:調→{sig_text(n, sign)}"], sound=tonic_minor if is_minor else tonic)


def gen_transpose(cfg):
    pool = [i for i in INSTRUMENTS if i[0] in cfg["instruments"]] or INSTRUMENTS
    inst, semis, steps = random.choice(pool)
    note = random.choice(pick_roots(cfg))
    w2c = pick_dir(cfg["transpose_dir"], "w2c", "c2w")
    answer, _ = spell(note[1], note[2], semis, steps, up=not w2c)
    base = 64 + note[2] if w2c else 52 + note[2]
    return dict(main=note[0], line1=f"in {inst}  {'記譜 → 実音' if w2c else '実音 → 記譜'}",
                line2="実音は？" if w2c else "記譜は？", kind="note", answer=answer, expect=[answer],
                tags=[f"移調:in {inst} {'記譜→実音' if w2c else '実音→記譜'}"],
                sound=[base, base - semis if w2c else base + semis])


def gen_circle(cfg):
    root = random.choice(pick_roots(cfg))
    up5 = pick_dir(cfg["circle_dir"], "up5", "up4")
    semis, steps = (7, 4) if up5 else (5, 3)
    answer, _ = spell(root[1], root[2], semis, steps)
    base = 60 + root[2]
    return dict(main=root[0], line1="5度上" if up5 else "4度上", line2="五度圏",
                kind="note", answer=answer, expect=[answer],
                tags=[f"五度圏:{'5度上' if up5 else '4度上'}", f"ルート:{root[0]}"],
                sound=[base, base + semis])


GENERATORS = {"interval": gen_interval, "chord": gen_chord, "degree": gen_degree,
              "keysig": gen_keysig, "transpose": gen_transpose, "circle": gen_circle}


def answer_names(q):
    if q["kind"] in ("note", "notes"):
        return q["expect"]
    if q["kind"] == "keyname":
        return list(q["expect"])
    return []


def make_one(cfg):
    gen = GENERATORS.get(cfg["mode"], gen_interval)
    q = gen(cfg)
    for _ in range(100):
        if not (cfg["avoid_double"] and has_double(answer_names(q))):
            break
        q = gen(cfg)
    return q


def tag_weight(stats, tag):
    tries, misses = stats.get(tag, (0, 0))
    return 1 + 6 * misses / (tries + 1)


def make_question(cfg):
    """苦手を多めに出す設定なら、候補の中から間違えた項目ほど選ばれやすくする。"""
    if not cfg["weak_focus"] or not cfg["stats"]:
        return make_one(cfg)
    cands = [make_one(cfg) for _ in range(8)]
    weights = [sum(tag_weight(cfg["stats"], t) for t in q["tags"]) / len(q["tags"]) for q in cands]
    return random.choices(cands, weights)[0]


# ---------- 判定 ----------
def format_typed(kind, typed):
    """入力中の文字を ♯ ♭ 付きで見せる。"""
    if kind == "keysig":
        return typed.replace("#", "♯").replace("+", "♯").replace("b", "♭").replace("-", "♭")
    out = []
    for token in typed.split(" "):
        p = parse_lead(token)
        out.append(p[0] + p[2] if p else token)
    return " ".join(out)


def check(q, typed, enharmonic_ok):
    """(結果, 入力の表示) を返す。結果は ok / enh(音は合うが表記ちがい) / ng。読めなければ None。"""
    kind = q["kind"]
    if kind == "note":
        p = parse_lead(typed)
        if not p or (p[2] and not q.get("lenient")):
            return None
        name, pc = p[0], p[1]
        want = q["expect"][0]
        if name == want:
            return "ok", name
        return ("enh" if pc == name_pc(want) else "ng"), name
    if kind == "notes":
        parsed = [parse_note(t) for t in typed.split()]
        if not parsed or None in parsed:
            return None
        names = [p[0] for p in parsed]
        shown = " ".join(names)
        if sorted(names) == sorted(q["expect"]):
            return "ok", shown
        want_pcs = sorted(name_pc(n) for n in q["expect"])
        return ("enh" if sorted(p[1] for p in parsed) == want_pcs else "ng"), shown
    if kind == "keyname":
        p = parse_lead(typed)
        if not p or p[2] not in ("", "m"):
            return None
        major, minor = q["expect"]
        name, want = (p[0] + "m", minor) if p[2] == "m" else (p[0], major)
        if name == want:
            return "ok", name
        return ("enh" if p[1] == name_pc(want) else "ng"), name
    if kind == "keysig":
        p = parse_keysig(typed)
        if not p:
            return None
        return ("ok" if p == tuple(q["expect"]) else "ng"), sig_text(*p)
    return None


BG = "#141518"
OUTLINE = "#0a0a0c"
FG = "#e9e9ea"
DIM = "#6c6f78"
OK = "#8fd4b4"
WARN = "#e2c27c"
NG = "#e58a8a"
FONT = "Segoe UI"
FONT_JP = "Yu Gothic UI"


def round_corners(win, on=True):
    """Windows 11 で枠なしウィンドウの角を丸め、縁の線を消す（失敗しても無視）。
    角丸だと影が付くので、背景を消している間は on=False で角丸をやめる。"""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        # 33: 角の形 (2=丸, 1=丸めない) / 34: 縁の色 (COLOR_NONE)
        for attr, value in ((33, 2 if on else 1), (34, 0xFFFFFFFE)):
            v = ctypes.c_uint(value)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
    except Exception:
        pass


class OutlinedText:
    """縁取り付きの文字。背景が透明でもどんな壁紙の上で読めるようにする。
    Label と同じく config(text=..., fg=...) で書き換える。"""

    def __init__(self, canvas, x, y, anchor, font, fg, text="", on_change=None):
        self.canvas, self.on_change = canvas, on_change
        r = max(1, round(canvas.winfo_fpixels("1p") * 0.75))
        if font[1] < 12:  # 小さい文字は縁を細く（上下左右のみ1px）
            offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        else:
            offsets = [(dx, dy) for dx in (-r, 0, r) for dy in (-r, 0, r) if dx or dy]
        self.shadow = [canvas.create_text(x + dx, y + dy, anchor=anchor, font=font, fill=OUTLINE, text=text)
                       for dx, dy in offsets]
        self.main = canvas.create_text(x, y, anchor=anchor, font=font, fill=fg, text=text)
        self.offsets = offsets

    def config(self, text=None, fg=None):
        if text is not None:
            for i in self.shadow + [self.main]:
                self.canvas.itemconfig(i, text=text)
            if self.on_change:
                self.on_change()
        if fg is not None:
            self.canvas.itemconfig(self.main, fill=fg)

    def cget(self, key):
        return self.canvas.itemcget(self.main, "fill" if key == "fg" else key)

    __getitem__ = cget

    def move_to(self, x, y):
        self.canvas.coords(self.main, x, y)
        for i, (dx, dy) in zip(self.shadow, self.offsets):
            self.canvas.coords(i, x + dx, y + dy)

    def width(self):
        box = self.canvas.bbox(self.main)
        return box[2] - box[0] if box and self.canvas.itemcget(self.main, "text") else 0

    def right(self):
        box = self.canvas.bbox(self.main)
        return box[2] if box else 0


class App:
    def __init__(self, master):
        self.master = master
        self.cfg = dict(DEFAULTS)
        try:
            self.cfg.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass

        self.running = False
        self.after_ids = []
        self.question = None
        self.revealed = False
        self.count = 0
        self.typed = ""
        self.answered = 0
        self.correct = 0
        self.last_time = None
        self.started = 0.0
        self.active_until = 0.0

        master.title("Interval")
        master.overrideredirect(True)
        master.configure(bg=BG)
        master.attributes("-topmost", self.cfg["topmost"])
        master.attributes("-alpha", self.cfg["idle_alpha"])
        self.clear = None

        s = master.winfo_fpixels("1p") * 0.75  # 96dpi 基準の倍率
        self.s = s
        self.min_w, h = int(290 * s), int(70 * s)
        body = self.body = tk.Canvas(master, width=self.min_w, height=h, bg=BG, highlightthickness=0)
        body.pack(fill="both", expand=True)
        mid = h / 2
        self.root_lbl = OutlinedText(body, 16 * s, mid, "w", (FONT + " Light", 28), FG, "·")
        self.iv_lbl = OutlinedText(body, 0, mid + 1 * s, "sw", (FONT_JP, 10), FG)
        self.dir_lbl = OutlinedText(body, 0, mid + 3 * s, "nw", (FONT_JP, 9), DIM)
        self.ans_lbl = OutlinedText(body, 0, mid + 4 * s, "se", (FONT + " Light", 18), DIM, "space")
        self.sub_lbl = OutlinedText(body, 0, mid + 6 * s, "ne", (FONT, 8), DIM)
        for lbl in (self.root_lbl, self.iv_lbl, self.dir_lbl, self.ans_lbl, self.sub_lbl):
            lbl.on_change = self.layout

        # 自動送りの残り時間（下端の細い線）
        self.bar = tk.Canvas(master, height=2, bg=BG, highlightthickness=0)
        self.bar.pack(fill="x", side="bottom")

        self.mode_var = tk.StringVar(value=self.cfg["mode"])
        mopt = dict(tearoff=0, bg=BG, fg=FG, activebackground="#2a2c31", activeforeground=FG, bd=0,
                    font=(FONT_JP, 9), selectcolor=FG)
        self.menu = tk.Menu(master, **mopt)
        self.menu.add_command(label="次へ\tSpace", command=self.new_question)
        self.menu.add_command(label="答え\tEnter", command=self.reveal)
        self.menu.add_command(label="自動 開始/停止\tTab", command=self.toggle_run)
        self.menu.add_separator()
        mode_menu = tk.Menu(self.menu, **mopt)
        for key, label in MODES:
            mode_menu.add_radiobutton(label=label, value=key, variable=self.mode_var, command=self.on_mode)
        self.menu.add_cascade(label="モード", menu=mode_menu)
        self.menu.add_command(label="設定…\tEsc", command=self.toggle_settings)
        self.menu.add_command(label="終了", command=self.on_close)

        for w in (master, body, self.bar):
            w.bind("<ButtonPress-1>", self.drag_start)
            w.bind("<B1-Motion>", self.drag_move)
            w.bind("<Button-3>", self.show_menu)
        master.bind("<Key>", self.on_key)

        self.build_settings()
        self.layout()
        if self.cfg["geometry"]:
            master.geometry(self.cfg["geometry"])
        else:
            master.update_idletasks()
            sw, sh = master.winfo_screenwidth(), master.winfo_screenheight()
            w, h = master.winfo_reqwidth(), master.winfo_reqheight()
            master.geometry(f"+{sw - w - 40}+{sh - h - 110}")
        master.after(50, master.focus_force)
        self.poll_hover()

    def layout(self):
        """文字の幅に合わせて配置し、答えが長いときはウィンドウを左へ広げる。"""
        if not hasattr(self, "sub_lbl"):
            return
        s, c = self.s, self.body
        h = int(c["height"]) / 2
        x = self.root_lbl.right() + 10 * s
        self.iv_lbl.move_to(x, h + 1 * s)
        self.dir_lbl.move_to(x, h + 3 * s)
        left = max(self.iv_lbl.right(), self.dir_lbl.right(), self.root_lbl.right())
        right_w = max(self.ans_lbl.width(), self.sub_lbl.width())
        need = max(self.min_w, int(left + 24 * s + right_w + 16 * s))
        old = int(c["width"])
        if need != old:
            c.config(width=need)
            m = self.master
            if m.winfo_ismapped():
                m.geometry(f"+{m.winfo_x() + old - need}+{m.winfo_y()}")  # 右端を固定
        self.ans_lbl.move_to(need - 16 * s, h + 4 * s)
        self.sub_lbl.move_to(need - 16 * s, h + 6 * s)

    # ---------- ウィンドウ操作 ----------
    def drag_start(self, e):
        self.master.focus_force()
        self._drag = (e.x_root - self.master.winfo_x(), e.y_root - self.master.winfo_y())

    def drag_move(self, e):
        dx, dy = self._drag
        self.master.geometry(f"+{e.x_root - dx}+{e.y_root - dy}")

    def show_menu(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)

    def poll_hover(self):
        """マウスが乗っている間・入力直後だけ濃く表示する。"""
        m = self.master
        x, y = m.winfo_pointerxy()
        inside = m.winfo_rootx() <= x < m.winfo_rootx() + m.winfo_width() and \
            m.winfo_rooty() <= y < m.winfo_rooty() + m.winfo_height()
        busy = inside or time.monotonic() < self.active_until or self.settings_shown
        # 待機中は背景を完全に透明にして文字だけ浮かせる
        clear = not busy and self.cfg["clear_bg"]
        if clear != self.clear:
            self.clear = clear
            m.attributes("-transparentcolor", BG if clear else "")
            round_corners(m, not clear)
        target = 0.95 if busy else self.cfg["idle_alpha"]
        cur = float(m.attributes("-alpha"))
        if abs(cur - target) > 0.01:
            m.attributes("-alpha", cur + (target - cur) * 0.35)
        m.after(40 if abs(cur - target) > 0.01 else 150, self.poll_hover)

    def wake(self, sec=2.5):
        self.active_until = time.monotonic() + sec

    # ---------- 設定ウィンドウ ----------
    def build_settings(self):
        win = self.settings = tk.Toplevel(self.master, bg=BG, padx=14, pady=10)
        win.title("設定")
        win.attributes("-toolwindow", True)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self.toggle_settings)
        win.bind("<Escape>", lambda e: self.toggle_settings())
        win.withdraw()
        self.settings_shown = False

        opt = dict(bg=BG, fg=FG, selectcolor=BG, activebackground=BG, activeforeground=FG,
                   font=(FONT_JP, 9), highlightthickness=0, bd=0)

        def heading(parent, text):
            tk.Label(parent, text=text, bg=BG, fg=DIM, font=(FONT_JP, 8)).pack(anchor="w", pady=(8, 2))

        def radios(parent, var, items):
            row = tk.Frame(parent, bg=BG)
            row.pack(anchor="w")
            for text, val in items:
                tk.Radiobutton(row, text=text, value=val, variable=var, command=self.save, **opt) \
                    .pack(side="left", padx=(0, 6))

        def checks(parent, items, selected, cols):
            grid = tk.Frame(parent, bg=BG)
            grid.pack(anchor="w")
            out = {}
            for i, (text, key) in enumerate(items):
                v = tk.BooleanVar(value=key in selected)
                out[key] = v
                tk.Checkbutton(grid, text=text, variable=v, command=self.save, **opt) \
                    .grid(row=i // cols, column=i % cols, sticky="w", padx=(0, 6))
            return out

        heading(win, "モード")
        mgrid = tk.Frame(win, bg=BG)
        mgrid.pack(anchor="w")
        for i, (key, label) in enumerate(MODES):
            tk.Radiobutton(mgrid, text=label, value=key, variable=self.mode_var, command=self.on_mode, **opt) \
                .grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 8))

        # モードごとの設定（選んだモードの分だけ表示）
        self.mode_box = tk.Frame(win, bg=BG)
        self.mode_box.pack(anchor="w", fill="x")
        self.mode_frames = {k: tk.Frame(self.mode_box, bg=BG) for k, _ in MODES}

        f = self.mode_frames["interval"]
        heading(f, "音程　1つ＝指定 / 複数＝ランダム")
        self.iv_vars = checks(f, [(n, a) for n, a, *_ in INTERVALS], self.cfg["intervals"], 4)
        row = tk.Frame(f, bg=BG)
        row.pack(anchor="w", pady=(2, 0))
        for text, val in (("すべて", True), ("クリア", False)):
            lbl = tk.Label(row, text=text, bg=BG, fg=DIM, font=(FONT_JP, 8), cursor="hand2")
            lbl.pack(side="left", padx=(0, 10))
            lbl.bind("<Button-1>", lambda e, val=val: self.set_all(val))
        heading(f, "方向")
        self.dir_var = tk.StringVar(value=self.cfg["direction"])
        radios(f, self.dir_var, (("上行 ↑", "up"), ("下行 ↓", "down"), ("ランダム", "random")))

        f = self.mode_frames["chord"]
        heading(f, "コードの種類　入力例: ab cb eb gb")
        self.chord_vars = checks(f, [(c[0] or "M（メジャー）", c[0]) for c in CHORDS], self.cfg["chords"], 4)

        f = self.mode_frames["degree"]
        heading(f, "長調のディグリー → コードのルート音を答える")
        self.deg_var = tk.StringVar(value=self.cfg["degree_type"])
        radios(f, self.deg_var, (("三和音", "triad"), ("四和音", "seventh"), ("両方", "both")))

        f = self.mode_frames["keysig"]
        heading(f, "出題の向き　調名は E / C#m のように答える")
        self.ks_var = tk.StringVar(value=self.cfg["keysig_dir"])
        radios(f, self.ks_var, (("調号 → 調名", "sig2key"), ("調名 → 調号", "key2sig"), ("両方", "both")))

        f = self.mode_frames["transpose"]
        heading(f, "楽器")
        self.inst_vars = checks(f, [(f"in {i[0]}", i[0]) for i in INSTRUMENTS], self.cfg["instruments"], 4)
        heading(f, "出題の向き")
        self.tr_var = tk.StringVar(value=self.cfg["transpose_dir"])
        radios(f, self.tr_var, (("記譜 → 実音", "w2c"), ("実音 → 記譜", "c2w"), ("両方", "both")))

        f = self.mode_frames["circle"]
        heading(f, "出題　答えるまでの秒数も表示")
        self.circ_var = tk.StringVar(value=self.cfg["circle_dir"])
        radios(f, self.circ_var, (("5度上", "up5"), ("4度上", "up4"), ("両方", "both")))

        heading(win, "ルート音・調　どちらも外すと幹音（C D E F G A B）のみ")
        rrow = tk.Frame(win, bg=BG)
        rrow.pack(anchor="w")
        self.rsharp_var = tk.BooleanVar(value=self.cfg["root_sharp"])
        self.rflat_var = tk.BooleanVar(value=self.cfg["root_flat"])
        for text, var in (("♯ を含める", self.rsharp_var), ("♭ を含める", self.rflat_var)):
            tk.Checkbutton(rrow, text=text, variable=var, command=self.save, **opt).pack(side="left", padx=(0, 6))

        heading(win, "苦手")
        self.weak_var = tk.BooleanVar(value=self.cfg["weak_focus"])
        wrow = tk.Frame(win, bg=BG)
        wrow.pack(anchor="w", fill="x")
        tk.Checkbutton(wrow, text="苦手を多めに出す", variable=self.weak_var, command=self.save, **opt) \
            .pack(side="left")
        reset = tk.Label(wrow, text="記録をリセット", bg=BG, fg=DIM, font=(FONT_JP, 8), cursor="hand2")
        reset.pack(side="left", padx=(12, 0))
        reset.bind("<Button-1>", lambda e: self.reset_stats())
        self.weak_lbl = tk.Label(win, text="", bg=BG, fg=FG, font=(FONT_JP, 8), justify="left")
        self.weak_lbl.pack(anchor="w")

        heading(win, "自動送り")
        trow = tk.Frame(win, bg=BG)
        trow.pack(anchor="w")
        sp = dict(width=4, increment=0.5, font=(FONT, 9), command=self.save, bg="#202227", fg=FG,
                  buttonbackground="#202227", relief="flat", insertbackground=FG)
        tk.Label(trow, text="次の問題まで", bg=BG, fg=FG, font=(FONT_JP, 9)).pack(side="left")
        self.auto_var = tk.DoubleVar(value=self.cfg["auto_sec"])
        tk.Spinbox(trow, from_=1, to=60, textvariable=self.auto_var, **sp).pack(side="left", padx=(4, 12))
        tk.Label(trow, text="答え表示まで", bg=BG, fg=FG, font=(FONT_JP, 9)).pack(side="left")
        self.reveal_var = tk.DoubleVar(value=self.cfg["reveal_sec"])
        tk.Spinbox(trow, from_=0, to=60, textvariable=self.reveal_var, **sp).pack(side="left", padx=4)
        tk.Label(trow, text="秒", bg=BG, fg=DIM, font=(FONT_JP, 9)).pack(side="left")

        heading(win, "表示")
        arow = tk.Frame(win, bg=BG)
        arow.pack(anchor="w", fill="x")
        tk.Label(arow, text="待機中の濃さ", bg=BG, fg=FG, font=(FONT_JP, 9)).pack(side="left")
        self.alpha_var = tk.DoubleVar(value=self.cfg["idle_alpha"])
        tk.Scale(arow, from_=0.1, to=1.0, resolution=0.05, orient="horizontal", variable=self.alpha_var,
                 showvalue=False, length=140, bg=BG, fg=FG, troughcolor="#2a2c31", highlightthickness=0,
                 bd=0, sliderrelief="flat", sliderlength=14, width=8, command=lambda v: self.save()) \
            .pack(side="left", padx=8)

        heading(win, "オプション")
        self.sound_var = tk.BooleanVar(value=self.cfg["sound"])
        self.top_var = tk.BooleanVar(value=self.cfg["topmost"])
        self.dbl_var = tk.BooleanVar(value=self.cfg["avoid_double"])
        self.enh_var = tk.BooleanVar(value=self.cfg["enharmonic_ok"])
        self.clear_var = tk.BooleanVar(value=self.cfg["clear_bg"])
        for text, var in (("待機中は背景を消す", self.clear_var), ("答えで音を鳴らす", self.sound_var),
                          ("最前面に表示", self.top_var), ("ダブル♯・ダブル♭を避ける", self.dbl_var),
                          ("異名同音も正解にする（D♯ = E♭）", self.enh_var)):
            tk.Checkbutton(win, text=text, variable=var, command=self.save, **opt).pack(anchor="w")

        tk.Label(win, text="♯: #  右隣のキー  → ↑　　♭: b  左隣のキー  ← ↓\n"
                           "Space 次へ / Enter 判定 / Tab 自動 / 右クリック メニュー",
                 bg=BG, fg=DIM, font=(FONT_JP, 8), justify="left").pack(anchor="w", pady=(10, 0))

        self.show_mode_frame()
        self.refresh_weak()

    def show_mode_frame(self):
        for f in self.mode_frames.values():
            f.pack_forget()
        self.mode_frames.get(self.mode_var.get(), self.mode_frames["interval"]).pack(anchor="w", fill="x")

    def refresh_weak(self):
        """間違えた割合が高い項目を表示する（3回以上出た項目のみ）。"""
        rows = [(m / t, t, m, tag) for tag, (t, m) in self.cfg["stats"].items() if t >= 3 and m]
        rows.sort(reverse=True)
        lines = [f"{tag}  {m}/{t} ミス" for _, t, m, tag in rows[:5]]
        self.weak_lbl.config(text="\n".join(lines) or "（まだ記録がありません）",
                             fg=FG if lines else DIM)

    def reset_stats(self):
        self.cfg["stats"] = {}
        self.save()
        self.refresh_weak()

    def toggle_settings(self):
        if self.settings_shown:
            self.settings.withdraw()
            self.master.focus_force()
        else:
            self.refresh_weak()
            m = self.master
            self.settings.update_idletasks()
            w, h = self.settings.winfo_reqwidth(), self.settings.winfo_reqheight()
            x = max(0, min(m.winfo_rootx(), m.winfo_screenwidth() - w - 10))
            y = m.winfo_rooty() - h - 40
            if y < 0:
                y = m.winfo_rooty() + m.winfo_height() + 10
            self.settings.geometry(f"+{x}+{max(0, y)}")
            self.settings.deiconify()
        self.settings_shown = not self.settings_shown

    def on_mode(self):
        self.show_mode_frame()
        self.save()
        self.new_question()

    def set_all(self, val):
        for v in self.iv_vars.values():
            v.set(val)
        self.save()

    def num(self, var, default):
        try:
            return max(0.0, float(var.get()))
        except (tk.TclError, ValueError):
            return default

    def save(self):
        def chosen(vars_):
            return [k for k, v in vars_.items() if v.get()]

        self.cfg.update(
            mode=self.mode_var.get(),
            intervals=chosen(self.iv_vars),
            direction=self.dir_var.get(),
            chords=chosen(self.chord_vars),
            degree_type=self.deg_var.get(),
            keysig_dir=self.ks_var.get(),
            instruments=chosen(self.inst_vars),
            transpose_dir=self.tr_var.get(),
            circle_dir=self.circ_var.get(),
            weak_focus=self.weak_var.get(),
            auto_sec=self.num(self.auto_var, DEFAULTS["auto_sec"]),
            reveal_sec=self.num(self.reveal_var, DEFAULTS["reveal_sec"]),
            idle_alpha=self.num(self.alpha_var, DEFAULTS["idle_alpha"]),
            sound=self.sound_var.get(),
            topmost=self.top_var.get(),
            avoid_double=self.dbl_var.get(),
            enharmonic_ok=self.enh_var.get(),
            clear_bg=self.clear_var.get(),
            root_sharp=self.rsharp_var.get(),
            root_flat=self.rflat_var.get(),
        )
        self.master.attributes("-topmost", self.cfg["topmost"])
        try:
            SETTINGS_FILE.write_text(json.dumps(self.cfg, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    # ---------- 出題 ----------
    def cancel_timers(self):
        for a in self.after_ids:
            self.master.after_cancel(a)
        self.after_ids = []

    def later(self, sec, fn):
        self.after_ids.append(self.master.after(int(sec * 1000), fn))

    def new_question(self):
        self.save()
        self.cancel_timers()
        q = self.question = make_question(self.cfg)
        self.revealed = False
        self.typed = ""
        self.count += 1
        self.started = time.monotonic()
        self.root_lbl.config(text=q["main"])
        self.iv_lbl.config(text=q["line1"])
        self.dir_lbl.config(text=q["line2"])
        self.ans_lbl.config(text="", fg=DIM)
        self.update_count()

        if self.running:
            auto = max(1.0, self.cfg["auto_sec"])
            reveal = min(self.cfg["reveal_sec"], auto)
            if reveal > 0:
                self.later(reveal, self.reveal)
            self.later(auto, self.new_question)
            self.animate_bar(auto)
        else:
            self.bar.delete("all")

    def animate_bar(self, total, elapsed=0.0):
        self.bar.delete("all")
        w = self.bar.winfo_width()
        self.bar.create_rectangle(0, 0, w * min(1, elapsed / total), 2, fill="#3d4048", width=0)
        if self.running and elapsed < total:
            self.after_ids.append(self.master.after(100, self.animate_bar, total, elapsed + 0.1))

    def update_count(self):
        parts = []
        if self.last_time is not None and self.revealed:
            parts.append(f"{self.last_time:.1f}s")
        if self.answered:
            parts.append(f"{self.correct}/{self.answered}")
        if self.running:
            parts.append("auto")
        self.sub_lbl.config(text="  ".join(parts))

    # ---------- キー入力 ----------
    def accidental_key(self, key, ch):
        """音名の直後なら、左右隣のキー・方向キーを ♭ / ♯ に読み替える。"""
        token = self.typed.split(" ")[-1]
        if not token or token[0] not in NEIGHBORS or self.question["kind"] == "keysig":
            return None
        if key in ARROWS:
            return ARROWS[key]
        left, right = NEIGHBORS[token[0]]
        if ch and ch == left:
            return "b"
        if ch and ch == right:
            return "#"
        return None

    def allowed(self, ch):
        kind = self.question["kind"]
        if kind == "keysig":
            return ch in "0123456789#+b-"
        if not self.typed.split(" ")[-1]:  # 音の頭は音名だけ
            return ch in "abcdefg"
        if kind == "keyname":
            return ch in "#+b-xm"
        if self.question.get("lenient"):
            return ch.isalnum() or ch in "#+-♭"
        return ch in "#+b-x"

    def on_key(self, e):
        if isinstance(e.widget, (tk.Spinbox, tk.Entry)):
            return None
        self.wake()
        key, ch = e.keysym, e.char.lower()
        q = self.question
        typing = q is not None and not self.revealed
        if key == "Escape":
            self.toggle_settings()
        elif key == "Tab":
            self.toggle_run()
            return "break"
        elif key == "space":
            if typing and q["kind"] == "notes" and self.typed and not self.typed.endswith(" "):
                self.typed += " "  # コード構成音では音の区切り
                self.show_typed()
            else:
                self.new_question()
        elif key in ("Return", "KP_Enter"):
            if not typing:
                self.new_question()
            elif self.typed.strip():
                self.judge()
            else:
                self.reveal()
        elif key == "BackSpace":
            if typing:
                self.typed = self.typed[:-1]
                self.show_typed()
        elif typing:
            acc = self.accidental_key(key, ch)
            if acc:
                ch = acc
            elif not ch or not self.allowed(ch):
                return None
            if len(self.typed) < (30 if q["kind"] == "notes" else 10):
                self.typed += ch
                self.show_typed()
        return None

    def show_typed(self):
        if self.revealed:
            return
        text = format_typed(self.question["kind"], self.typed)
        self.ans_lbl.config(text=text + "_" if self.typed else "", fg=FG)

    def judge(self):
        q = self.question
        res = check(q, self.typed, self.cfg["enharmonic_ok"])
        if not res:
            return
        status, shown = res
        ok = status == "ok" or (status == "enh" and self.cfg["enharmonic_ok"])
        self.last_time = time.monotonic() - self.started
        self.answered += 1
        self.correct += ok
        stats = self.cfg["stats"]
        for tag in q["tags"]:
            tries, misses = stats.get(tag, (0, 0))
            stats[tag] = [tries + 1, misses + (not ok)]
        if ok:
            result, color = q["answer"], OK
        elif q["kind"] == "notes":
            result, color = q["answer"], WARN if status == "enh" else NG  # 長くなるので正解だけ
        elif status == "enh":
            result, color = f"{shown} ≈ {q['answer']}", WARN  # 音は合っているが表記ちがい
        else:
            result, color = f"{shown} → {q['answer']}", NG
        self.reveal(result, color)
        if self.running:
            # 自動モードでは回答後すぐ次へ
            self.cancel_timers()
            self.bar.delete("all")
            self.later(1.0 if ok else 2.0, self.new_question)

    def reveal(self, text=None, color=None):
        if not self.question or self.revealed:
            return
        self.revealed = True
        if text is None:
            self.last_time = None
        self.ans_lbl.config(text=text or self.question["answer"], fg=color or FG)
        self.update_count()
        if self.cfg["sound"] and winsound:
            threading.Thread(target=self.play, args=(self.question["sound"],), daemon=True).start()

    @staticmethod
    def play(notes):
        for i, m in enumerate(notes):
            winsound.Beep(midi_freq(m), 650 if i == len(notes) - 1 else 380)

    def toggle_run(self):
        self.running = not self.running
        if self.running:
            self.new_question()
        else:
            self.cancel_timers()
            self.bar.delete("all")
            self.update_count()

    def on_close(self):
        self.cfg["geometry"] = "+%d+%d" % (self.master.winfo_x(), self.master.winfo_y())
        self.save()
        self.master.destroy()


if __name__ == "__main__":
    try:  # 高DPI画面で文字をくっきり表示
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    master = tk.Tk()
    App(master)
    master.mainloop()
