import pandas as pd
import joblib

DATASET = "policies_dataset_v2_clean.csv"
MODEL_FILE = "premium_model.joblib"

bundle = joblib.load(MODEL_FILE)
model = bundle["model"]
features = bundle["features"]

df = pd.read_csv(DATASET)

# Te same feature'y co przy treningu
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

# Testujemy TYLKO segment, dla którego model był trenowany:
# premium flat / SME, czyli składki poniżej 100 000 PLN
test_df = df[
    (df["premium_amount"].notna())
    & (df["premium_amount"] < 100000)
].dropna(subset=features).copy()

test_df["estimated_premium_ml"] = model.predict(test_df[features])
test_df["difference"] = test_df["estimated_premium_ml"] - test_df["premium_amount"]

cols = [
    "source_file",
    "product_family",
    "sum_guaranteed_amount",
    "premium_amount",
    "estimated_premium_ml",
    "difference",
]

print("\nLiczba rekordów testowych:", len(test_df))
print(test_df[cols].to_string())