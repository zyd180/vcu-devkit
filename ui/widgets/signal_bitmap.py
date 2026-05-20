"""Signal bitmap widget — 8×8 bit-level visualization of CAN frame."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QToolTip
from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QMouseEvent, QPaintEvent

from core.parsers.dbc_parser import SignalDef

# Distinct colors for signals
_PALETTE = [
    QColor("#4CAF50"),  # green
    QColor("#2196F3"),  # blue
    QColor("#FF9800"),  # orange
    QColor("#9C27B0"),  # purple
    QColor("#F44336"),  # red
    QColor("#00BCD4"),  # cyan
    QColor("#795548"),  # brown
    QColor("#607D8B"),  # blue grey
    QColor("#E91E63"),  # pink
    QColor("#3F51B5"),  # indigo
    QColor("#CDDC39"),  # lime
    QColor("#FF5722"),  # deep orange
]


class SignalBitmapWidget(QWidget):
    """Visualize signal bit layout in an 8-byte CAN frame."""

    signal_selected = Signal(str)  # signal name

    def __init__(self, dlc: int = 8, parent=None):
        super().__init__(parent)
        self.dlc = dlc
        self._signals: list[SignalDef] = []
        self._bit_owner: dict[int, str] = {}      # bit_pos → signal name
        self._signal_colors: dict[str, QColor] = {}
        self._hovered_signal: str | None = None
        self._selected_signal: str | None = None
        self._cell_size = 36
        self._header_h = 24
        self._label_w = 48
        self.setMouseTracking(True)
        self.setMinimumHeight(self._header_h + dlc * self._cell_size + 4)
        self.setMinimumWidth(self._label_w + 8 * self._cell_size + 4)

    def set_signals(self, signals: list[SignalDef], dlc: int = 8):
        """Set the signals to display."""
        self.dlc = dlc
        self._signals = signals
        self._bit_owner.clear()
        self._signal_colors.clear()

        color_idx = 0
        for sig in signals:
            if sig.name not in self._signal_colors:
                self._signal_colors[sig.name] = _PALETTE[color_idx % len(_PALETTE)]
                color_idx += 1

            # Map bits based on byte order
            bits = self._get_signal_bits(sig)
            for bit_pos in bits:
                if 0 <= bit_pos < dlc * 8:
                    self._bit_owner[bit_pos] = sig.name

        self.setMinimumHeight(self._header_h + dlc * self._cell_size + 4)
        self.update()

    def set_selected_signal(self, name: str | None):
        self._selected_signal = name
        self.update()

    def _get_signal_bits(self, sig: SignalDef) -> list[int]:
        """Get the physical bit positions occupied by a signal."""
        bits = []
        if sig.byte_order == "little_endian":
            # Intel byte order: start_bit, start_bit+1, ...
            for i in range(sig.bit_length):
                bits.append(sig.start_bit + i)
        else:
            # Motorola byte order
            cur_byte = sig.start_bit // 8
            cur_bit = sig.start_bit % 8
            for _ in range(sig.bit_length):
                bits.append(cur_byte * 8 + cur_bit)
                if cur_bit == 0:
                    cur_byte += 1
                    cur_bit = 7
                else:
                    cur_bit -= 1
        return bits

    def _pos_to_bit(self, x: int, y: int) -> int | None:
        """Convert mouse position to bit index, or None."""
        col = (x - self._label_w) // self._cell_size
        row = (y - self._header_h) // self._cell_size
        if 0 <= col < 8 and 0 <= row < self.dlc:
            return row * 8 + col
        return None

    # ── Painting ──────────────────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        cell = self._cell_size
        x0 = self._label_w
        y0 = self._header_h

        # Column headers (bit 7..0)
        header_font = QFont()
        header_font.setPointSize(8)
        p.setFont(header_font)
        p.setPen(QPen(QColor("#666")))
        for col in range(8):
            rect = QRectF(x0 + col * cell, 0, cell, y0)
            p.drawText(rect, Qt.AlignCenter, str(7 - col))

        # Row headers (byte N)
        for row in range(self.dlc):
            rect = QRectF(0, y0 + row * cell, x0, cell)
            p.drawText(rect, Qt.AlignCenter, f"B{row}")

        # Grid cells
        for row in range(self.dlc):
            for col in range(8):
                bit_pos = row * 8 + col
                rect = QRectF(x0 + col * cell, y0 + row * cell, cell, cell)

                owner = self._bit_owner.get(bit_pos)
                if owner:
                    color = self._signal_colors.get(owner, QColor("#ccc"))
                    if owner == self._selected_signal:
                        # Selected: darker, bold border
                        fill = color.darker(130)
                        p.fillRect(rect, fill)
                        p.setPen(QPen(QColor("#000"), 2))
                    elif owner == self._hovered_signal:
                        # Hovered: lighter
                        fill = color.lighter(130)
                        p.fillRect(rect, fill)
                        p.setPen(QPen(color.darker(150), 1))
                    else:
                        p.fillRect(rect, color)
                        p.setPen(QPen(color.darker(120), 1))
                    p.drawRect(rect)

                    # Signal name (abbreviated) in cell
                    p.setPen(QPen(QColor("#fff")))
                    small_font = QFont()
                    small_font.setPointSize(7)
                    p.setFont(small_font)
                    short = owner[:4]
                    p.drawText(rect, Qt.AlignCenter, short)
                else:
                    p.setPen(QPen(QColor("#ddd")))
                    p.drawRect(rect)

        # Legend
        legend_y = y0 + self.dlc * cell + 4
        legend_font = QFont()
        legend_font.setPointSize(8)
        p.setFont(legend_font)
        lx = x0
        for name, color in self._signal_colors.items():
            p.fillRect(QRectF(lx, legend_y, 12, 12), color)
            p.setPen(QPen(QColor("#333")))
            p.drawText(QRectF(lx + 14, legend_y, 80, 14), Qt.AlignLeft | Qt.AlignVCenter, name)
            lx += len(name) * 7 + 24

        p.end()

    # ── Mouse interaction ─────────────────────────────────────────────────

    def mouseMoveEvent(self, event: QMouseEvent):
        bit = self._pos_to_bit(event.position().x(), event.position().y())
        owner = self._bit_owner.get(bit) if bit is not None else None
        if owner != self._hovered_signal:
            self._hovered_signal = owner
            self.update()
        if owner:
            sig = next((s for s in self._signals if s.name == owner), None)
            if sig:
                tip = (
                    f"{sig.name}\n"
                    f"bit {sig.start_bit}, len {sig.bit_length}, {sig.byte_order}\n"
                    f"factor={sig.factor}, offset={sig.offset}\n"
                    f"range [{sig.minimum}, {sig.maximum}] {sig.unit}"
                )
                QToolTip.showText(event.globalPosition().toPoint(), tip, self)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            bit = self._pos_to_bit(event.position().x(), event.position().y())
            owner = self._bit_owner.get(bit) if bit is not None else None
            self._selected_signal = owner
            if owner:
                self.signal_selected.emit(owner)
            self.update()

    def leaveEvent(self, event):
        self._hovered_signal = None
        self.update()
