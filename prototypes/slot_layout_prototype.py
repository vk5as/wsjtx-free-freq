"""PROTOTYPE - throwaway. Question: slot panels side by side vs stacked vertically?

Three variants of the main window, switchable with the floating bar (or Left/Right keys, or --variant A|B|C):
  A  Side by side: 1st | 2nd panels, each with its own band map and a free-location table.
  B  Stacked: 1st above 2nd, full-width band maps, free locations as a chip row.
  C  Shared axis: both slots as lanes on one band map, the two lists side by side underneath.
  D  C's shared-axis band map with B's chip rows per slot.  <- CHOSEN by VK5AS

Fake decodes, no networking, Set Rx only updates in-memory state. Run:
  .venv/bin/python prototypes/slot_layout_prototype.py [--variant B]
  QT_QPA_PLATFORM=offscreen .venv/bin/python prototypes/slot_layout_prototype.py --screenshot /tmp/proto
"""

import argparse
import random
import sys

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeySequence, QPainter, QPalette, QPen, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

LO, HI, WIDTH, GUARD, STRONG_SNR, STRONG_EXTRA, WINDOW = 200, 2800, 50, 10, 10, 20, 4
SLOTS = ("1st", "2nd")


def fake_decodes(seed, count):
    rnd = random.Random(seed)
    calls = ["VK5", "ZL2", "JA1", "W6", "K7", "DL1", "G4", "VK3", "VK2", "JH7", "KH6", "VE7", "BY1", "YB0"]
    out = []
    for _ in range(count):
        out.append(
            {
                "call": rnd.choice(calls) + "".join(rnd.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(3)),
                "offset": rnd.randrange(LO, HI - WIDTH, 5),
                "snr": rnd.randint(-22, 18),
                "age": rnd.randint(0, WINDOW - 1),
            }
        )
    return out


DECODES = {"1st": fake_decodes(1, 16), "2nd": fake_decodes(2, 30)}


def occupied(decodes):
    for d in decodes:
        g = GUARD + (STRONG_EXTRA if d["snr"] >= STRONG_SNR else 0)
        yield d, d["offset"] - g, d["offset"] + WIDTH + g


def free_locations(decodes, tx):
    occ = list(occupied(decodes))
    cands = []
    for c in range(LO, HI - WIDTH + 1, 5):
        if any(c < hi and c + WIDTH > lo for _, lo, hi in occ):
            continue
        clearance = min(
            (max(lo - (c + WIDTH), c - hi) * (1 + d["age"]) for d, lo, hi in occ),
            default=HI - LO,
        )
        cands.append((clearance, -abs(c - tx), c))
    picked = []
    for clearance, _, c in sorted(cands, reverse=True):
        if all(abs(c - p) >= WIDTH for p, _ in picked):
            picked.append((c, clearance))
        if len(picked) == 10:
            break
    return picked


class State:
    def __init__(self):
        self.rx, self.tx = 1500, 1500
        self.last_action = "none yet"


# ---------- shared widgets ----------


