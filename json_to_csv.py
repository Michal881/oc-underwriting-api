from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


CSV_COLUMNS = [
    "source_file",
    "policy_number",
    "insurer",
    "policyholder",
    "insured",
    "agent_or_broker",
    "insured_activity",
    "insured_products",
    "risk_code",
    "scope_of_insurance",
    "sum_guaranteed",
    "additional_clauses",
    "territorial_scope",
    "insurance_period",
    "turnover",
    "rate",
    "premium",
    "premium_payment",
    "additional_conditions",
    "covers_general_liability",
    "covers_professional_liability",
    "covers_product_liability",
    "covers_completed_operations",
    "covers_pure_financial_loss",
    "covers_employers_liability",
    "covers_documents_loss",
    "covers_subcontractors",
    "usa_canada_included",
    "sum_guaranteed_amount",
    "turnover_amount",
    "premium_amount",
    "rate_primary_per_mille",
]


def normalize_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, list):
        return " | ".join("" if v is None else str(v) for v in value)

    text = str(value).strip()

    # Zamieniamy wielolinijkowy tekst na jedną linię do CSV
    text = text.replace("\r", " ").replace("\n", " | ")
    return text


def flatten_json_record(data: Dict[str, Any]) -> Dict[str, str]:
    row: Dict[str, str] = {}

    fields = data.get("fields", {}) or {}
    parsed_numbers = data.get("parsed_numbers", {}) or {}
    flags = data.get("flags", {}) or {}

    row["source_file"] = normalize_value(data.get("source_file"))

    for col in CSV_COLUMNS:
        if col == "source_file":
            continue

        if col in fields:
            row[col] = normalize_value(fields.get(col))
        elif col in parsed_numbers:
            row[col] = normalize_value(parsed_numbers.get(col))
        elif col in flags:
            row[col] = normalize_value(flags.get(col))
        else:
            row[col] = ""

    return row


def load_json_file(file_path: Path) -> Dict[str, Any]:
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def collect_json_files(directory: Path) -> List[Path]:
    return sorted(directory.glob("*.json"))


def write_csv(rows: List[Dict[str, str]], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Zbiera pliki JSON z polis do jednego CSV")
    parser.add_argument(
        "-d",
        "--directory",
        required=True,
        help="Folder z plikami .json",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="policies_dataset.csv",
        help="Nazwa pliku wynikowego CSV",
    )

    args = parser.parse_args()

    input_dir = Path(args.directory)
    if not input_dir.exists():
        raise FileNotFoundError(f"Nie znaleziono folderu: {input_dir}")

    json_files = collect_json_files(input_dir)
    print(f"Znaleziono {len(json_files)} plików JSON...")

    rows: List[Dict[str, str]] = []

    for file_path in json_files:
        try:
            data = load_json_file(file_path)
            row = flatten_json_record(data)
            rows.append(row)
            print(f"✔ {file_path.name}")
        except Exception as e:
            print(f"❌ {file_path.name} → BŁĄD: {e}")

    output_path = input_dir / args.output
    write_csv(rows, output_path)

    print(f"\nGotowe. Zapisano CSV do: {output_path}")
    print(f"Liczba rekordów: {len(rows)}")


if __name__ == "__main__":
    main()