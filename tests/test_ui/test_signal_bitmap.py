"""Tests for ui.widgets.signal_bitmap — CAN signal bit-level visualization."""

import pytest

from core.parsers.dbc_parser import SignalDef
from ui.widgets.signal_bitmap import _PALETTE, SignalBitmapWidget


def _make_signal(
    name, start_bit, bit_length, byte_order="little_endian", factor=1.0, offset=0.0, minimum=0.0, maximum=0.0, unit=""
):
    return SignalDef(
        name=name,
        start_bit=start_bit,
        bit_length=bit_length,
        byte_order=byte_order,
        factor=factor,
        offset=offset,
        minimum=minimum,
        maximum=maximum,
        unit=unit,
        value_type="unsigned",
        comment="",
        receivers=[],
    )


@pytest.fixture
def bitmap(qtbot):
    w = SignalBitmapWidget(dlc=8)
    qtbot.addWidget(w)
    return w


class TestBitmapCreation:
    def test_create_default(self, qtbot):
        w = SignalBitmapWidget()
        qtbot.addWidget(w)
        assert w.dlc == 8
        assert w._signals == []

    def test_create_custom_dlc(self, qtbot):
        w = SignalBitmapWidget(dlc=4)
        qtbot.addWidget(w)
        assert w.dlc == 4

    def test_initial_state(self, bitmap):
        assert bitmap._hovered_signal is None
        assert bitmap._selected_signal is None
        assert bitmap._bit_owner == {}
        assert bitmap._signal_colors == {}


class TestBitmapSetSignals:
    def test_set_signals_populates_bit_owner(self, bitmap):
        sig = _make_signal("Speed", start_bit=0, bit_length=8)
        bitmap.set_signals([sig], dlc=8)
        # bit 0-7 should be owned by "Speed"
        for i in range(8):
            assert bitmap._bit_owner[i] == "Speed"

    def test_set_signals_clears_previous(self, bitmap):
        sig1 = _make_signal("Old", start_bit=0, bit_length=8)
        bitmap.set_signals([sig1])
        sig2 = _make_signal("New", start_bit=0, bit_length=8)
        bitmap.set_signals([sig2])
        assert bitmap._bit_owner[0] == "New"
        assert "Old" not in bitmap._bit_owner.values()

    def test_set_signals_assigns_colors(self, bitmap):
        sig1 = _make_signal("A", start_bit=0, bit_length=4)
        sig2 = _make_signal("B", start_bit=4, bit_length=4)
        bitmap.set_signals([sig1, sig2])
        assert "A" in bitmap._signal_colors
        assert "B" in bitmap._signal_colors
        assert bitmap._signal_colors["A"] != bitmap._signal_colors["B"]

    def test_same_name_same_color(self, bitmap):
        sig1 = _make_signal("Speed", start_bit=0, bit_length=4)
        sig2 = _make_signal("Speed", start_bit=8, bit_length=4)
        bitmap.set_signals([sig1, sig2])
        colors = [v for k, v in bitmap._signal_colors.items() if k == "Speed"]
        assert len(colors) == 1