class BandMap(QWidget):
    """One or more lanes (slots) on a shared 200-2800 Hz axis."""

    clicked = pyqtSignal(int)

    def __init__(self, state, slots, lane_height=46):
        super().__init__()
        self.state, self.slots, self.lane_height = state, slots, lane_height
        self.setMinimumHeight(lane_height * len(slots) + 22)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setToolTip("Click to Set Rx")

    def x_of(self, hz):
        return 40 + (hz - LO) / (HI - LO) * (self.width() - 50)

    def hz_of(self, x):
        return int(LO + (x - 40) / (self.width() - 50) * (HI - LO))

    def mousePressEvent(self, e):
        self.clicked.emit(max(LO, min(HI - WIDTH, round(self.hz_of(e.position().x()) / 5) * 5)))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        p.fillRect(self.rect(), pal.color(QPalette.ColorRole.Base))
        small = QFont(self.font())
        small.setPointSizeF(7.5)
        p.setFont(small)
        for i, slot in enumerate(self.slots):
            top = i * self.lane_height + 2
            lane = QRectF(self.x_of(LO), top, self.x_of(HI) - self.x_of(LO), self.lane_height - 4)
            p.fillRect(lane, QColor(20, 26, 40))
            if len(self.slots) > 1:
                p.setPen(pal.color(QPalette.ColorRole.Text))
                p.drawText(QRectF(0, top, 38, self.lane_height - 4), Qt.AlignmentFlag.AlignCenter, slot)
            for d, lo, hi in occupied(DECODES[slot]):
                alpha = int(255 * (1 - d["age"] / WINDOW * 0.7))
                p.fillRect(QRectF(self.x_of(lo), top + 6, self.x_of(hi) - self.x_of(lo), lane.height() - 12), QColor(230, 120, 40, alpha // 3))
                p.fillRect(QRectF(self.x_of(d["offset"]), top + 6, self.x_of(d["offset"] + WIDTH) - self.x_of(d["offset"]), lane.height() - 12), QColor(240, 90, 50, alpha))
            for n, (c, _) in enumerate(free_locations(DECODES[slot], self.state.tx), 1):
                r = QRectF(self.x_of(c), top + 10, self.x_of(c + WIDTH) - self.x_of(c), lane.height() - 20)
                p.fillRect(r, QColor(60, 200, 120, 90))
                p.setPen(QColor(140, 255, 180))
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, str(n))
            for hz, colour, label in ((self.state.rx, QColor(80, 200, 255), "Rx"), (self.state.tx, QColor(255, 80, 120), "Tx")):
                x = self.x_of(hz)
                p.setPen(QPen(colour, 2))
                p.drawLine(QPointF(x, top), QPointF(x, top + lane.height()))
                if i == 0:
                    p.drawText(QPointF(x + 3 + (14 if label == "Tx" else 0), top + 10), label)
        axis_y = len(self.slots) * self.lane_height + 2
        p.setPen(pal.color(QPalette.ColorRole.PlaceholderText))
        for hz in range(500, HI + 1, 500):
            x = self.x_of(hz)
            p.drawLine(QPointF(x, axis_y), QPointF(x, axis_y + 4))
            p.drawText(QRectF(x - 25, axis_y + 4, 50, 14), Qt.AlignmentFlag.AlignCenter, str(hz))


def header(state, on_change):
    w = QFrame()
    w.setFrameShape(QFrame.Shape.StyledPanel)
    h = QHBoxLayout(w)
    dot = QLabel("●")
    dot.setStyleSheet("color: #4c4; font-size: 16px;")
    h.addWidget(dot)
    h.addWidget(QLabel("Connected"))
    inst = QComboBox()
    inst.addItems(["WSJT-X", "WSJT-X - IC7300"])
    h.addWidget(inst)
    h.addSpacing(16)
    for label, value in (("Dial", "14.074 000 MHz"), ("Mode", "FT8"), ("Rx", f"{state.rx} Hz"), ("Tx", f"{state.tx} Hz")):
        lab = QLabel(f"<span style='color:gray'>{label}</span>&nbsp;<b>{value}</b>")
        h.addWidget(lab)
        h.addSpacing(10)
    h.addStretch()
    h.addWidget(QPushButton("Settings…"))
    return w


def hint(state):
    lab = QLabel(f"Rx set to <b>{state.rx} Hz</b>. Press <b>Tx ← Rx</b> in WSJT-X to move your Tx too.")
    lab.setStyleSheet("background:#3a3320; color:#f0d890; padding:6px; border-radius:4px;")
    lab.setVisible(state.last_action != "none yet")
    return lab


def slot_title(slot):
    t = QLabel(f"{slot} slot <span style='color:gray; font-weight:normal'>({'even' if slot == '1st' else 'odd'}, "
               f"{len(DECODES[slot])} decodes, last {WINDOW} cycles)</span>")
    f = t.font()
    f.setPointSizeF(f.pointSizeF() * 1.25)
    f.setBold(True)
    t.setFont(f)
    return t


def table(state, slot, on_set):
    locs = free_locations(DECODES[slot], state.tx)
    t = QTableWidget(len(locs), 4)
    t.setHorizontalHeaderLabels(["#", "Offset", "Clearance", ""])
    t.verticalHeader().hide()
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    from PyQt6.QtWidgets import QTableWidgetItem

    for row, (c, clr) in enumerate(locs):
        for col, text in enumerate((str(row + 1), f"{c} Hz", f"{clr} Hz")):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setItem(row, col, item)
        b = QPushButton("Set Rx")
        b.clicked.connect(lambda _=False, c=c: on_set(c))
        t.setCellWidget(row, 3, b)
    return t


def chips(state, slot, on_set):
    w = QWidget()
    g = QGridLayout(w)
    g.setContentsMargins(0, 0, 0, 0)
    for n, (c, clr) in enumerate(free_locations(DECODES[slot], state.tx)):
        b = QPushButton(f"{n + 1}.  {c} Hz\n±{clr} Hz clear")
        b.setStyleSheet("QPushButton{padding:6px 10px; border:1px solid #3c8; border-radius:6px; background:#1d3a2b;}"
                        "QPushButton:hover{background:#2a5a40;}")
        b.clicked.connect(lambda _=False, c=c: on_set(c))
        g.addWidget(b, n // 5, n % 5)
    return w


# ---------- variants ----------


def variant_a(state, on_set):
    root = QWidget()
    v = QVBoxLayout(root)
    v.addWidget(header(state, on_set))
    v.addWidget(hint(state))
    row = QHBoxLayout()
    for slot in SLOTS:
        col = QVBoxLayout()
        col.addWidget(slot_title(slot))
        bm = BandMap(state, [slot])
        bm.clicked.connect(on_set)
        col.addWidget(bm)
        col.addWidget(table(state, slot, on_set))
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setLayout(col)
        row.addWidget(frame)
    v.addLayout(row)
    return root


def variant_b(state, on_set):
    root = QWidget()
    v = QVBoxLayout(root)
    v.addWidget(header(state, on_set))
    v.addWidget(hint(state))
    for slot in SLOTS:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        col = QVBoxLayout(frame)
        col.addWidget(slot_title(slot))
        bm = BandMap(state, [slot], lane_height=60)
        bm.clicked.connect(on_set)
        col.addWidget(bm)
        col.addWidget(chips(state, slot, on_set))
        v.addWidget(frame)
    v.addStretch()
    return root


def variant_c(state, on_set):
    root = QWidget()
    v = QVBoxLayout(root)
    v.addWidget(header(state, on_set))
    v.addWidget(hint(state))
    bm = BandMap(state, list(SLOTS), lane_height=56)
    bm.clicked.connect(on_set)  # PROTOTYPE: lane click would set Rx for that slot; offset is all that matters
    v.addWidget(bm)
    row = QHBoxLayout()
    for slot in SLOTS:
        col = QVBoxLayout()
        col.addWidget(slot_title(slot))
        col.addWidget(table(state, slot, on_set))
        row.addLayout(col)
    v.addLayout(row)
    return root


def variant_d(state, on_set):
    root = QWidget()
    v = QVBoxLayout(root)
    v.addWidget(header(state, on_set))
    v.addWidget(hint(state))
    bm = BandMap(state, list(SLOTS), lane_height=56)
    bm.clicked.connect(on_set)
    v.addWidget(bm)
    for slot in SLOTS:
        v.addWidget(slot_title(slot))
        v.addWidget(chips(state, slot, on_set))
    v.addStretch()
    return root


VARIANTS = [
    ("A", "Side by side", variant_a),
    ("B", "Stacked", variant_b),
    ("C", "Shared axis", variant_c),
    ("D", "C map + B buttons", variant_d),
]


class Switcher(QFrame):
    def __init__(self, parent, cycle):
        super().__init__(parent)
        self.setStyleSheet("QFrame{background:#fff; border-radius:16px;} QLabel{color:#000; font-weight:bold;}"
                           "QPushButton{color:#000; background:transparent; border:none; font-size:16px; padding:2px 8px;}")
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 4, 8, 4)
        prev, nxt = QPushButton("◀"), QPushButton("▶")
        prev.clicked.connect(lambda: cycle(-1))
        nxt.clicked.connect(lambda: cycle(1))
        self.label = QLabel()
        for w in (prev, self.label, nxt):
            h.addWidget(w)

    def place(self):
        self.adjustSize()
        p = self.parentWidget()
        self.move((p.width() - self.width()) // 2, p.height() - self.height() - 12)
        self.raise_()


class Window(QMainWindow):
    def __init__(self, variant):
        super().__init__()
        self.state = State()
        self.index = [k for k, _, _ in VARIANTS].index(variant)
        self.switcher = Switcher(self, self.cycle)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self.cycle(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self.cycle(1))
        self.render_variant()

    def cycle(self, step):
        self.index = (self.index + step) % len(VARIANTS)
        self.render_variant()

    def set_rx(self, hz):
        self.state.rx = hz
        self.state.last_action = f"Set Rx {hz}"
        self.render_variant()

    def render_variant(self):
        key, name, build = VARIANTS[self.index]
        self.setCentralWidget(build(self.state, self.set_rx))
        self.setWindowTitle(f"PROTOTYPE wsjtx-free-freq - variant {key} ({name})")
        self.switcher.label.setText(f"{key} ({name})")
        self.statusBar().showMessage(f"variant={key}  rx={self.state.rx}  tx={self.state.tx}  last action: {self.state.last_action}")
        self.switcher.place()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.switcher.place()


def dark(app):
    app.setStyle("Fusion")
    p = QPalette()
    for role, c in (
        (QPalette.ColorRole.Window, "#1e2129"), (QPalette.ColorRole.WindowText, "#dde"),
        (QPalette.ColorRole.Base, "#161920"), (QPalette.ColorRole.AlternateBase, "#22262f"),
        (QPalette.ColorRole.Text, "#dde"), (QPalette.ColorRole.Button, "#2a2e38"),
        (QPalette.ColorRole.ButtonText, "#dde"), (QPalette.ColorRole.Highlight, "#3a7bd5"),
        (QPalette.ColorRole.PlaceholderText, "#889"),
    ):
        p.setColor(role, QColor(c))
    app.setPalette(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="D", choices=[k for k, _, _ in VARIANTS])
    ap.add_argument("--screenshot", help="write <prefix>-A.png etc. for every variant and exit")
    args = ap.parse_args()
    app = QApplication(sys.argv)
    dark(app)
    w = Window(args.variant)
    w.resize(1280, 640)
    w.show()
    if args.screenshot:
        for i, (key, _, _) in enumerate(VARIANTS):
            w.index = i
            w.render_variant()
            app.processEvents()
            w.grab().save(f"{args.screenshot}-{key}.png")
        return
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
