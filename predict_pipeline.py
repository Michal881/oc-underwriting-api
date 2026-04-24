class FunctionTransformerForText:
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        import pandas as pd

        if hasattr(X, "iloc"):
            return X.iloc[:, 0].fillna("").astype(str).tolist()
        if hasattr(X, "ndim") and X.ndim == 2:
            return pd.Series(X[:, 0]).fillna("").astype(str).tolist()
        return pd.Series(X).fillna("").astype(str).tolist()
import pandas as pd
import joblib


INPUT_CSV = "/Users/local/Desktop/oc_policies_extracted_v2.csv"
OUTPUT_CSV = "/Users/local/Desktop/oc_policies_predictions.csv"

stage1_model = joblib.load("stage1_model.joblib")
stage2_model = joblib.load("stage2_model.joblib")

df = pd.read_csv(INPUT_CSV).copy()

# =========================
# Stage 1
# =========================
stage1_text_features = [
    "sum_guaranteed_notes",
    "deductible_notes",
    "insured_activity",
]

stage1_categorical_features = [
    "covers_pure_financial_loss",
    "has_documents_loss",
    "has_office_liability",
    "has_excess_layer",
]

X1 = df[stage1_text_features + stage1_categorical_features]
df["pred_stage1"] = stage1_model.predict(X1)

if hasattr(stage1_model.named_steps["classifier"], "predict_proba"):
    proba1 = stage1_model.predict_proba(X1)
    classes1 = stage1_model.named_steps["classifier"].classes_
    class_to_idx1 = {c: i for i, c in enumerate(classes1)}
    df["pred_stage1_proba"] = [
        round(proba1[i, class_to_idx1[df.iloc[i]["pred_stage1"]]], 4)
        for i in range(len(df))
    ]
else:
    df["pred_stage1_proba"] = None


# =========================
# Stage 2 tylko dla technicznych
# =========================
df["pred_final"] = df["pred_stage1"]
df["pred_stage2"] = None
df["pred_stage2_proba"] = None

tech_mask = df["pred_stage1"] == "oc_techniczne"

if tech_mask.any():
    stage2_text_features = [
        "insured_activity",
        "sum_guaranteed_notes",
        "deductible_notes",
    ]

    stage2_categorical_features = [
        "has_documents_loss",
        "has_office_liability",
        "covers_pure_financial_loss",
    ]

    X2 = df.loc[tech_mask, stage2_text_features + stage2_categorical_features]
    pred2 = stage2_model.predict(X2)

    df.loc[tech_mask, "pred_stage2"] = pred2
    df.loc[tech_mask, "pred_final"] = pred2

    if hasattr(stage2_model.named_steps["classifier"], "predict_proba"):
        proba2 = stage2_model.predict_proba(X2)
        classes2 = stage2_model.named_steps["classifier"].classes_
        class_to_idx2 = {c: i for i, c in enumerate(classes2)}

        pred2_list = list(pred2)
        proba2_list = [
            round(proba2[i, class_to_idx2[pred2_list[i]]], 4)
            for i in range(len(pred2_list))
        ]
        df.loc[tech_mask, "pred_stage2_proba"] = proba2_list

# zapis
df.to_csv(OUTPUT_CSV, index=False)

print("Gotowe.")
print(f"Zapisano: {OUTPUT_CSV}")

print("\nPodsumowanie pred_final:")
print(df["pred_final"].value_counts(dropna=False))