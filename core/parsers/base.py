"""Base classes for file parsers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParseResult:
    """Unified parse result container."""
    success: bool
    data: Any = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_path: Path | None = None


class BaseParser(ABC):
    """Abstract base for all file parsers."""

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """Parse a file and return structured data."""
        ...

    @abstractmethod
    def validate(self, file_path: Path) -> list[str]:
        """Validate file format, return error list."""
        ...

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        ...