class TestBitmapBitLayout:
    def test_little_endian_bits(self, bitmap):
        sig = _make_signal("S1", start_bit=0, bit_length=4, byte_order="little_endian")
        bits = bitmap._get_signal_bits(sig)
        assert bits == [0, 1, 2, 3]

    def test_little_endian_offset(self, bitmap):
        sig = _make_signal("S1", start_bit=8, bit_length=3, byte_order="little_endian")
        bits = bitmap._get_signal_bits(sig)
        assert bits == [8, 9, 10]

    def test_big_endian_bits(self, bitmap):
        # Motorola: start_bit=7 means byte0 bit7, then 6,5,4,...
        sig = _make_signal("S1", start_bit=7, bit_length=4, byte_order="big_endian")
        bits = bitmap._get_signal_bits(sig)
        assert bits == [7, 6, 5, 4]

    def test_big_endian_cross_byte(self, bitmap):
        # start_bit=15 → byte1 bit7, then byte1 bit6,5,... then byte2 bit7
        sig = _make_signal("S1", start_bit=15, bit_length=4, byte_order="big_endian")
        bits = bitmap._get_signal_bits(sig)
        assert bits == [15, 14, 13, 12]

    def test_big_endian_byte_boundary(self, bitmap):
        # start_bit=15 → byte1 bit7 → 15, 14, 13, 12, 11, 10, 9, 8 → then byte2 bit7=23
        sig = _make_signal("S1", start_bit=15, bit_length=9, byte_order="big_endian")
        bits = bitmap._get_signal_bits(sig)
        assert bits[0] == 15
        assert bits[-1] == 23  # crossed into byte2

    def test_bits_within_dlc(self, bitmap):
        # Signal extending beyond DLC should not be added
        sig = _make_signal("Overflow", start_bit=56, bit_length=16)
        bitmap.set_signals([sig], dlc=8)  # 64 bits total
        # bits 56-63 should be set, but 64+ are out of range
        for i in range(56, 64):
            assert bitmap._bit_owner.get(i) == "Overflow"
        assert bitmap._bit_owner.get(64) is None

    def test_multiple_signals_no_overlap(self, bitmap):
        sig1 = _make_signal("A", start_bit=0, bit_length=4)
        sig2 = _make_signal("B", start_bit=4, bit_length=4)
        bitmap.set_signals([sig1, sig2])
        for i in range(4):
            assert bitmap._bit_owner[i] == "A"
        for i in range(4, 8):
            assert bitmap._bit_owner[i] == "B"

    def test_overlapping_signals_last_wins(self, bitmap):
        sig1 = _make_signal("First", start_bit=0, bit_length=8)
        sig2 = _make_signal("Second", start_bit=0, bit_length=8)
        bitmap.set_signals([sig1, sig2])
        for i in range(8):
            assert bitmap._bit_owner[i] == "Second"


class TestBitmapInteraction:
    def test_set_selected_signal(self, bitmap):
        sig = _make_signal("Speed", start_bit=0, bit_length=8)
        bitmap.set_signals([sig])
        bitmap.set_selected_signal("Speed")
        assert bitmap._selected_signal == "Speed"

    def test_set_selected_none(self, bitmap):
        bitmap.set_selected_signal(None)
        assert bitmap._selected_signal is None

    def test_signal_selected_emission(self, bitmap, qtbot):
        sig = _make_signal("Speed", start_bit=0, bit_length=8)
        bitmap.set_signals([sig])
        with qtbot.waitSignal(bitmap.signal_selected, timeout=1000) as blocker:
            bitmap.signal_selected.emit("Speed")
        assert blocker.args == ["Speed"]

    def test_pos_to_bit_valid(self, bitmap):
        # Click at (label_w + 0.5*cell, header_h + 0.5*cell) → bit 0
        x = bitmap._label_w + bitmap._cell_size // 2
        y = bitmap._header_h + bitmap._cell_size // 2
        bit = bitmap._pos_to_bit(x, y)
        assert bit == 0

    def test_pos_to_bit_outside(self, bitmap):
        bit = bitmap._pos_to_bit(0, 0)
        assert bit is None

    def test_pos_to_bit_last_cell(self, bitmap):
        x = bitmap._label_w + 7 * bitmap._cell_size + bitmap._cell_size // 2
        y = bitmap._header_h + 7 * bitmap._cell_size + bitmap._cell_size // 2
        bit = bitmap._pos_to_bit(x, y)
        assert bit == 63


class TestBitmapPalette:
    def test_palette_has_colors(self):
        assert len(_PALETTE) >= 12

    def test_palette_colors_unique(self):
        names = [c.name() for c in _PALETTE]
        assert len(names) == len(set(names))


class TestBitmapPaint:
    def test_paint_no_crash(self, bitmap):
        """Painting with no signals should not crash."""
        bitmap.update()
        bitmap.repaint()

    def test_paint_with_signals(self, bitmap):
        sig1 = _make_signal("Speed", start_bit=0, bit_length=8)
        sig2 = _make_signal("Torque", start_bit=8, bit_length=16)
        bitmap.set_signals([sig1, sig2])
        bitmap.repaint()

    def test_paint_with_selection(self, bitmap):
        sig = _make_signal("Speed", start_bit=0, bit_length=8)
        bitmap.set_signals([sig])
        bitmap.set_selected_signal("Speed")
        bitmap.repaint()

    def test_paint_with_hover(self, bitmap):
        sig = _make_signal("Speed", start_bit=0, bit_length=8)
        bitmap.set_signals([sig])
        bitmap._hovered_signal = "Speed"
        bitmap.repaint()

    def test_paint_custom_dlc(self, qtbot):
        w = SignalBitmapWidget(dlc=4)
        qtbot.addWidget(w)
        sig = _make_signal("S1", start_bit=0, bit_length=16)
        w.set_signals([sig], dlc=4)
        w.repaint()
