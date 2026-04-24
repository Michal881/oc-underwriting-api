import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression


class FunctionTransformerForText:
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        if hasattr(X, "iloc"):
            return X.iloc[:, 0].fillna("").astype(str).tolist()
        if hasattr(X, "ndim") and X.ndim == 2:
            return pd.Series(X[:, 0]).fillna("").astype(str).tolist()
        return pd.Series(X).fillna("").astype(str).tolist()


CSV_PATH = "/Users/local/Desktop/oc_policies_extracted_v2.csv"

df = pd.read_csv(CSV_PATH)
df = df.dropna(subset=["product_type"]).copy()


# =========================
# STAGE 1
# =========================
def map_stage1(label: str) -> str:
    if label in ["oc_architekci", "oc_budowlane"]:
        return "oc_techniczne"
    return label


df["product_type_stage1"] = df["product_type"].apply(map_stage1)

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
y1 = df["product_type_stage1"]

stage1_text_transformers = []
for col in stage1_text_features:
    stage1_text_transformers.append(
        (
            f"tfidf_{col}",
            Pipeline([
                ("imputer", SimpleImputer(strategy="constant", fill_value="")),
                ("flatten", FunctionTransformerForText()),
                ("tfidf", TfidfVectorizer(max_features=3000, ngram_range=(1, 2))),
            ]),
            [col],
        )
    )

stage1_cat_transformer = Pipeline([
    ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
    ("onehot", OneHotEncoder(handle_unknown="ignore")),
])

stage1_preprocessor = ColumnTransformer(
    transformers=stage1_text_transformers + [
        ("cat", stage1_cat_transformer, stage1_categorical_features)
    ]
)

stage1_model = Pipeline([
    ("preprocessor", stage1_preprocessor),
    ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced")),
])

stage1_model.fit(X1, y1)

joblib.dump(stage1_model, "stage1_model.joblib")


# =========================
# STAGE 2
# =========================
df2 = df[df["product_type"].isin(["oc_architekci", "oc_budowlane"])].copy()

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

X2 = df2[stage2_text_features + stage2_categorical_features]
y2 = df2["product_type"]

stage2_text_transformers = []
for col in stage2_text_features:
    stage2_text_transformers.append(
        (
            f"tfidf_{col}",
            Pipeline([
                ("imputer", SimpleImputer(strategy="constant", fill_value="")),
                ("flatten", FunctionTransformerForText()),
                ("tfidf", TfidfVectorizer(max_features=2000, ngram_range=(1, 2))),
            ]),
            [col],
        )
    )

stage2_cat_transformer = Pipeline([
    ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
    ("onehot", OneHotEncoder(handle_unknown="ignore")),
])

stage2_preprocessor = ColumnTransformer(
    transformers=stage2_text_transformers + [
        ("cat", stage2_cat_transformer, stage2_categorical_features)
    ]
)

stage2_model = Pipeline([
    ("preprocessor", stage2_preprocessor),
    ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced")),
])

stage2_model.fit(X2, y2)

joblib.dump(stage2_model, "stage2_model.joblib")

print("Gotowe.")
print("Zapisano:")
print("- stage1_model.joblib")
print("- stage2_model.joblib")