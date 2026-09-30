import argparse
import sys
from pathlib import Path

from app.data.contracts import ContractViolationError
from app.data.pipeline import run_pipeline

DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[3] / "data"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the local curated banking database.")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    args = parser.parse_args(argv)

    try:
        result = run_pipeline(args.data_root)
    except ContractViolationError as exc:
        print(f"contract failure: {exc}", file=sys.stderr)
        return 1

    print(f"database: {result.database_path}")
    print(f"report:   {result.report_path}")
    for key, table in result.report["tables"].items():
        print(f"  {key}: {table['curated_row_count']} rows, {len(table['findings'])} finding(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
