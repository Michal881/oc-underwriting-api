import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor

DATASET = "policies_dataset_v2_clean.csv"
MODEL_OUT = "premium_model.joblib"


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

        return "rate_unknown"

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


df = pd.read_csv(DATASET)

df["premium_type"] = df.apply(classify_premium, axis=1)
df = add_features(df)

# model składki dla segmentu SME / flat
train_df = df[
    (df["premium_type"] == "flat")
    & (df["premium_amount"].notna())
    & (df["premium_amount"] < 100000)
].copy()

features = [
    "sum_guaranteed_amount",
    "usa_canada_included",
    "num_covers",
    "product_family_code",
    "activity_len",
    "kw_budowl",
    "kw_produkc",
    "kw_doradzt",
    "kw_praw",
    "kw_księg",
]

train_df = train_df.dropna(subset=features + ["premium_amount"])

X = train_df[features]
y = train_df["premium_amount"]

model = RandomForestRegressor(n_estimators=300, random_state=42)
model.fit(X, y)

bundle = {
    "model": model,
    "features": features,
    "premium_types_count": df["premium_type"].value_counts().to_dict(),
    "training_rows": len(train_df),
}

joblib.dump(bundle, MODEL_OUT)

print("Gotowe.")
print(f"Zapisano model: {MODEL_OUT}")
print(f"Liczba rekordów treningowych: {len(train_df)}")
print("Typy składki:")
print(df["premium_type"].value_counts())