from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
import joblib


bundle = joblib.load("premium_model.joblib")
model = bundle["model"]
features = bundle["features"]

app = FastAPI(title="OC Underwriting API")


class PolicyInput(BaseModel):
    product_family: Optional[str] = None
    insured_activity: Optional[str] = None
    scope_of_insurance: Optional[str] = None
    insured_products: Optional[str] = None

    sum_guaranteed_amount: Optional[float] = None
    turnover_amount: Optional[float] = None
    rate_primary_per_mille: Optional[float] = None
    premium_amount: Optional[float] = None
    usa_canada_included: bool = False

    covers_general_liability: int = 0
    covers_professional_liability: int = 0
    covers_product_liability: int = 0
    covers_completed_operations: int = 0
    covers_pure_financial_loss: int = 0
    covers_employers_liability: int = 0
    covers_documents_loss: int = 0
    covers_subcontractors: int = 0


class ProductInput(BaseModel):
    product_family: Optional[str] = None
    insured_activity: Optional[str] = None
    scope_of_insurance: Optional[str] = None
    insured_products: Optional[str] = None


def classify_premium(row):
    if row.get("turnover_amount") and row.get("rate_primary_per_mille"):
        calc = row["turnover_amount"] * row["rate_primary_per_mille"] / 1000

        if row.get("premium_amount"):
            ratio = row["premium_amount"] / calc if calc != 0 else None

            if ratio:
                if 0.7 < ratio < 0.9:
                    return "minimum_deposit"
                elif 0.9 < ratio < 1.1:
                    return "pure_rate"
                elif ratio > 2:
                    return "minimum_override"

        return "rate"

    elif row.get("premium_amount"):
        return "flat"

    return "unknown"


def add_features(df):
    df = df.copy()

    cover_cols = [c for c in df.columns if c.startswith("covers_")]
    df["num_covers"] = df[cover_cols].sum(axis=1)

    df["product_family"] = df["product_family"].fillna("nieustalone")
    df["product_family_code"] = df["product_family"].astype("category").cat.codes

    df["insured_activity"] = df["insured_activity"].fillna("")
    df["activity_len"] = df["insured_activity"].apply(len)

    keywords = ["budowl", "produkc", "doradzt", "praw", "księg"]

    for kw in keywords:
        df[f"kw_{kw}"] = (
            df["insured_activity"]
            .str.lower()
            .str.contains(kw)
            .astype(int)
        )

    return df


def estimate(policy_dict):
    row = policy_dict.copy()
    premium_type = classify_premium(row)

    if premium_type in ["pure_rate", "minimum_deposit", "rate"]:
        calc = row["turnover_amount"] * row["rate_primary_per_mille"] / 1000

        if premium_type == "minimum_deposit":
            return {
                "method": "rate_minimum",
                "estimated": calc * 0.8,
                "reason": "turnover × rate × 0.8",
            }

        return {
            "method": "rate",
            "estimated": calc,
            "reason": "turnover × rate",
        }

    if premium_type == "flat" and row.get("premium_amount") and row["premium_amount"] < 100000:
        df = pd.DataFrame([row])
        df = add_features(df)

        if not df[features].isna().any(axis=1).iloc[0]:
            pred = model.predict(df[features])[0]
            return {
                "method": "ml",
                "estimated": float(pred),
                "reason": "ML model (SME flat)",
            }

    return {
        "method": "fallback",
        "estimated": None,
        "reason": "insufficient data / large risk",
    }


def predict_product(data):
    if data.get("product_family") and data.get("product_family") != "nieustalone":
        return {
            "product_family": data.get("product_family"),
            "confidence": "high",
            "reason": "product_family provided in input",
        }

    text = " ".join(
        [
            data.get("insured_activity") or "",
            data.get("scope_of_insurance") or "",
            data.get("insured_products") or "",
        ]
    ).lower()

    if any(x in text for x in ["praw", "doradzt", "księg", "architekt", "projekt", "inżynier"]):
        return {
            "product_family": "oc_zawodowe",
            "confidence": "medium",
            "reason": "wykryto sygnały działalności zawodowej",
        }

    if any(x in text for x in ["produkt", "produkc", "sprzedaż", "wyrób", "wykonane usługi", "completed operations"]):
        return {
            "product_family": "oc_produkt_lub_mieszane",
            "confidence": "medium",
            "reason": "wykryto sygnały produkcji, produktu lub wykonanych usług",
        }

    if any(x in text for x in ["nieruchomo", "posiadanie", "zarządzanie", "oc ogólna", "prowadzonej działalności"]):
        return {
            "product_family": "oc_ogolne",
            "confidence": "medium",
            "reason": "wykryto sygnały OC ogólnej",
        }

    return {
        "product_family": "nieustalone",
        "confidence": "low",
        "reason": "brak wystarczających sygnałów",
    }


@app.get("/")
def root():
    return {"status": "API działa"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/estimate")
def estimate_endpoint(policy: PolicyInput):
    return estimate(policy.model_dump())


@app.post("/predict-product")
def predict_product_endpoint(policy: ProductInput):
    return predict_product(policy.model_dump())


@app.post("/underwrite")
def underwrite(policy: PolicyInput):
    data = policy.model_dump()

    product = predict_product(data)
    premium = estimate(data)

    return {
        "product_prediction": product,
        "premium_estimation": premium,
    }