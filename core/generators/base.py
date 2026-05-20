"""Base code generator with Jinja2 template engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape, Template


@dataclass
class GenerateResult:
    """Result of a code generation run."""
    success: bool
    output_files: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class TemplateEngine:
    """Jinja2 template engine with VCU DevKit conventions."""

    def __init__(self, template_dir: Path):
        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape([]),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        self._register_filters()

    def _register_filters(self):
        """Register custom Jinja2 filters for automotive code generation."""
        self.env.filters["hex"] = lambda v: f"0x{v:X}" if isinstance(v, int) else str(v)
        self.env.filters["hex_padded"] = lambda v, w=4: f"0x{v:0{w}X}" if isinstance(v, int) else str(v)
        self.env.filters["c_identifier"] = self._to_c_identifier
        self.env.filters["upper_snake"] = self._to_upper_snake
        self.env.filters["lower_snake"] = self._to_lower_snake
        self.env.filters["c_literal_suffix"] = self._c_literal_suffix

    @staticmethod
    def _to_c_identifier(name: str) -> str:
        """Convert a name to a valid C identifier."""
        result = []
        for ch in name:
            if ch.isalnum() or ch == "_":
                result.append(ch)
            else:
                result.append("_")
        ident = "".join(result)
        if ident and ident[0].isdigit():
            ident = "_" + ident
        return ident

    @staticmethod
    def _to_upper_snake(name: str) -> str:
        """Convert camelCase/PascalCase to UPPER_SNAKE_CASE."""
        result = []
        for i, ch in enumerate(name):
            if ch.isupper() and i > 0 and name[i - 1].islower():
                result.append("_")
            result.append(ch.upper())
        return "".join(result)

    @staticmethod
    def _to_lower_snake(name: str) -> str:
        """Convert camelCase/PascalCase to lower_snake_case."""
        result = []
        for i, ch in enumerate(name):
            if ch.isupper() and i > 0 and name[i - 1].islower():
                result.append("_")
            result.append(ch.lower())
        return "".join(result)

    @staticmethod
    def _c_literal_suffix(value: float) -> str:
        """Format a float as a C literal with appropriate suffix."""
        try:
            if value == int(value):
                return f"{int(value)}f"
        except (OverflowError, ValueError):
            pass
        return f"{value}f"

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template with the given context."""
        template = self.env.get_template(template_name)
        return template.render(**context)

    def render_string(self, template_str: str, context: dict[str, Any]) -> str:
        """Render a template string (not from file)."""
        template = self.env.from_string(template_str)
        return template.render(**context)

    def get_template(self, template_name: str) -> Template:
        """Get a raw Jinja2 Template object."""
        return self.env.get_template(template_name)

    def list_templates(self) -> list[str]:
        """List all available templates."""
        return self.env.list_templates()


class BaseGenerator(ABC):
    """Abstract base for code generators."""

    def __init__(self, template_dir: Path):
        self.engine = TemplateEngine(template_dir)

    @abstractmethod
    def generate(self, data: Any, output_dir: Path) -> GenerateResult:
        """Generate code files from data."""
        ...

    def _write_file(self, path: Path, content: str) -> Path:
        """Write content to file, creating directories as needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _write_bytes(self, path: Path, content: bytes) -> Path:
        """Write binary content to file, creating directories as needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path
