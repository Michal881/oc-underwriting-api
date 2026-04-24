from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


INPUT_FILE = "policies_dataset.csv"
OUTPUT_FILE = "policies_dataset_v2_clean.csv"


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    text = text.replace("\r", " ").replace("\n", " | ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_first_money_amount(value: object) -> float | None:
    if pd.isna(value):
        return None
    text = str(value)
    match = re.search(r"(\d{1,3}(?:[ .]\d{3})*(?:,\d+)?)", text)
    if not match:
        return None
    number = match.group(1).replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(number)
    except ValueError:
        return None


def extract_turnover_amount(value: object) -> float | None:
    if pd.isna(value):
        return None
    text = str(value)

    # Priorytet: większe kwoty z walutą
    matches = re.findall(r"(\d{1,3}(?:[ .]\d{3})*(?:,\d+)?)\s*(PLN|zł|EUR|USD)", text, flags=re.IGNORECASE)
    if matches:
        numbers = []
        for amount, _currency in matches:
            try:
                number = float(amount.replace(" ", "").replace(".", "").replace(",", "."))
                numbers.append(number)
            except ValueError:
                pass
        if numbers:
            return max(numbers)

    return None


def extract_rate_amount(value: object) -> float | None:
    if pd.isna(value):
        return None
    text = str(value)
    match = re.search(r"(\d+(?:,\d+)?)\s*‰", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def trim_after_markers(value: object, markers: list[str]) -> str:
    text = clean_text(value)
    lowered = text.lower()

    cut_positions = []
    for marker in markers:
        idx = lowered.find(marker.lower())
        if idx != -1:
            cut_positions.append(idx)

    if cut_positions:
        text = text[: min(cut_positions)].strip(" |,-")

    return text


def normalize_scope(value: object) -> str:
    text = clean_text(value)
    text = trim_after_markers(text, [
        "suma gwarancyjna",
        "sum insured",
        "okres ubezpieczenia",
        "stawka",
        "składka",
        "franszyza",
    ])
    return text


def normalize_premium_payment(value: object) -> str:
    text = clean_text(value)
    text = trim_after_markers(text, [
        "nr konta",
        "numer konta",
        "nr rachunku",
        "bank handlowy",
        "nrb:",
        "klient",
        "pośrednik",
        "debetor",
        "cr",
        "nip",
        "regon",
        "typ polisy",
    ])
    return text


def normalize_additional_conditions(value: object) -> str:
    text = clean_text(value)
    text = trim_after_markers(text, [
        "klient",
        "pośrednik",
        "debetor",
        "cr",
        "nip",
        "regon",
        "typ polisy",
        "warunki umowy",
    ])
    return text


def has_any(text: str, phrases: list[str]) -> bool:
    return any(p in text for p in phrases)


def fix_product_liability_flag(scope: object, clauses: object, conditions: object) -> bool:
    text = " ".join([
        clean_text(scope).lower(),
        clean_text(clauses).lower(),
        clean_text(conditions).lower(),
    ])

    if not has_any(text, ["produkt", "product liability", "odpowiedzialność za produkt", "oc za produkt"]):
        return False

    negative_patterns = [
        "z wyłączeniem odpowiedzialności za produkt",
        "nie obejmuje odpowiedzialności za produkt",
        "wyłączona odpowiedzialność za produkt",
        "wyłączenie odpowiedzialności za produkt",
    ]
    if has_any(text, negative_patterns):
        return False

    return True


def fix_completed_operations_flag(scope: object, clauses: object, conditions: object) -> bool:
    text = " ".join([
        clean_text(scope).lower(),
        clean_text(clauses).lower(),
        clean_text(conditions).lower(),
    ])

    if not has_any(text, ["wykonane usługi", "completed operations"]):
        return False

    negative_patterns = [
        "z wyłączeniem",
        "nie obejmuje wykonanych usług",
        "wyłączone wykonane usługi",
    ]
    if has_any(text, negative_patterns):
        # jeżeli jest wyraźne włączenie, to i tak True
        if has_any(text, ["z włączeniem", "including", "włączeniem odpowiedzialności"]):
            return True
        return False

    return True


def fix_employers_liability_flag(clauses: object, conditions: object) -> bool:
    text = " ".join([
        clean_text(clauses).lower(),
        clean_text(conditions).lower(),
    ])
    return has_any(text, [
        "odpowiedzialność pracodawcy",
        "odpowiedzialność cywilna pracodawcy",
        "employer",
    ])


def infer_product_family(scope: object, activity: object, clauses: object) -> str:
    text = " ".join([
        clean_text(scope).lower(),
        clean_text(activity).lower(),
        clean_text(clauses).lower(),
    ])

    if has_any(text, ["zawodowa odpowiedzialność cywilna", "wykonywania zawodu", "pomocy prawnej", "projektanta", "architekt", "doradztwa podatkowego"]):
        return "oc_zawodowe"

    if has_any(text, ["odpowiedzialność za produkt", "product liability", "oc za produkt"]):
        return "oc_produkt_lub_mieszane"

    if has_any(text, ["prowadzonej działalności", "posiadanego mienia", "third party liability"]):
        return "oc_ogolne"

    return "nieustalone"


def main() -> None:
    input_path = Path(INPUT_FILE)
    if not input_path.exists():
        raise FileNotFoundError(f"Nie znaleziono pliku wejściowego: {INPUT_FILE}")

    df = pd.read_csv(input_path)

    # Czyszczenie tekstów
    text_columns = [
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
    ]

    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].apply(clean_text)

    # Dodatkowe czyszczenie wybranych kolumn
    if "scope_of_insurance" in df.columns:
        df["scope_of_insurance"] = df["scope_of_insurance"].apply(normalize_scope)

    if "premium_payment" in df.columns:
        df["premium_payment"] = df["premium_payment"].apply(normalize_premium_payment)

    if "additional_conditions" in df.columns:
        df["additional_conditions"] = df["additional_conditions"].apply(normalize_additional_conditions)

    # Liczby - przeliczenie od nowa
    if "sum_guaranteed" in df.columns:
        df["sum_guaranteed_amount"] = df["sum_guaranteed"].apply(extract_first_money_amount)

    if "turnover" in df.columns:
        df["turnover_amount"] = df["turnover"].apply(extract_turnover_amount)

    if "premium" in df.columns:
        df["premium_amount"] = df["premium"].apply(extract_first_money_amount)

    if "rate" in df.columns:
        df["rate_primary_per_mille"] = df["rate"].apply(extract_rate_amount)

    # Poprawa flag
    def _safe_col(row, col):
        return row[col] if col in row.index else ""

    df["covers_product_liability"] = df.apply(
        lambda row: fix_product_liability_flag(
            _safe_col(row, "scope_of_insurance"),
            _safe_col(row, "additional_clauses"),
            _safe_col(row, "additional_conditions"),
        ),
        axis=1,
    )

    df["covers_completed_operations"] = df.apply(
        lambda row: fix_completed_operations_flag(
            _safe_col(row, "scope_of_insurance"),
            _safe_col(row, "additional_clauses"),
            _safe_col(row, "additional_conditions"),
        ),
        axis=1,
    )

    df["covers_employers_liability"] = df.apply(
        lambda row: fix_employers_liability_flag(
            _safe_col(row, "additional_clauses"),
            _safe_col(row, "additional_conditions"),
        ),
        axis=1,
    )

    # Klasyfikacja typu polisy
    df["product_family"] = df.apply(
        lambda row: infer_product_family(
            _safe_col(row, "scope_of_insurance"),
            _safe_col(row, "insured_activity"),
            _safe_col(row, "additional_clauses"),
        ),
        axis=1,
    )

    # Finalne kolumny robocze
    final_columns = [
        "source_file",
        "product_family",
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
        "sum_guaranteed_amount",
        "territorial_scope",
        "insurance_period",
        "turnover",
        "turnover_amount",
        "rate",
        "rate_primary_per_mille",
        "premium",
        "premium_amount",
        "premium_payment",
        "additional_clauses",
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
    ]

    existing_final_columns = [col for col in final_columns if col in df.columns]
    df_clean = df[existing_final_columns]

    output_path = Path(OUTPUT_FILE)
    df_clean.to_csv(output_path, index=False)

    print(f"Clean dataset saved to: {output_path}")
    print(f"Liczba rekordów: {len(df_clean)}")


if __name__ == "__main__":
    main()