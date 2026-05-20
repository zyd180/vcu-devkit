"""Batch processing engine for headless / CI usage."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BatchResult:
    """Result of a batch operation."""
    success: bool
    files_processed: int = 0
    files_succeeded: int = 0
    files_failed: int = 0
    output_files: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        status = "OK" if self.success else "FAILED"
        return (
            f"[{status}] {self.files_succeeded}/{self.files_processed} succeeded, "
            f"{self.files_failed} failed, {len(self.output_files)} output files"
        )


class BatchProcessor:
    """Headless batch processing for DBC/ARXML/A2L files."""

    _FORMAT_MAP = {
        "c": "_generate_c",
        "capl": "_generate_capl",
        "arxml": "_generate_arxml",
        "a2l": "_generate_a2l",
        "excel": "_generate_excel",
        "signal_matrix": "_generate_signal_matrix",
    }

    def generate(
        self,
        inputs: list[Path],
        formats: list[str],
        output_dir: Path,
    ) -> BatchResult:
        """Generate code/files from input files."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        result = BatchResult(success=True)

        for inp in inputs:
            inp = Path(inp)
            result.files_processed += 1
            try:
                ext = inp.suffix.lower()
                if ext == ".dbc":
                    self._process_dbc(inp, formats, output_dir, result)
                elif ext == ".arxml":
                    self._process_arxml(inp, formats, output_dir, result)
                elif ext == ".a2l":
                    self._process_a2l(inp, formats, output_dir, result)
                else:
                    result.errors.append(f"Unsupported format: {ext}")
                    result.files_failed += 1
                    continue
                result.files_succeeded += 1
            except Exception as exc:
                result.errors.append(f"{inp.name}: {exc}")
                result.files_failed += 1

        result.success = result.files_failed == 0
        return result

    def validate(self, inputs: list[Path]) -> BatchResult:
        """Validate input files against rules."""
        result = BatchResult(success=True)

        for inp in inputs:
            inp = Path(inp)
            result.files_processed += 1
            try:
                ext = inp.suffix.lower()
                errors: list[str] = []
                if ext == ".dbc":
                    from core.parsers.dbc_parser import DBCParser
                    parser = DBCParser()
                    errors = parser.validate(inp)
                elif ext == ".arxml":
                    from core.parsers.arxml_parser import ARXMLParser
                    parser = ARXMLParser()
                    errors = parser.validate(inp)
                elif ext == ".a2l":
                    from core.parsers.a2l_parser import A2LParser
                    parser = A2LParser()
                    errors = parser.validate(inp)
                else:
                    result.errors.append(f"Unsupported format: {ext}")
                    result.files_failed += 1
                    continue

                if errors:
                    for e in errors:
                        result.errors.append(f"{inp.name}: {e}")
                    result.files_failed += 1
                else:
                    result.files_succeeded += 1
            except Exception as exc:
                result.errors.append(f"{inp.name}: {exc}")
                result.files_failed += 1

        result.success = result.files_failed == 0
        return result

    def diff(self, old: Path, new: Path, output: Path | None = None) -> BatchResult:
        """Compare two DBC files and produce a diff report."""
        from core.parsers.dbc_parser import DBCParser
        from core.diff.dbc_diff import DBCDiffEngine

        result = BatchResult(success=True, files_processed=2)
        try:
            parser = DBCParser()
            old_data = parser.parse(Path(old))
            new_data = parser.parse(Path(new))
            if not old_data.success:
                result.errors.extend(old_data.errors)
                result.files_failed += 1
            if not new_data.success:
                result.errors.extend(new_data.errors)
                result.files_failed += 1
            if result.files_failed:
                result.success = False
                return result

            engine = DBCDiffEngine()
            diff = engine.compare(old_data.data, new_data.data)

            if output:
                output = Path(output)
                output.parent.mkdir(parents=True, exist_ok=True)
                if output.suffix == ".xlsx":
                    engine.export_excel_report(diff, output)
                else:
                    report = engine.generate_text_report(diff)
                    output.write_text(report, encoding="utf-8")
                result.output_files.append(output)

            result.files_succeeded = 2
        except Exception as exc:
            result.errors.append(str(exc))
            result.files_failed = 2
            result.success = False

        return result

    # ── Internal generators ───────────────────────────────────────────────

    def _process_dbc(self, inp: Path, formats: list[str], output_dir: Path, result: BatchResult):
        from core.parsers.dbc_parser import DBCParser
        parser = DBCParser()
        parse_result = parser.parse(inp)
        if not parse_result.success:
            raise ValueError(f"Parse failed: {parse_result.errors}")
        data = parse_result.data
        subdir = output_dir / inp.stem
        subdir.mkdir(parents=True, exist_ok=True)

        for fmt in formats:
            if fmt == "c":
                from core.generators.c_generator import CANCodeGenerator
                gen = CANCodeGenerator()
                r = gen.generate(data, subdir)
            elif fmt == "capl":
                from core.generators.capl_generator import CAPLGenerator
                gen = CAPLGenerator()
                r = gen.generate(data, subdir)
            elif fmt in ("excel", "signal_matrix"):
                from core.generators.report_generator import ReportGenerator
                gen = ReportGenerator()
                r = gen.generate_signal_matrix(data, subdir / f"{inp.stem}_signals.xlsx")
            elif fmt == "arxml":
                continue  # DBC → ARXML not supported
            else:
                result.errors.append(f"Unknown format '{fmt}' for DBC")
                continue

            if r.success:
                result.output_files.extend(r.output_files)
            else:
                result.errors.extend(r.errors)

    def _process_arxml(self, inp: Path, formats: list[str], output_dir: Path, result: BatchResult):
        from core.parsers.arxml_parser import ARXMLParser
        parser = ARXMLParser()
        parse_result = parser.parse(inp)
        if not parse_result.success:
            raise ValueError(f"Parse failed: {parse_result.errors}")
        data = parse_result.data
        subdir = output_dir / inp.stem
        subdir.mkdir(parents=True, exist_ok=True)

        for fmt in formats:
            if fmt == "arxml":
                from core.generators.arxml_generator import ARXMLGenerator
                gen = ARXMLGenerator()
                out_path = subdir / f"{inp.stem}_export.arxml"
                r = gen.generate(data, out_path)
            elif fmt == "a2l":
                from core.generators.a2l_generator import A2LGenerator
                gen = A2LGenerator()
                out_path = subdir / f"{inp.stem}.a2l"
                r = gen.generate(data, out_path)
            elif fmt == "rte":
                from core.generators.rte_generator import RTEGenerator
                gen = RTEGenerator()
                r = gen.generate(data, subdir)
            else:
                result.errors.append(f"Unknown format '{fmt}' for ARXML")
                continue

            if r.success:
                result.output_files.extend(r.output_files)
            else:
                result.errors.extend(r.errors)

    def _process_a2l(self, inp: Path, formats: list[str], output_dir: Path, result: BatchResult):
        from core.parsers.a2l_parser import A2LParser
        parser = A2LParser()
        parse_result = parser.parse(inp)
        if not parse_result.success:
            raise ValueError(f"Parse failed: {parse_result.errors}")
        subdir = output_dir / inp.stem
        subdir.mkdir(parents=True, exist_ok=True)

        for fmt in formats:
            if fmt == "a2l":
                # Round-trip: parse → serialize back
                from core.parsers.a2l_parser import a2l_data_to_dict
                import json
                d = a2l_data_to_dict(parse_result.data)
                out_path = subdir / f"{inp.stem}_export.json"
                out_path.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
                result.output_files.append(out_path)
            else:
                result.errors.append(f"Unknown format '{fmt}' for A2L")
