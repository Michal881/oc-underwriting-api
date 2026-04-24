import pandas as pd

INPUT_CSV = "/Users/local/Desktop/oc_policies_predictions.csv"
OUTPUT_FULL_CSV = "/Users/local/Desktop/oc_policies_predictions_audited.csv"
OUTPUT_REVIEW_CSV = "/Users/local/Desktop/oc_policies_needs_review.csv"

df = pd.read_csv(INPUT_CSV).copy()

required_cols = ["product_type", "pred_final"]
missing_cols = [c for c in required_cols if c not in df.columns]
if missing_cols:
    raise Exception(f"Brakuje kolumn w pliku wejściowym: {missing_cols}")

# =========================
# Normalizacja
# =========================
df["product_type"] = df["product_type"].fillna("").astype(str).str.strip()
df["pred_final"] = df["pred_final"].fillna("").astype(str).str.strip()

# =========================
# Match / review
# =========================
df["is_match"] = df["product_type"] == df["pred_final"]
df["needs_review"] = df["is_match"].map({True: "no", False: "yes"})

def build_review_reason(row):
    if row["is_match"]:
        return "ok"
    return f'label={row["product_type"]} vs pred={row["pred_final"]}'

df["review_reason"] = df.apply(build_review_reason, axis=1)

# =========================
# Confidence
# =========================
def confidence_level(row):
    p1 = row.get("pred_stage1_proba", 0)
    p2 = row.get("pred_stage2_proba", 0)

    # zabezpieczenie na NaN
    if pd.isna(p1):
        p1 = 0
    if pd.isna(p2):
        p2 = 0

    if row.get("pred_stage2") not in [None, "", float("nan")]:
        if p1 >= 0.9 and p2 >= 0.8:
            return "high"
        elif p1 >= 0.7:
            return "medium"
        else:
            return "low"
    else:
        if p1 >= 0.9:
            return "high"
        elif p1 >= 0.7:
            return "medium"
        else:
            return "low"

df["confidence"] = df.apply(confidence_level, axis=1)

# =========================
# Kolejność kolumn
# =========================
priority_cols = [
    "source_file",
    "product_type",
    "pred_stage1",
    "pred_stage1_proba",
    "pred_stage2",
    "pred_stage2_proba",
    "pred_final",
    "confidence",
    "is_match",
    "needs_review",
    "review_reason",
    "insured_activity",
    "sum_guaranteed_notes",
    "deductible_notes",
]

existing_priority_cols = [c for c in priority_cols if c in df.columns]
other_cols = [c for c in df.columns if c not in existing_priority_cols]

df = df[existing_priority_cols + other_cols]

# =========================
# Zapis
# =========================
df.to_csv(OUTPUT_FULL_CSV, index=False)

review_df = df[df["needs_review"] == "yes"].copy()
review_df.to_csv(OUTPUT_REVIEW_CSV, index=False)

# =========================
# Podsumowanie
# =========================
print("Gotowe.")
print(f"Pełny plik: {OUTPUT_FULL_CSV}")
print(f"Do review: {OUTPUT_REVIEW_CSV}")

print("\n=== PODSUMOWANIE ===")
print("Liczba wszystkich rekordów:", len(df))
print("Zgodne:", int(df["is_match"].sum()))
print("Do review:", int((df["needs_review"] == "yes").sum()))

print("\n=== ROZBICIE NIEZGODNOŚCI ===")
if len(review_df) == 0:
    print("Brak niezgodności.")
else:
    mismatch_summary = (
        review_df.groupby(["product_type", "pred_final"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    print(mismatch_summary.to_string(index=False))

print("\n=== ROZKŁAD CONFIDENCE ===")
print(df["confidence"].value_counts())