"""Base classes for VCU DevKit plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.generators.base import BaseGenerator
from core.parsers.base import BaseParser
from core.rules.engine import RuleResult


@dataclass
class PluginMeta:
    """Metadata describing a plugin."""

    name: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""


class ParserPlugin(BaseParser, ABC):
    """Base class for parser plugins.

    Subclasses must implement:
        - plugin_meta (property or class attribute)
        - supported_extensions()
        - parse()
        - validate()
    """

    @property
    @abstractmethod
    def plugin_meta(self) -> PluginMeta: ...


class GeneratorPlugin(BaseGenerator, ABC):
    """Base class for generator plugins.

    Subclasses must implement:
        - plugin_meta (property or class attribute)
        - generate()
    """

    def __init__(self, template_dir: Path | None = None):
        # Generator plugins may not need templates
        if template_dir is not None:
            super().__init__(template_dir)

    @property
    @abstractmethod
    def plugin_meta(self) -> PluginMeta: ...


class RulePlugin(ABC):
    """Base class for validation rule plugins.

    Subclasses must implement:
        - plugin_meta (property or class attribute)
        - at least one of check_dbc() or check_arxml()
    """

    @property
    @abstractmethod
    def plugin_meta(self) -> PluginMeta: ...

    def check_dbc(self, data: Any) -> list[RuleResult]:
        """Run DBC validation rules. Override to add custom rules."""
        return []

    def check_arxml(self, data: Any) -> list[RuleResult]:
        """Run ARXML validation rules. Override to add custom rules."""
        return []
