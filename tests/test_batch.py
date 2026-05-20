"""Tests for core.batch — batch processing engine."""

import pytest
from pathlib import Path

from core.batch import BatchProcessor, BatchResult


SAMPLE_DBC = """\
VERSION ""

NS_ :

BS_:

BU_: VCU BMS

BO_ 256 VCU_Status: 8 VCU
 SG_ VCU_PowerMode : 0|4@1+ (1,0) [0|15] "" BMS
 SG_ VCU_SOC : 8|8@1+ (0.5,0) [0|127.5] "%" BMS

BO_ 512 BMS_Voltage: 8 BMS
 SG_ HV_Voltage : 0|16@1+ (0.1,0) [0|1000] "V" VCU
"""


@pytest.fixture
def processor():
    return BatchProcessor()


@pytest.fixture
def sample_dbc(tmp_path):
    f = tmp_path / "test.dbc"
    f.write_text(SAMPLE_DBC, encoding="utf-8")
    return f


class TestBatchResult:

    def test_summary_success(self):
        r = BatchResult(success=True, files_processed=3, files_succeeded=3)
        assert "OK" in r.summary
        assert "3/3" in r.summary

    def test_summary_failure(self):
        r = BatchResult(success=False, files_processed=3, files_succeeded=2, files_failed=1)
        assert "FAILED" in r.summary


class TestBatchGenerate:

    def test_generate_c(self, processor, sample_dbc, tmp_path):
        result = processor.generate([sample_dbc], ["c"], tmp_path / "out")
        assert result.success
        assert result.files_succeeded == 1
        assert len(result.output_files) >= 1

    def test_generate_capl(self, processor, sample_dbc, tmp_path):
        result = processor.generate([sample_dbc], ["capl"], tmp_path / "out")
        assert result.success
        assert len(result.output_files) >= 1

    def test_generate_excel(self, processor, sample_dbc, tmp_path):
        result = processor.generate([sample_dbc], ["excel"], tmp_path / "out")
        assert result.success
        assert len(result.output_files) >= 1

    def test_generate_multiple_formats(self, processor, sample_dbc, tmp_path):
        result = processor.generate([sample_dbc], ["c", "capl"], tmp_path / "out")
        assert result.success
        # c generates 3 files, capl generates 1
        assert len(result.output_files) >= 4

    def test_generate_unsupported_format(self, processor, tmp_path):
        f = tmp_path / "test.xyz"
        f.write_text("data", encoding="utf-8")
        result = processor.generate([f], ["c"], tmp_path / "out")
        assert not result.success
        assert result.files_failed == 1

    def test_generate_unknown_output_format(self, processor, sample_dbc, tmp_path):
        result = processor.generate([sample_dbc], ["unknown_fmt"], tmp_path / "out")
        # File succeeds but format has error
        assert result.files_succeeded == 1
        assert len(result.errors) > 0

    def test_generate_creates_output_dir(self, processor, sample_dbc, tmp_path):
        out = tmp_path / "deep" / "nested" / "out"
        result = processor.generate([sample_dbc], ["c"], out)
        assert result.success
        assert out.exists()


class TestBatchValidate:

    def test_validate_valid_dbc(self, processor, sample_dbc):
        result = processor.validate([sample_dbc])
        assert result.success
        assert result.files_succeeded == 1

    def test_validate_invalid_dbc(self, processor, tmp_path):
        f = tmp_path / "bad.dbc"
        f.write_text("not a valid DBC", encoding="utf-8")
        result = processor.validate([f])
        assert not result.success
        assert result.files_failed == 1

    def test_validate_unsupported(self, processor, tmp_path):
        f = tmp_path / "test.xyz"
        f.write_text("data", encoding="utf-8")
        result = processor.validate([f])
        assert not result.success


class TestBatchDiff:

    def test_diff_identical(self, processor, sample_dbc, tmp_path):
        result = processor.diff(sample_dbc, sample_dbc, tmp_path / "diff.txt")
        assert result.success
        assert len(result.output_files) == 1

    def test_diff_different(self, processor, tmp_path):
        old = tmp_path / "old.dbc"
        old.write_text(SAMPLE_DBC, encoding="utf-8")
        new_content = SAMPLE_DBC.replace("0.5,0", "0.1,0")
        new = tmp_path / "new.dbc"
        new.write_text(new_content, encoding="utf-8")
        result = processor.diff(old, new, tmp_path / "diff.txt")
        assert result.success
        assert len(result.output_files) == 1

    def test_diff_excel_output(self, processor, tmp_path):
        old = tmp_path / "old.dbc"
        old.write_text(SAMPLE_DBC, encoding="utf-8")
        new = tmp_path / "new.dbc"
        new.write_text(SAMPLE_DBC, encoding="utf-8")
        result = processor.diff(old, new, tmp_path / "diff.xlsx")
        assert result.success
        assert result.output_files[0].suffix == ".xlsx"

    def test_diff_no_output_file(self, processor, sample_dbc):
        result = processor.diff(sample_dbc, sample_dbc)
        assert result.success
        assert len(result.output_files) == 0

    def test_diff_invalid_file(self, processor, tmp_path):
        bad = tmp_path / "bad.dbc"
        bad.write_text("not a DBC", encoding="utf-8")
        result = processor.diff(bad, bad)
        assert not result.success


class TestCLI:

    def test_cli_help(self):
        import subprocess
        r = subprocess.run(
            ["python", "cli.py", "--help"],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent,
        )
        assert r.returncode == 0
        assert "generate" in r.stdout

    def test_cli_generate(self, sample_dbc, tmp_path):
        import subprocess
        out = tmp_path / "cli_out"
        r = subprocess.run(
            ["python", "cli.py", "generate", "-i", str(sample_dbc), "-f", "c", "-o", str(out)],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent,
        )
        assert r.returncode == 0
        assert "OK" in r.stdout

    def test_cli_validate(self, sample_dbc):
        import subprocess
        r = subprocess.run(
            ["python", "cli.py", "validate", "-i", str(sample_dbc)],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent,
        )
        assert r.returncode == 0
