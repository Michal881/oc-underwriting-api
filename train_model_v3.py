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
    """
    Zamienia wejście z ColumnTransformer na listę stringów dla TfidfVectorizer.
    """
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        if hasattr(X, "iloc"):
            return X.iloc[:, 0].fillna("").astype(str).tolist()
        if hasattr(X, "ndim") and X.ndim == 2:
            return pd.Series(X[:, 0]).fillna("").astype(str).tolist()
        return pd.Series(X).fillna("").astype(str).tolist()


# === 1. Wczytanie danych ===
df = pd.read_csv("/Users/local/Desktop/oc_policies_extracted_v2.csv")

target_col = "product_type"

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

df = df.dropna(subset=[target_col]).copy()

X = df[text_features + categorical_features]
y = df[target_col]

# stratify zachowuje proporcje klas
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# osobny TF-IDF dla każdej kolumny tekstowej
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

print("\n=== RAPORT V3 ===")
print(classification_report(y_test, y_pred, zero_division=0))

print("\n=== MACIERZ POMYŁEK V3 ===")
labels = sorted(y.unique())
cm = confusion_matrix(y_test, y_pred, labels=labels)
cm_df = pd.DataFrame(
    cm,
    index=[f"true_{x}" for x in labels],
    columns=[f"pred_{x}" for x in labels]
)
print(cm_df)

results = X_test.copy()
results["true_label"] = y_test.values
results["pred_label"] = y_pred

errors = results[results["true_label"] != results["pred_label"]].copy()

print("\n=== PRZYKŁADOWE POMYŁKI V3 ===")
if errors.empty:
    print("Brak pomyłek w próbce testowej.")
else:
    cols_to_show = [
        "insured_activity",
        "sum_guaranteed_notes",
        "deductible_notes",
        "covers_pure_financial_loss",
        "has_documents_loss",
        "has_office_liability",
        "has_excess_layer",
        "true_label",
        "pred_label",
    ]
    for _, row in errors[cols_to_show].head(10).iterrows():
        print("\n---")
        for c in cols_to_show:
            print(f"{c}: {row[c]}")