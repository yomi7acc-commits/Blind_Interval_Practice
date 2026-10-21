"""PCの片隅で使うインターバル（音程）練習ツール。

ルート音はランダム、音程は選択したものから（1つだけ選べば指定、複数ならランダム）。
答えの入力: 音名 A-G に続けて # または + で♯、b または - で♭（例: eb, f#, bb）→ Enter
Space: 次へ / Enter: 判定（未入力なら答え表示、表示後なら次へ） / Backspace: 1文字消す
1: 自動の開始・停止 / Esc: 設定の開閉 / 右クリック: メニュー / ドラッグで移動
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
ACC = {-2: "𝄫", -1: "♭", 0: "", 1: "♯", 2: "𝄪"}

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

DEFAULTS = {
    "intervals": ["m3", "M3", "P4", "P5"],
    "direction": "up",  # up / down / random
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


def spell(root_letter, root_pc, semis, steps, up):
    sign = 1 if up else -1
    letter = (root_letter + sign * steps) % 7
    pc = (root_pc + sign * semis) % 12
    diff = (pc - NATURAL_PC[letter] + 6) % 12 - 6  # -6..5
    return LETTERS[letter] + ACC.get(diff, "?"), abs(diff) >= 2


def make_question(abbrs, direction, avoid_double, root_sharp=True, root_flat=True):
    pool = [iv for iv in INTERVALS if iv[1] in abbrs] or INTERVALS
    roots = [r for r in ROOTS
             if len(r[0]) == 1 or (root_sharp and "♯" in r[0]) or (root_flat and "♭" in r[0])]
    for _ in range(100):
        root = random.choice(roots)
        iv = random.choice(pool)
        up = direction == "up" or (direction == "random" and random.random() < 0.5)
        answer, double = spell(root[1], root[2], iv[2], iv[3], up)
        if not (avoid_double and double):
            return root, iv, up, answer
    return root, iv, up, answer


def parse_note(text):
    """'eb' → ('E♭', ピッチクラス)。不完全なら None。"""
    text = text.strip().lower()
    if not text or text[0] not in "cdefgab":
        return None
    letter = "cdefgab".index(text[0])
    offset = 0
    for ch in text[1:]:
        if ch in "#+":
            offset += 1
        elif ch in "b-":
            offset -= 1
        elif ch == "x":
            offset += 2
        else:
            return None
    if abs(offset) > 2:
        return None
    return LETTERS[letter] + ACC[offset], (NATURAL_PC[letter] + offset) % 12


def midi_freq(m):
    return int(440 * 2 ** ((m - 69) / 12))


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

    def right(self):
        return self.canvas.bbox(self.main)[2]


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
        self.active_until = 0.0

        master.title("Interval")
        master.overrideredirect(True)
        master.configure(bg=BG)
        master.attributes("-topmost", self.cfg["topmost"])
        master.attributes("-alpha", self.cfg["idle_alpha"])
        self.clear = None

        s = master.winfo_fpixels("1p") * 0.75  # 96dpi 基準の倍率
        self.s = s
        w, h = int(290 * s), int(70 * s)
        body = tk.Canvas(master, width=w, height=h, bg=BG, highlightthickness=0)
        body.pack(fill="both", expand=True)
        mid = h / 2
        self.root_lbl = OutlinedText(body, 16 * s, mid, "w", (FONT + " Light", 28), FG, "·",
                                     on_change=self.layout)
        self.iv_lbl = OutlinedText(body, 0, mid + 1 * s, "sw", (FONT_JP, 10), FG)
        self.dir_lbl = OutlinedText(body, 0, mid + 3 * s, "nw", (FONT, 9), DIM)
        self.ans_lbl = OutlinedText(body, w - 16 * s, mid + 4 * s, "se", (FONT + " Light", 18), DIM, "space")
        self.sub_lbl = OutlinedText(body, w - 16 * s, mid + 6 * s, "ne", (FONT, 8), DIM)
        self.layout()

        # 自動送りの残り時間（下端の細い線）
        self.bar = tk.Canvas(master, height=2, bg=BG, highlightthickness=0)
        self.bar.pack(fill="x", side="bottom")

        self.menu = tk.Menu(master, tearoff=0, bg=BG, fg=FG, activebackground="#2a2c31",
                            activeforeground=FG, bd=0, font=(FONT_JP, 9))
        self.menu.add_command(label="次へ\tSpace", command=self.new_question)
        self.menu.add_command(label="答え\tEnter", command=self.reveal)
        self.menu.add_command(label="自動 開始/停止\t1", command=self.toggle_run)
        self.menu.add_separator()
        self.menu.add_command(label="設定…\tEsc", command=self.toggle_settings)
        self.menu.add_command(label="終了", command=self.on_close)

        for w in (master, body, self.bar):
            w.bind("<ButtonPress-1>", self.drag_start)
            w.bind("<B1-Motion>", self.drag_move)
            w.bind("<Button-3>", self.show_menu)
        master.bind("<Key>", self.on_key)

        self.build_settings()
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
        """ルート音の幅に合わせて音程の表示位置をずらす。"""
        x = self.root_lbl.right() + 10 * self.s
        h = int(self.root_lbl.canvas["height"]) / 2
        self.iv_lbl.move_to(x, h + 1 * self.s)
        self.dir_lbl.move_to(x, h + 3 * self.s)

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

        def heading(text):
            tk.Label(win, text=text, bg=BG, fg=DIM, font=(FONT_JP, 8)).pack(anchor="w", pady=(8, 2))

        heading("音程　1つ＝指定 / 複数＝ランダム")
        grid = tk.Frame(win, bg=BG)
        grid.pack(anchor="w")
        self.iv_vars = {}
        for i, (name, abbr, *_rest) in enumerate(INTERVALS):
            v = tk.BooleanVar(value=abbr in self.cfg["intervals"])
            self.iv_vars[abbr] = v
            tk.Checkbutton(grid, text=name, variable=v, command=self.save, **opt) \
                .grid(row=i // 4, column=i % 4, sticky="w", padx=(0, 6))
        row = tk.Frame(win, bg=BG)
        row.pack(anchor="w", pady=(2, 0))
        for text, val in (("すべて", True), ("クリア", False)):
            lbl = tk.Label(row, text=text, bg=BG, fg=DIM, font=(FONT_JP, 8), cursor="hand2")
            lbl.pack(side="left", padx=(0, 10))
            lbl.bind("<Button-1>", lambda e, val=val: self.set_all(val))

        heading("ルート音　どちらも外すと幹音（C D E F G A B）のみ")
        rrow = tk.Frame(win, bg=BG)
        rrow.pack(anchor="w")
        self.rsharp_var = tk.BooleanVar(value=self.cfg["root_sharp"])
        self.rflat_var = tk.BooleanVar(value=self.cfg["root_flat"])
        for text, var in (("♯ を含める", self.rsharp_var), ("♭ を含める", self.rflat_var)):
            tk.Checkbutton(rrow, text=text, variable=var, command=self.save, **opt).pack(side="left", padx=(0, 6))

        heading("方向")
        drow = tk.Frame(win, bg=BG)
        drow.pack(anchor="w")
        self.dir_var = tk.StringVar(value=self.cfg["direction"])
        for text, val in (("上行 ↑", "up"), ("下行 ↓", "down"), ("ランダム", "random")):
            tk.Radiobutton(drow, text=text, value=val, variable=self.dir_var, command=self.save, **opt) \
                .pack(side="left", padx=(0, 6))

        heading("自動送り")
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

        heading("表示")
        arow = tk.Frame(win, bg=BG)
        arow.pack(anchor="w", fill="x")
        tk.Label(arow, text="待機中の濃さ", bg=BG, fg=FG, font=(FONT_JP, 9)).pack(side="left")
        self.alpha_var = tk.DoubleVar(value=self.cfg["idle_alpha"])
        tk.Scale(arow, from_=0.1, to=1.0, resolution=0.05, orient="horizontal", variable=self.alpha_var,
                 showvalue=False, length=140, bg=BG, fg=FG, troughcolor="#2a2c31", highlightthickness=0,
                 bd=0, sliderrelief="flat", sliderlength=14, width=8, command=lambda v: self.save()) \
            .pack(side="left", padx=8)

        heading("オプション")
        self.sound_var = tk.BooleanVar(value=self.cfg["sound"])
        self.top_var = tk.BooleanVar(value=self.cfg["topmost"])
        self.dbl_var = tk.BooleanVar(value=self.cfg["avoid_double"])
        self.enh_var = tk.BooleanVar(value=self.cfg["enharmonic_ok"])
        self.clear_var = tk.BooleanVar(value=self.cfg["clear_bg"])
        for text, var in (("待機中は背景を消す", self.clear_var),("答えで音を鳴らす", self.sound_var), ("最前面に表示", self.top_var),
                          ("𝄪 𝄫 を避ける", self.dbl_var), ("異名同音も正解にする（D♯ = E♭）", self.enh_var)):
            tk.Checkbutton(win, text=text, variable=var, command=self.save, **opt).pack(anchor="w")

        tk.Label(win, text="入力: eb  f#  bb → Enter　/　右クリックでメニュー", bg=BG, fg=DIM,
                 font=(FONT_JP, 8)).pack(anchor="w", pady=(10, 0))

    def toggle_settings(self):
        if self.settings_shown:
            self.settings.withdraw()
            self.master.focus_force()
        else:
            m = self.master
            self.settings.update_idletasks()
            w, h = self.settings.winfo_reqwidth(), self.settings.winfo_reqheight()
            x = max(0, min(m.winfo_rootx(), m.winfo_screenwidth() - w - 10))
            y = m.winfo_rooty() - h - 40
            if y < 0:
                y = m.winfo_rooty() + m.winfo_height() + 10
            self.settings.geometry(f"+{x}+{y}")
            self.settings.deiconify()
        self.settings_shown = not self.settings_shown

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
        self.cfg.update(
            intervals=[k for k, v in self.iv_vars.items() if v.get()],
            direction=self.dir_var.get(),
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
        root, iv, up, answer = make_question(self.cfg["intervals"], self.cfg["direction"], self.cfg["avoid_double"],
                                             self.cfg["root_sharp"], self.cfg["root_flat"])
        self.question = (root, iv, up, answer)
        self.revealed = False
        self.typed = ""
        self.count += 1
        self.root_lbl.config(text=root[0])
        self.iv_lbl.config(text=iv[0])
        self.dir_lbl.config(text=f"{'↑' if up else '↓'}  {iv[1]}")
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
        if self.answered:
            parts.append(f"{self.correct}/{self.answered}")
        if self.running:
            parts.append("auto")
        self.sub_lbl.config(text="  ".join(parts))

    # ---------- キー入力 ----------
    def on_key(self, e):
        if isinstance(e.widget, (tk.Spinbox, tk.Entry)):
            return
        self.wake()
        key, ch = e.keysym, e.char.lower()
        if key == "Escape":
            self.toggle_settings()
        elif key == "space":
            self.new_question()
        elif key in ("Return", "KP_Enter"):
            if not self.question or self.revealed:
                self.new_question()
            elif self.typed:
                self.judge()
            else:
                self.reveal()
        elif key == "BackSpace":
            self.typed = self.typed[:-1]
            self.show_typed()
        elif ch == "1":
            self.toggle_run()
        elif ch and ch in "abcdefg#+-x" and self.question and not self.revealed:
            # 先頭は音名、2文字目以降の b は♭として扱う
            if not self.typed and ch not in "abcdefg":
                return
            if len(self.typed) >= 3:
                return
            self.typed += ch
            self.show_typed()

    def show_typed(self):
        if self.revealed:
            return
        parsed = parse_note(self.typed)
        text = parsed[0] if parsed else self.typed
        self.ans_lbl.config(text=text + ("_" if self.typed else ""), fg=FG)

    def judge(self):
        parsed = parse_note(self.typed)
        if not parsed:
            return
        name, pc = parsed
        root, iv, up, answer = self.question
        target_pc = (root[2] + (iv[2] if up else -iv[2])) % 12
        exact = name == answer
        ok = exact or (self.cfg["enharmonic_ok"] and pc == target_pc)
        self.answered += 1
        self.correct += ok
        if ok:
            result, color = answer, OK
        elif pc == target_pc:
            result, color = f"{name} ≈ {answer}", WARN  # 音は合っているが表記ちがい
        else:
            result, color = f"{name} → {answer}", NG
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
        root, iv, up, answer = self.question
        self.ans_lbl.config(text=text or answer, fg=color or FG)
        self.update_count()
        if self.cfg["sound"] and winsound:
            base = 60 + root[2] if up else 72 + root[2]
            if base > 76:
                base -= 12
            target = base + (iv[2] if up else -iv[2])
            threading.Thread(target=self.play, args=(base, target), daemon=True).start()

    @staticmethod
    def play(a, b):
        winsound.Beep(midi_freq(a), 450)
        winsound.Beep(midi_freq(b), 650)

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
