"""Tests for core.commands.command — undo/redo framework."""

import pytest
from core.commands.command import (
    Command, UpdateFieldCommand, BatchUpdateCommand,
    AddItemCommand, RemoveItemCommand, CompoundCommand, CommandHistory,
)


class DummyObj:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ── UpdateFieldCommand ────────────────────────────────────────────────────────

class TestUpdateFieldCommand:

    def test_execute_sets_field(self):
        obj = DummyObj(x=1)
        cmd = UpdateFieldCommand(obj, "x", 2)
        cmd.execute()
        assert obj.x == 2

    def test_undo_restores_field(self):
        obj = DummyObj(x=1)
        cmd = UpdateFieldCommand(obj, "x", 2)
        cmd.execute()
        cmd.undo()
        assert obj.x == 1

    def test_description(self):
        obj = DummyObj(x=1)
        cmd = UpdateFieldCommand(obj, "x", 2)
        assert "x" in cmd.description

    def test_new_field(self):
        obj = DummyObj()
        cmd = UpdateFieldCommand(obj, "new_field", 42)
        cmd.execute()
        assert obj.new_field == 42
        cmd.undo()
        assert getattr(obj, "new_field", None) is None


# ── BatchUpdateCommand ────────────────────────────────────────────────────────

class TestBatchUpdateCommand:

    def test_execute_sets_multiple_fields(self):
        obj = DummyObj(a=1, b=2)
        cmd = BatchUpdateCommand(obj, {"a": 10, "b": 20})
        cmd.execute()
        assert obj.a == 10
        assert obj.b == 20

    def test_undo_restores_all(self):
        obj = DummyObj(a=1, b=2)
        cmd = BatchUpdateCommand(obj, {"a": 10, "b": 20})
        cmd.execute()
        cmd.undo()
        assert obj.a == 1
        assert obj.b == 2

    def test_description(self):
        obj = DummyObj(a=1, b=2)
        cmd = BatchUpdateCommand(obj, {"a": 10, "b": 20})
        assert "a" in cmd.description and "b" in cmd.description


# ── AddItemCommand / RemoveItemCommand ────────────────────────────────────────

class TestAddItemCommand:

    def test_add_to_end(self):
        lst = [1, 2]
        cmd = AddItemCommand(lst, 3)
        cmd.execute()
        assert lst == [1, 2, 3]

    def test_add_at_index(self):
        lst = [1, 3]
        cmd = AddItemCommand(lst, 2, index=1)
        cmd.execute()
        assert lst == [1, 2, 3]

    def test_undo_removes_item(self):
        lst = [1, 2]
        cmd = AddItemCommand(lst, 3)
        cmd.execute()
        cmd.undo()
        assert lst == [1, 2]


class TestRemoveItemCommand:

    def test_remove(self):
        lst = [1, 2, 3]
        cmd = RemoveItemCommand(lst, 1)
        cmd.execute()
        assert lst == [1, 3]

    def test_undo_restores(self):
        lst = [1, 2, 3]
        cmd = RemoveItemCommand(lst, 1)
        cmd.execute()
        cmd.undo()
        assert lst == [1, 2, 3]

    def test_out_of_range_noop(self):
        lst = [1]
        cmd = RemoveItemCommand(lst, 5)
        cmd.execute()
        assert lst == [1]


# ── CompoundCommand ───────────────────────────────────────────────────────────

class TestCompoundCommand:

    def test_execute_runs_all(self):
        obj = DummyObj(a=1, b=2)
        cmds = [
            UpdateFieldCommand(obj, "a", 10),
            UpdateFieldCommand(obj, "b", 20),
        ]
        compound = CompoundCommand(cmds, "batch edit")
        compound.execute()
        assert obj.a == 10
        assert obj.b == 20
        assert compound.description == "batch edit"

    def test_undo_reverses_all(self):
        obj = DummyObj(a=1, b=2)
        cmds = [
            UpdateFieldCommand(obj, "a", 10),
            UpdateFieldCommand(obj, "b", 20),
        ]
        compound = CompoundCommand(cmds)
        compound.execute()
        compound.undo()
        assert obj.a == 1
        assert obj.b == 2

    def test_undo_order_reversed(self):
        log = []
        class LoggingCmd(Command):
            def __init__(self, name):
                self.name = name
            def execute(self):
                log.append(f"exec-{self.name}")
            def undo(self):
                log.append(f"undo-{self.name}")

        compound = CompoundCommand([LoggingCmd("A"), LoggingCmd("B")])
        compound.execute()
        compound.undo()
        assert log == ["exec-A", "exec-B", "undo-B", "undo-A"]

    def test_default_description(self):
        compound = CompoundCommand([UpdateFieldCommand(DummyObj(x=1), "x", 2)])
        assert "1 action" in compound.description


# ── CommandHistory ────────────────────────────────────────────────────────────

class TestCommandHistory:

    def test_execute_pushes_to_undo(self):
        history = CommandHistory()
        obj = DummyObj(x=1)
        history.execute(UpdateFieldCommand(obj, "x", 2))
        assert history.can_undo()
        assert not history.can_redo()

    def test_undo_moves_to_redo(self):
        history = CommandHistory()
        obj = DummyObj(x=1)
        history.execute(UpdateFieldCommand(obj, "x", 2))
        assert history.undo()
        assert obj.x == 1
        assert history.can_redo()

    def test_redo_reapplies(self):
        history = CommandHistory()
        obj = DummyObj(x=1)
        history.execute(UpdateFieldCommand(obj, "x", 2))
        history.undo()
        assert history.redo()
        assert obj.x == 2

    def test_undo_empty_returns_false(self):
        history = CommandHistory()
        assert not history.undo()

    def test_redo_empty_returns_false(self):
        history = CommandHistory()
        assert not history.redo()

    def test_new_execute_clears_redo(self):
        history = CommandHistory()
        obj = DummyObj(x=1)
        history.execute(UpdateFieldCommand(obj, "x", 2))
        history.undo()
        assert history.can_redo()
        history.execute(UpdateFieldCommand(obj, "x", 3))
        assert not history.can_redo()

    def test_max_history_trims(self):
        history = CommandHistory(max_history=3)
        obj = DummyObj(x=0)
        for i in range(5):
            history.execute(UpdateFieldCommand(obj, "x", i))
        # Only last 3 should be undoable
        assert history.undo()
        assert history.undo()
        assert history.undo()
        assert not history.undo()

    def test_clear(self):
        history = CommandHistory()
        obj = DummyObj(x=1)
        history.execute(UpdateFieldCommand(obj, "x", 2))
        history.clear()
        assert not history.can_undo()
        assert not history.can_redo()

    def test_undo_redo_descriptions(self):
        history = CommandHistory()
        obj = DummyObj(x=1)
        history.execute(UpdateFieldCommand(obj, "x", 2))
        assert history.undo_description is not None
        history.undo()
        assert history.redo_description is not None

    def test_empty_descriptions(self):
        history = CommandHistory()
        assert history.undo_description is None
        assert history.redo_description is None
