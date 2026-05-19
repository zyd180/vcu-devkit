"""Generic CRUD mixin for peewee model controllers."""

from __future__ import annotations

import logging
from typing import Any

from peewee import Model

logger = logging.getLogger(__name__)


class CRUDMixin:
    """Provides generic get/update/delete for a peewee model.

    Subclasses must set ``model`` to a peewee Model class.
    """

    model: type[Model] | None = None

    def get_by_id(self, obj_id: int) -> Model | None:
        """Fetch a single record by primary key, or None."""
        if self.model is None:
            return None
        try:
            return self.model.get_by_id(obj_id)
        except self.model.DoesNotExist:
            return None

    def update_fields(self, obj_id: int, **kwargs: Any) -> bool:
        """Update fields on a record. Returns True on success."""
        obj = self.get_by_id(obj_id)
        if obj is None:
            return False
        for key, value in kwargs.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        obj.save()
        return True

    def delete_by_id(self, obj_id: int) -> bool:
        """Delete a record by primary key. Returns True on success."""
        obj = self.get_by_id(obj_id)
        if obj is None:
            return False
        obj.delete_instance()
        return True
