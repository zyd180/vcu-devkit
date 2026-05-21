"""Plugin discovery and registration."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from core.plugins.base import (
    GeneratorPlugin,
    ParserPlugin,
    RulePlugin,
)

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Central registry for all VCU DevKit plugins."""

    def __init__(self):
        self.parsers: dict[str, ParserPlugin] = {}  # ext → plugin
        self.generators: dict[str, GeneratorPlugin] = {}  # name → plugin
        self.rules: list[RulePlugin] = []
        self._discovered_modules: list[Any] = []

    # ── Discovery ─────────────────────────────────────────────────────────

    def discover(self, plugin_dirs: list[Path]) -> int:
        """Scan directories for plugin .py files and register them.

        Returns the number of plugins registered.
        """
        count = 0
        for d in plugin_dirs:
            d = Path(d)
            if not d.is_dir():
                logger.debug("Plugin directory not found: %s", d)
                continue
            for py_file in sorted(d.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                try:
                    n = self._load_module(py_file)
                    count += n
                except Exception:
                    logger.exception("Failed to load plugin: %s", py_file)
        return count

    def _load_module(self, py_file: Path) -> int:
        """Import a .py file and register any plugin classes found."""
        module_name = f"vcu_plugin_{py_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, str(py_file))
        if spec is None or spec.loader is None:
            return 0
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        self._discovered_modules.append(module)

        count = 0
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if not isinstance(attr, type):
                continue
            if issubclass(attr, ParserPlugin) and attr is not ParserPlugin:
                try:
                    plugin = attr()
                    self.register_parser(plugin)
                    count += 1
                except Exception:
                    logger.exception("Failed to instantiate parser plugin: %s", attr_name)
            elif issubclass(attr, GeneratorPlugin) and attr is not GeneratorPlugin:
                try:
                    plugin = attr()
                    self.register_generator(plugin)
                    count += 1
                except Exception:
                    logger.exception("Failed to instantiate generator plugin: %s", attr_name)
            elif issubclass(attr, RulePlugin) and attr is not RulePlugin:
                try:
                    plugin = attr()
                    self.register_rule(plugin)
                    count += 1
                except Exception:
                    logger.exception("Failed to instantiate rule plugin: %s", attr_name)
        return count

    # ── Registration ──────────────────────────────────────────────────────

    def register_parser(self, plugin: ParserPlugin) -> None:
        """Register a parser plugin for its supported extensions."""
        for ext in plugin.supported_extensions():
            existing = self.parsers.get(ext)
            if existing is not None:
                logger.warning(
                    "Parser plugin '%s' overrides '%s' for extension '%s'",
                    plugin.plugin_meta.name,
                    existing.plugin_meta.name,
                    ext,
                )
            self.parsers[ext] = plugin
            logger.info("Registered parser '%s' for %s", plugin.plugin_meta.name, ext)

    def register_generator(self, plugin: GeneratorPlugin) -> None:
        """Register a generator plugin by name."""
        name = plugin.plugin_meta.name
        if name in self.generators:
            logger.warning("Generator plugin '%s' already registered, overriding", name)
        self.generators[name] = plugin
        logger.info("Registered generator '%s'", name)

    def register_rule(self, plugin: RulePlugin) -> None:
        """Register a rule plugin."""
        self.rules.append(plugin)
        logger.info("Registered rule plugin '%s'", plugin.plugin_meta.name)

    # ── Lookup ────────────────────────────────────────────────────────────

    def get_parser(self, ext: str) -> ParserPlugin | None:
        """Get a parser plugin by file extension (e.g. '.dbc')."""
        return self.parsers.get(ext)

    def get_generator(self, name: str) -> GeneratorPlugin | None:
        """Get a generator plugin by name."""
        return self.generators.get(name)

    def get_all_parsers(self) -> list[ParserPlugin]:
        """Return all registered parser plugins."""
        return list(self.parsers.values())

    def get_all_generators(self) -> list[GeneratorPlugin]:
        """Return all registered generator plugins."""
        return list(self.generators.values())

    def get_all_rules(self) -> list[RulePlugin]:
        """Return all registered rule plugins."""
        return list(self.rules)

    # ── Query ─────────────────────────────────────────────────────────────

    def supported_extensions(self) -> list[str]:
        """Return all file extensions supported by registered parsers."""
        return sorted(self.parsers.keys())

    def generator_names(self) -> list[str]:
        """Return all registered generator names."""
        return sorted(self.generators.keys())
