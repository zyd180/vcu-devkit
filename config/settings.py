"""Application settings management."""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AppSettings:
    """Application settings."""

    app_name: str = "VCU DevKit"
    version: str = "0.1.0"
    theme: str = "light"
    last_project_dir: str = ""
    last_dbc_dir: str = ""
    last_arxml_dir: str = ""
    recent_files: list[str] = field(default_factory=list)
    max_recent_files: int = 10
    default_arxml_target: str = "davinci"
    auto_save_interval: int = 300
    window_geometry: bytes = b""
    window_state: bytes = b""

    def load(self, config_path: Path | None = None):
        """Load settings from JSON file."""
        if config_path is None:
            config_path = Path.home() / ".vcu-devkit" / "settings.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key, value in data.items():
                    if hasattr(self, key):
                        setattr(self, key, value)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load settings from %s: %s", config_path, exc)

    def save(self, config_path: Path | None = None):
        """Save settings to JSON file."""
        if config_path is None:
            config_path = Path.home() / ".vcu-devkit" / "settings.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "theme": self.theme,
            "last_project_dir": self.last_project_dir,
            "last_dbc_dir": self.last_dbc_dir,
            "last_arxml_dir": self.last_arxml_dir,
            "recent_files": self.recent_files,
            "default_arxml_target": self.default_arxml_target,
            "auto_save_interval": self.auto_save_interval,
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_recent_file(self, file_path: str):
        """Add a file to recent files list."""
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        self.recent_files = self.recent_files[: self.max_recent_files]
