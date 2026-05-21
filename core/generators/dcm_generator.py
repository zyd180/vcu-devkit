"""DCM (Data Calibration Method) file generator.

Generates ASAP2-compatible DCM files from calibration parameter data.
Output can be loaded into ETAS INCA for calibration.
"""

from __future__ import annotations

from pathlib import Path

from core.generators.base import BaseGenerator, GenerateResult


class DCMGenerator(BaseGenerator):
    """Generate DCM calibration data files."""

    def __init__(self, template_dir: Path | None = None):
        if template_dir is None:
            template_dir = Path(__file__).parent
        super().__init__(template_dir)

    def generate(self, params: list[dict], output_path: Path) -> GenerateResult:
        """Write a DCM file to output_path.

        params: list of dicts with keys: name, description, default_value,
                min_value, max_value, unit.
        """
        errors: list[str] = []
        try:
            content = self.generate_string(params)
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_file(output_path, content)
            return GenerateResult(success=True, output_files=[output_path])
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            return GenerateResult(success=False, errors=errors)

    def generate_string(self, params: list[dict]) -> str:
        """Generate DCM content as a string."""
        lines = [
            '/begin PROJECT VCU_Calibration "VCU Calibration Data"',
            '  /begin HEADER "DCM Export"',
            '    VERSION "1.0"',
            "  /end HEADER",
            "",
            '  /begin MODULE VCU_Module "VCU"',
            "",
        ]

        for p in params:
            name = p.get("name", "")
            desc = p.get("description", name)
            lower = self._fmt_val(p.get("min_value"))
            upper = self._fmt_val(p.get("max_value"))
            value = self._fmt_val(p.get("default_value"))
            unit = p.get("unit", "")

            lines.append("    /begin CHARACTERISTIC")
            lines.append(f'      {name} "{desc}" VALUE 0x0 Default_RL 0 CM_Identical')
            lines.append(f"      {lower}")
            lines.append(f"      {upper}")
            lines.append(f"      VALUE = {value}")
            if unit:
                lines.append(f'      UNIT "{unit}"')
            lines.append("    /end CHARACTERISTIC")
            lines.append("")

        lines.append("  /end MODULE")
        lines.append("/end PROJECT")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _fmt_val(value) -> str:
        if value is None:
            return "0"
        try:
            if float(value) == int(float(value)):
                return str(int(float(value)))
        except (ValueError, OverflowError):
            pass
        return f"{value:g}"
