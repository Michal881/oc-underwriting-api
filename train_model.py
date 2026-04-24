import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix

df = pd.read_csv("/Users/local/Desktop/oc_policies_extracted_v2.csv")
df = df.dropna(subset=["product_type"])

X = (
    df["sum_guaranteed_notes"].fillna("") + " " +
    df["deductible_notes"].fillna("")
)
y = df["product_type"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

vectorizer = TfidfVectorizer(
    max_features=5000,
    ngram_range=(1, 2)
)

X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)

model = LogisticRegression(max_iter=1000)
model.fit(X_train_vec, y_train)

y_pred = model.predict(X_test_vec)

print("\n=== RAPORT ===")
print(classification_report(y_test, y_pred, zero_division=0))

print("\n=== MACIERZ POMYŁEK ===")
labels = sorted(y.unique())
cm = confusion_matrix(y_test, y_pred, labels=labels)
cm_df = pd.DataFrame(cm, index=[f"true_{x}" for x in labels], columns=[f"pred_{x}" for x in labels])
print(cm_df)

feature_names = vectorizer.get_feature_names_out()

print("\n=== NAJWAŻNIEJSZE CECHY DLA KAŻDEJ KLASY ===")
for i, class_name in enumerate(model.classes_):
    coefs = model.coef_[i]
    top_idx = coefs.argsort()[-15:][::-1]
    top_features = [(feature_names[j], round(coefs[j], 4)) for j in top_idx]

    print(f"\nKlasa: {class_name}")
    for feat, weight in top_features:
        print(f"  {feat:<35} {weight}")

results = pd.DataFrame({
    "text": X_test,
    "true_label": y_test,
    "pred_label": y_pred
})

errors = results[results["true_label"] != results["pred_label"]].copy()

print("\n=== PRZYKŁADOWE POMYŁKI ===")
if errors.empty:
    print("Brak pomyłek w próbce testowej.")
else:
    for _, row in errors.head(10).iterrows():
        print("\n---")
        print("TRUE:", row["true_label"])
        print("PRED:", row["pred_label"])
        print("TEXT:", row["text"][:500])