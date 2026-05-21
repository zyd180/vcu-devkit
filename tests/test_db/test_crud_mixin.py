"""Tests for core.db.crud_mixin — generic CRUD operations."""

import pytest
from peewee import CharField, IntegerField, Model, SqliteDatabase

from core.db.crud_mixin import CRUDMixin

# In-memory test model
test_db = SqliteDatabase(":memory:")


class TestModel(Model):
    name = CharField()
    value = IntegerField(default=0)

    class Meta:
        database = test_db
        table_name = "test_model"


class TestCRUD(CRUDMixin):
    model = TestModel


@pytest.fixture(autouse=True)
def setup_db():
    test_db.bind([TestModel])
    test_db.create_tables([TestModel])
    yield
    test_db.drop_tables([TestModel])
    test_db.close()


class TestCRUDMixin:
    def test_get_by_id(self):
        obj = TestModel.create(name="test", value=42)
        result = TestCRUD().get_by_id(obj.id)
        assert result is not None
        assert result.name == "test"

    def test_get_by_id_not_found(self):
        result = TestCRUD().get_by_id(99999)
        assert result is None

    def test_get_by_id_no_model(self):
        class NoModel(CRUDMixin):
            model = None

        assert NoModel().get_by_id(1) is None

    def test_update_fields(self):
        obj = TestModel.create(name="old", value=1)
        crud = TestCRUD()
        assert crud.update_fields(obj.id, name="new", value=2)
        updated = TestModel.get_by_id(obj.id)
        assert updated.name == "new"
        assert updated.value == 2

    def test_update_fields_not_found(self):
        assert not TestCRUD().update_fields(99999, name="x")

    def test_update_fields_ignores_unknown(self):
        obj = TestModel.create(name="test", value=1)
        crud = TestCRUD()
        # Should not raise even with unknown field
        assert crud.update_fields(obj.id, name="new", unknown_field="ignored")

    def test_delete_by_id(self):
        obj = TestModel.create(name="test", value=1)
        assert TestCRUD().delete_by_id(obj.id)
        assert TestModel.get_or_none(TestModel.id == obj.id) is None

    def test_delete_by_id_not_found(self):
        assert not TestCRUD().delete_by_id(99999)
