import json
import os
from typing import Literal, Optional
from urllib import error, request

import joblib
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


bundle = joblib.load("premium_model.joblib")
model = bundle["model"]
features = bundle["features"]

app = FastAPI(title="OC Underwriting API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PolicyInput(BaseModel):
    product_family: Optional[str] = None
    insured_activity: Optional[str] = None
    scope_of_insurance: Optional[str] = None
    insured_products: Optional[str] = None

    sum_guaranteed_amount: Optional[float] = None
    turnover_amount: Optional[float] = None
    rate_primary_per_mille: Optional[float] = None
    premium_amount: Optional[float] = None
    deductible_amount: Optional[float] = None
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


class LLMEstimation(BaseModel):
    status: Literal["enabled", "disabled", "error", "fallback"]
    estimated_premium: Optional[float]
    premium_range_low: Optional[float]
    premium_range_high: Optional[float]
    confidence: Literal["low", "medium", "high"]
    reason: str
    missing_data: list[str] = Field(default_factory=list)
    hitl_required: bool = True


class UnderwriteResult(BaseModel):
    product_prediction: dict
    premium_estimation: dict
    llm_estimation: LLMEstimation


def classify_premium(row):
    if row.get("turnover_amount") and row.get("rate_primary_per_mille"):
        calc = row["turnover_amount"] * row["rate_primary_per_mille"] / 1000
        if row.get("premium_amount"):
            ratio = row["premium_amount"] / calc if calc != 0 else None
            if ratio:
                if 0.7 < ratio < 0.9:
                    return "minimum_deposit"
                if 0.9 < ratio < 1.1:
                    return "pure_rate"
                if ratio > 2:
                    return "minimum_override"
        return "rate"

    if row.get("premium_amount"):
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
        df[f"kw_{kw}"] = df["insured_activity"].str.lower().str.contains(kw).astype(int)

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

    if any(x in text for x in ["produkt", "produkc", "sprzedaż", "wyrób", "wykonane usługi"]):
        return {
            "product_family": "oc_produkt_lub_mieszane",
            "confidence": "medium",
            "reason": "wykryto sygnały produktu / produkcji",
        }

    if any(x in text for x in ["nieruchomo", "posiadanie", "zarządzanie", "oc ogólna"]):
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


def _disabled_llm_estimation(reason: str) -> LLMEstimation:
    return LLMEstimation(
        status="disabled",
        estimated_premium=None,
        premium_range_low=None,
        premium_range_high=None,
        confidence="low",
        reason=reason,
        missing_data=[],
        hitl_required=True,
    )


def _error_llm_estimation(reason: str) -> LLMEstimation:
    return LLMEstimation(
        status="error",
        estimated_premium=None,
        premium_range_low=None,
        premium_range_high=None,
        confidence="low",
        reason=reason,
        missing_data=[],
        hitl_required=True,
    )


def _fallback_llm_estimation(reason: str, premium_estimation: dict) -> LLMEstimation:
    base_estimate = premium_estimation.get("estimated")
    if isinstance(base_estimate, (int, float)):
        low = round(float(base_estimate) * 0.8, 2)
        high = round(float(base_estimate) * 1.2, 2)
    else:
        low = None
        high = None

    return LLMEstimation(
        status="fallback",
        estimated_premium=float(base_estimate) if isinstance(base_estimate, (int, float)) else None,
        premium_range_low=low,
        premium_range_high=high,
        confidence="low",
        reason=reason,
        missing_data=[],
        hitl_required=True,
    )


def generate_llm_estimation(policy_data, product_prediction, premium_estimation) -> LLMEstimation:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _disabled_llm_estimation("OPENAI_API_KEY not configured")

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": ["enabled", "fallback"]},
            "estimated_premium": {"type": ["number", "null"]},
            "premium_range_low": {"type": ["number", "null"]},
            "premium_range_high": {"type": ["number", "null"]},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "reason": {"type": "string"},
            "missing_data": {"type": "array", "items": {"type": "string"}},
            "hitl_required": {"type": "boolean"},
        },
        "required": [
            "status",
            "estimated_premium",
            "premium_range_low",
            "premium_range_high",
            "confidence",
            "reason",
            "missing_data",
            "hitl_required",
        ],
    }

    prompt = {
        "policy": {
            "product_family": policy_data.get("product_family"),
            "insured_activity": policy_data.get("insured_activity"),
            "scope_of_insurance": policy_data.get("scope_of_insurance"),
            "sum_guaranteed_amount": policy_data.get("sum_guaranteed_amount"),
            "premium_amount": policy_data.get("premium_amount"),
            "turnover_amount": policy_data.get("turnover_amount"),
            "rate_primary_per_mille": policy_data.get("rate_primary_per_mille"),
            "deductible_amount": policy_data.get("deductible_amount"),
            "usa_canada_included": policy_data.get("usa_canada_included"),
        },
        "product_prediction": product_prediction,
        "premium_estimation": premium_estimation,
        "instructions": (
            "Provide indicative, non-binding premium estimate for human-in-the-loop underwriting review. "
            "The estimate is allowed even when premium_estimation.estimated is null. "
            "Return JSON only. Set hitl_required=true. "
            "Reason must explicitly say estimate is indicative only and requires underwriter review."
        ),
    }

    body = {
        "model": model_name,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": json.dumps(prompt, ensure_ascii=False)}],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "llm_estimation",
                "schema": schema,
                "strict": True,
            }
        },
    }

    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=20) as response:
            parsed = json.loads(response.read().decode("utf-8"))
            content = parsed.get("output_text")
            if not content:
                return _fallback_llm_estimation(
                    "OpenAI returned empty structured payload; indicative fallback prepared for HITL only.",
                    premium_estimation,
                )

            llm_data = json.loads(content)
            llm_data["hitl_required"] = True
            if llm_data.get("status") not in ["enabled", "fallback"]:
                llm_data["status"] = "enabled"

            return LLMEstimation.model_validate(llm_data)
    except (json.JSONDecodeError, ValueError):
        return _fallback_llm_estimation(
            "Invalid OpenAI JSON payload; indicative fallback prepared for HITL only.",
            premium_estimation,
        )
    except error.HTTPError:
        return _error_llm_estimation(
            "LLM service unavailable; unable to produce indicative estimate right now."
        )
    except error.URLError:
        return _error_llm_estimation(
            "Network error while contacting LLM service; try again later."
        )


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


@app.post("/underwrite", response_model=UnderwriteResult)
def underwrite(policy: PolicyInput):
    data = policy.model_dump()
    product_prediction = predict_product(data)
    premium_estimation = estimate(data)
    llm_estimation = generate_llm_estimation(data, product_prediction, premium_estimation)
    return {
        "product_prediction": product_prediction,
        "premium_estimation": premium_estimation,
        "llm_estimation": llm_estimation,
    }
