"""VCU DevKit CLI — headless batch processing for CI/CD pipelines."""

from __future__ import annotations

import argparse
import sys
from glob import glob
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vcu-devkit",
        description="VCU DevKit CLI — 批量生成、校验、对比",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── generate ──────────────────────────────────────────────────────────
    gen_p = sub.add_parser("generate", help="从 DBC/ARXML/A2L 批量生成代码")
    gen_p.add_argument("--input", "-i", nargs="+", required=True, help="输入文件 (支持 glob)")
    gen_p.add_argument("--format", "-f", required=True, help="输出格式: c,capl,arxml,a2l,excel,rte (逗号分隔)")
    gen_p.add_argument("--output", "-o", required=True, help="输出目录")

    # ── validate ──────────────────────────────────────────────────────────
    val_p = sub.add_parser("validate", help="校验 DBC/ARXML/A2L 文件")
    val_p.add_argument("--input", "-i", nargs="+", required=True, help="输入文件 (支持 glob)")

    # ── diff ──────────────────────────────────────────────────────────────
    diff_p = sub.add_parser("diff", help="对比两个 DBC 文件")
    diff_p.add_argument("--old", required=True, help="旧版 DBC 文件")
    diff_p.add_argument("--new", required=True, help="新版 DBC 文件")
    diff_p.add_argument("--output", "-o", help="输出文件 (.xlsx 或 .txt)")

    args = parser.parse_args(argv)

    # Expand globs
    def expand(patterns: list[str]) -> list[Path]:
        files: list[Path] = []
        for p in patterns:
            expanded = glob(p)
            if expanded:
                files.extend(Path(f) for f in expanded)
            else:
                files.append(Path(p))
        return files

    from core.batch import BatchProcessor
    proc = BatchProcessor()

    if args.command == "generate":
        inputs = expand(args.input)
        formats = [f.strip().lower() for f in args.format.split(",")]
        output_dir = Path(args.output)
        result = proc.generate(inputs, formats, output_dir)

    elif args.command == "validate":
        inputs = expand(args.input)
        result = proc.validate(inputs)

    elif args.command == "diff":
        result = proc.diff(Path(args.old), Path(args.new), Path(args.output) if args.output else None)

    else:
        return 1

    # Print result
    print(result.summary)
    if result.errors:
        for err in result.errors:
            print(f"  ERROR: {err}", file=sys.stderr)

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
