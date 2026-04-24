import pandas as pd
import joblib

MODEL_FILE = "premium_model.joblib"

bundle = joblib.load(MODEL_FILE)
model = bundle["model"]
features = bundle["features"]


def classify_premium(row):
    if pd.notna(row["turnover_amount"]) and pd.notna(row["rate_primary_per_mille"]):
        calc = row["turnover_amount"] * row["rate_primary_per_mille"] / 1000

        if pd.notna(row["premium_amount"]):
            ratio = row["premium_amount"] / calc if calc != 0 else None

            if ratio is not None:
                if 0.7 < ratio < 0.9:
                    return "minimum_deposit"
                elif 0.9 < ratio < 1.1:
                    return "pure_rate"
                elif ratio > 2:
                    return "minimum_override"

        return "rate"

    elif pd.notna(row["premium_amount"]):
        return "flat"

    return "unknown"


def add_features(df):
    df = df.copy()

    cover_cols = [c for c in df.columns if c.startswith("covers_")]
    df["num_covers"] = df[cover_cols].sum(axis=1)

    df["product_family_code"] = df["product_family"].astype("category").cat.codes
    df["activity_len"] = df["insured_activity"].fillna("").apply(len)

    keywords = ["budowl", "produkc", "doradzt", "praw", "księg"]

    for kw in keywords:
        df[f"kw_{kw}"] = (
            df["insured_activity"]
            .fillna("")
            .str.lower()
            .str.contains(kw)
            .astype(int)
        )

    return df


def estimate_row(row):
    premium_type = classify_premium(row)

    # --- CASE 1: RATE ---
    if premium_type in ["pure_rate", "minimum_deposit", "rate"]:
        if pd.notna(row["turnover_amount"]) and pd.notna(row["rate_primary_per_mille"]):
            calc = row["turnover_amount"] * row["rate_primary_per_mille"] / 1000

            if premium_type == "minimum_deposit":
                return {
                    "method": "rate_minimum",
                    "estimated": calc * 0.8,
                    "reason": "turnover × rate × 0.8"
                }
            else:
                return {
                    "method": "rate",
                    "estimated": calc,
                    "reason": "turnover × rate"
                }

    # --- CASE 2: FLAT SME → ML ---
    if premium_type == "flat" and pd.notna(row["premium_amount"]) and row["premium_amount"] < 100000:
        df = pd.DataFrame([row])
        df = add_features(df)

        if not df[features].isna().any(axis=1).iloc[0]:
            pred = model.predict(df[features])[0]

            return {
                "method": "ml",
                "estimated": float(pred),
                "reason": "ML model (SME flat)"
            }

    # --- CASE 3: fallback ---
    return {
        "method": "fallback",
        "estimated": None,
        "reason": "insufficient data / large risk"
    }


def run_pipeline(dataset_path):
    df = pd.read_csv(dataset_path)

    results = []

    for _, row in df.iterrows():
        res = estimate_row(row)

        results.append({
            "source_file": row["source_file"],
            "premium_real": row.get("premium_amount"),
            "estimated": res["estimated"],
            "method": res["method"],
            "reason": res["reason"]
        })

    return pd.DataFrame(results)


if __name__ == "__main__":
    df_out = run_pipeline("policies_dataset_v2_clean.csv")
    print(df_out.to_string())