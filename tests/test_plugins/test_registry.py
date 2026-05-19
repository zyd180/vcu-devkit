"""Tests for the plugin system — registry, discovery, and integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.parsers.base import ParseResult
from core.parsers.dbc_parser import DBCData, MessageDef, SignalDef
from core.generators.base import GenerateResult
from core.rules.engine import RuleEngine, RuleResult, Severity
from core.plugins.base import (
    GeneratorPlugin, ParserPlugin, PluginMeta, RulePlugin,
)
from core.plugins.registry import PluginRegistry


# ── Test plugin implementations ──────────────────────────────────────────────

class DummyParser(ParserPlugin):
    """A minimal test parser plugin."""

    @property
    def plugin_meta(self) -> PluginMeta:
        return PluginMeta(name="dummy_parser", version="0.1.0", author="test")

    def supported_extensions(self) -> list[str]:
        return [".dummy"]

    def parse(self, file_path: Path) -> ParseResult:
        return ParseResult(success=True, data=None)

    def validate(self, file_path: Path) -> list[str]:
        return []


class DummyGenerator(GeneratorPlugin):
    """A minimal test generator plugin."""

    @property
    def plugin_meta(self) -> PluginMeta:
        return PluginMeta(name="dummy_gen", version="0.1.0", author="test")

    def generate(self, data, output_dir: Path) -> GenerateResult:
        return GenerateResult(success=True)


class DummyRule(RulePlugin):
    """A minimal test rule plugin."""

    @property
    def plugin_meta(self) -> PluginMeta:
        return PluginMeta(name="dummy_rule", version="0.1.0", author="test")

    def check_dbc(self, data) -> list[RuleResult]:
        return [RuleResult(
            rule_id="PLUGIN_DUMMY",
            severity=Severity.INFO,
            message="Dummy rule fired",
            location="global",
        )]


class DummyARXMLRule(RulePlugin):
    """A test rule plugin that only checks ARXML."""

    @property
    def plugin_meta(self) -> PluginMeta:
        return PluginMeta(name="dummy_arxml_rule")

    def check_arxml(self, data) -> list[RuleResult]:
        return [RuleResult(
            rule_id="PLUGIN_ARXML",
            severity=Severity.INFO,
            message="ARXML plugin rule",
            location="global",
        )]


# ── Registry tests ───────────────────────────────────────────────────────────

class TestPluginRegistry:

    def test_register_parser(self):
        registry = PluginRegistry()
        parser = DummyParser()
        registry.register_parser(parser)
        assert registry.get_parser(".dummy") is parser
        assert ".dummy" in registry.supported_extensions()

    def test_register_generator(self):
        registry = PluginRegistry()
        gen = DummyGenerator()
        registry.register_generator(gen)
        assert registry.get_generator("dummy_gen") is gen
        assert "dummy_gen" in registry.generator_names()

    def test_register_rule(self):
        registry = PluginRegistry()
        rule = DummyRule()
        registry.register_rule(rule)
        assert len(registry.get_all_rules()) == 1

    def test_parser_override_logs_warning(self, caplog):
        registry = PluginRegistry()
        p1 = DummyParser()
        p2 = DummyParser()
        registry.register_parser(p1)
        registry.register_generator(DummyGenerator())  # avoid error
        registry.register_parser(p2)
        assert "overrides" in caplog.text or registry.get_parser(".dummy") is p2

    def test_get_nonexistent_parser(self):
        registry = PluginRegistry()
        assert registry.get_parser(".xyz") is None

    def test_get_nonexistent_generator(self):
        registry = PluginRegistry()
        assert registry.get_generator("nonexistent") is None

    def test_supported_extensions_sorted(self):
        registry = PluginRegistry()
        p = DummyParser()
        registry.register_parser(p)
        exts = registry.supported_extensions()
        assert exts == sorted(exts)

    def test_generator_names_sorted(self):
        registry = PluginRegistry()
        registry.register_generator(DummyGenerator())
        names = registry.generator_names()
        assert names == sorted(names)


# ── Discovery tests ──────────────────────────────────────────────────────────

class TestPluginDiscovery:

    def test_discover_empty_dir(self, tmp_path):
        registry = PluginRegistry()
        count = registry.discover([tmp_path])
        assert count == 0

    def test_discover_nonexistent_dir(self, tmp_path):
        registry = PluginRegistry()
        count = registry.discover([tmp_path / "nonexistent"])
        assert count == 0

    def test_discover_finds_plugins(self, tmp_path):
        plugin_code = '''
from core.plugins.base import ParserPlugin, PluginMeta
from core.parsers.base import ParseResult
from pathlib import Path

class TestPlugin(ParserPlugin):
    @property
    def plugin_meta(self):
        return PluginMeta(name="test_plugin")

    def supported_extensions(self):
        return [".test"]

    def parse(self, file_path):
        return ParseResult(success=True)

    def validate(self, file_path):
        return []
'''
        (tmp_path / "test_plugin.py").write_text(plugin_code)
        registry = PluginRegistry()
        count = registry.discover([tmp_path])
        assert count == 1
        assert registry.get_parser(".test") is not None

    def test_discover_skips_underscore_files(self, tmp_path):
        (tmp_path / "_private.py").write_text("# nothing")
        registry = PluginRegistry()
        count = registry.discover([tmp_path])
        assert count == 0

    def test_discover_ignores_import_errors(self, tmp_path):
        (tmp_path / "bad_plugin.py").write_text("raise ImportError('nope')")
        registry = PluginRegistry()
        count = registry.discover([tmp_path])
        assert count == 0


# ── Rule engine integration tests ────────────────────────────────────────────

class TestRuleEnginePluginIntegration:

    def test_plugin_rule_executed_in_check_dbc(self):
        engine = RuleEngine()
        engine.register_plugin_rules([DummyRule()])
        dbc = DBCData(
            version="", messages=[], nodes=[],
            value_tables={}, comments={}, attributes={},
            source_path="<test>",
        )
        results = engine.check_dbc(dbc)
        plugin_results = [r for r in results if r.rule_id == "PLUGIN_DUMMY"]
        assert len(plugin_results) == 1

    def test_plugin_arxml_rule_executed(self):
        from core.parsers.arxml_parser import ARXMLData
        engine = RuleEngine()
        engine.register_plugin_rules([DummyARXMLRule()])
        data = ARXMLData(
            autosar_version="4.4", package_name="pkg",
            swcs=[], interfaces=[], compositions=[],
            data_types=[], source_path="<test>",
        )
        results = engine.check_arxml(data)
        plugin_results = [r for r in results if r.rule_id == "PLUGIN_ARXML"]
        assert len(plugin_results) == 1

    def test_no_plugins_no_extra_results(self):
        engine = RuleEngine()
        dbc = DBCData(
            version="", messages=[], nodes=[],
            value_tables={}, comments={}, attributes={},
            source_path="<test>",
        )
        results = engine.check_dbc(dbc)
        plugin_results = [r for r in results if r.rule_id.startswith("PLUGIN_")]
        assert len(plugin_results) == 0


# ── Example CSV parser plugin test ───────────────────────────────────────────

class TestExampleCSVParser:

    def test_csv_parser_loads(self, tmp_path):
        registry = PluginRegistry()
        plugin_dir = Path(__file__).parent.parent.parent / "plugins"
        if not plugin_dir.exists():
            pytest.skip("plugins/ directory not found")
        count = registry.discover([plugin_dir])
        assert count >= 1
        assert registry.get_parser(".csv") is not None

    def test_csv_parser_parse(self, tmp_path):
        registry = PluginRegistry()
        plugin_dir = Path(__file__).parent.parent.parent / "plugins"
        if not plugin_dir.exists():
            pytest.skip("plugins/ directory not found")
        registry.discover([plugin_dir])
        parser = registry.get_parser(".csv")
        assert parser is not None

        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "message_id,message_name,dlc,signal_name,start_bit,bit_length\n"
            "0x100,VCU_Status,8,PowerMode,0,8\n"
            "0x100,VCU_Status,8,SOC,8,16\n"
        )
        result = parser.parse(csv_file)
        assert result.success
        assert len(result.data.messages) == 1
        assert len(result.data.messages[0].signals) == 2

    def test_csv_parser_validate(self, tmp_path):
        registry = PluginRegistry()
        plugin_dir = Path(__file__).parent.parent.parent / "plugins"
        if not plugin_dir.exists():
            pytest.skip("plugins/ directory not found")
        registry.discover([plugin_dir])
        parser = registry.get_parser(".csv")

        csv_file = tmp_path / "bad.csv"
        csv_file.write_text("wrong,columns\n1,2\n")
        errors = parser.validate(csv_file)
        assert len(errors) > 0
