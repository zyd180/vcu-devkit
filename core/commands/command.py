"""Undo/redo command framework using the Command pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Command(ABC):
    """Base command with execute/undo interface."""

    @abstractmethod
    def execute(self) -> Any:
        """Perform the action."""

    @abstractmethod
    def undo(self) -> None:
        """Reverse the action."""

    @property
    def description(self) -> str:
        """Human-readable description for UI display."""
        return self.__class__.__name__


class UpdateFieldCommand(Command):
    """Update a single field on a data object."""

    def __init__(self, obj: Any, field: str, new_value: Any):
        self._obj = obj
        self._field = field
        self._new_value = new_value
        self._old_value = getattr(obj, field, None)

    def execute(self):
        setattr(self._obj, self._field, self._new_value)

    def undo(self):
        setattr(self._obj, self._field, self._old_value)

    @property
    def description(self) -> str:
        return f"Update {self._field}: {self._old_value} → {self._new_value}"


class BatchUpdateCommand(Command):
    """Update multiple fields atomically."""

    def __init__(self, obj: Any, changes: dict[str, Any]):
        self._obj = obj
        self._changes = changes
        self._old_values: dict[str, Any] = {}

    def execute(self):
        for field, new_val in self._changes.items():
            self._old_values[field] = getattr(self._obj, field, None)
            setattr(self._obj, field, new_val)

    def undo(self):
        for field, old_val in self._old_values.items():
            setattr(self._obj, field, old_val)

    @property
    def description(self) -> str:
        fields = ", ".join(self._changes.keys())
        return f"Batch update: {fields}"


class AddItemCommand(Command):
    """Add an item to a list."""

    def __init__(self, lst: list, item: Any, index: int = -1):
        self._list = lst
        self._item = item
        self._index = index

    def execute(self):
        if self._index < 0:
            self._list.append(self._item)
            self._index = len(self._list) - 1
        else:
            self._list.insert(self._index, self._item)

    def undo(self):
        if 0 <= self._index < len(self._list):
            self._list.pop(self._index)

    @property
    def description(self) -> str:
        return f"Add item at index {self._index}"


class RemoveItemCommand(Command):
    """Remove an item from a list by index."""

    def __init__(self, lst: list, index: int):
        self._list = lst
        self._index = index
        self._item: Any = None

    def execute(self):
        if 0 <= self._index < len(self._list):
            self._item = self._list.pop(self._index)

    def undo(self):
        if self._item is not None:
            self._list.insert(self._index, self._item)

    @property
    def description(self) -> str:
        return f"Remove item at index {self._index}"


class CompoundCommand(Command):
    """Group multiple commands into a single undoable action."""

    def __init__(self, commands: list[Command], description: str = ""):
        self._commands = commands
        self._desc = description

    def execute(self):
        for cmd in self._commands:
            cmd.execute()

    def undo(self):
        for cmd in reversed(self._commands):
            cmd.undo()

    @property
    def description(self) -> str:
        return self._desc or f"Compound ({len(self._commands)} actions)"


class CommandHistory:
    """Manages undo/redo stacks."""

    def __init__(self, max_history: int = 100):
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []
        self._max_history = max_history

    def execute(self, command: Command) -> Any:
        """Execute a command and push it onto the undo stack."""
        result = command.execute()
        self._undo_stack.append(command)
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        return result

    def undo(self) -> bool:
        """Undo the last command. Returns True if successful."""
        if not self._undo_stack:
            return False
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        return True

    def redo(self) -> bool:
        """Redo the last undone command. Returns True if successful."""
        if not self._redo_stack:
            return False
        cmd = self._redo_stack.pop()
        cmd.execute()
        self._undo_stack.append(cmd)
        return True

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()

    @property
    def undo_description(self) -> str | None:
        return self._undo_stack[-1].description if self._undo_stack else None

    @property
    def redo_description(self) -> str | None:
        return self._redo_stack[-1].description if self._redo_stack else None
