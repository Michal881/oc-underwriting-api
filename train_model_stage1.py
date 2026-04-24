import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
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


df = pd.read_csv("/Users/local/Desktop/oc_policies_extracted_v2.csv")

# mapowanie 4 klas -> 3 klasy
def map_stage1(label: str) -> str:
    if label in ["oc_architekci", "oc_budowlane"]:
        return "oc_techniczne"
    return label

df = df.dropna(subset=["product_type"]).copy()
df["product_type_stage1"] = df["product_type"].apply(map_stage1)

target_col = "product_type_stage1"

text_features = [
    "sum_guaranteed_notes",
    "deductible_notes",
    "insured_activity",
]

categorical_features = [
    "covers_pure_financial_loss",
    "has_documents_loss",
    "has_office_liability",
    "has_excess_layer",
]

required_cols = [target_col] + text_features + categorical_features
missing_cols = [c for c in required_cols if c not in df.columns]
if missing_cols:
    raise Exception(f"Brakuje kolumn w CSV: {missing_cols}")

X = df[text_features + categorical_features]
y = df[target_col]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

text_transformers = []
for col in text_features:
    text_transformers.append(
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

categorical_transformer = Pipeline([
    ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
    ("onehot", OneHotEncoder(handle_unknown="ignore")),
])

preprocessor = ColumnTransformer(
    transformers=text_transformers + [
        ("cat", categorical_transformer, categorical_features)
    ]
)

model = Pipeline([
    ("preprocessor", preprocessor),
    ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced")),
])

model.fit(X_train, y_train)
y_pred = model.predict(X_test)

print("\n=== RAPORT STAGE 1 ===")
print(classification_report(y_test, y_pred, zero_division=0))

print("\n=== MACIERZ POMYŁEK STAGE 1 ===")
labels = sorted(y.unique())
cm = confusion_matrix(y_test, y_pred, labels=labels)
cm_df = pd.DataFrame(
    cm,
    index=[f"true_{x}" for x in labels],
    columns=[f"pred_{x}" for x in labels]
)
print(cm_df)