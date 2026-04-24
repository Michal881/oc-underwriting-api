import logging
import os
from typing import Literal, Optional

import joblib
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


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
    status: Literal["ok", "disabled", "error"]
    estimated_premium: Optional[float]
    premium_range_low: Optional[float]
    premium_range_high: Optional[float]
    confidence: Literal["low", "medium", "high"]
    reason: str
    explanation: str
    missing_data: list[str] = Field(default_factory=list)
    hitl_required: bool = True


class UnderwriteResult(BaseModel):
    product_prediction: dict
    premium_estimation: dict
    llm_estimation: LLMEstimation


class LlmEstimationOutput(BaseModel):
    status: Literal["ok"]
    estimated_premium: float
    premium_range_low: float
    premium_range_high: float
    confidence: Literal["low", "medium", "high"]
    reason: str
    missing_data: list[str] = Field(default_factory=list)
    hitl_required: Literal[True]


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


def _error_llm_estimation(reason: str) -> LLMEstimation:
    return LLMEstimation(
        status="error",
        estimated_premium=None,
        premium_range_low=None,
        premium_range_high=None,
        confidence="low",
        reason=reason,
        explanation=(
            "No valid premium estimate could be produced from either LLM output or deterministic inputs. "
            "HITL review is required because this API provides only indicative, non-binding guidance."
        ),
        missing_data=[],
        hitl_required=True,
    )


def _disabled_llm_estimation(reason: str) -> LLMEstimation:
    return LLMEstimation(
        status="disabled",
        estimated_premium=None,
        premium_range_low=None,
        premium_range_high=None,
        confidence="low",
        reason=reason,
        explanation=(
            "LLM estimation is disabled because OPENAI_API_KEY is not configured. "
            "HITL review is required for any underwriting decision."
        ),
        missing_data=[],
        hitl_required=True,
    )


def generate_llm_estimation(policy_data, product_prediction, premium_estimation) -> LLMEstimation:
    api_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    logger.info(
        "Starting LLM estimation. openai_api_key_present=%s model=%s",
        bool(api_key),
        model_name,
    )
    if not api_key:
        return _disabled_llm_estimation("OPENAI_API_KEY not configured")

    try:
        client = OpenAI(api_key=api_key)
        completion = client.beta.chat.completions.parse(
            model=model_name,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an underwriting assistant. Return a strictly parsed estimate using the provided schema. "
                        "The estimate must be indicative only and always require underwriter review (HITL). "
                        "Set hitl_required=true and status='ok'."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Policy data: {policy_data}\n"
                        f"Product prediction: {product_prediction}\n"
                        f"Premium estimation context: {premium_estimation}\n"
                        "Provide an indicative, non-binding premium estimate with rationale and missing_data."
                    ),
                },
            ],
            response_format=LlmEstimationOutput,
        )

        parsed_output = completion.choices[0].message.parsed if completion.choices else None
        if parsed_output is None:
            return _error_llm_estimation(
                "OpenAI structured parsing returned no parsed object. HITL review remains required."
            )

        reason = parsed_output.reason.strip() if parsed_output.reason else "Indicative only estimate."
        if "underwriter review" not in reason.lower() and "hitl" not in reason.lower():
            reason = f"{reason} Requires underwriter review."

        return LLMEstimation(
            status="ok",
            estimated_premium=round(float(parsed_output.estimated_premium), 2),
            premium_range_low=round(float(parsed_output.premium_range_low), 2),
            premium_range_high=round(float(parsed_output.premium_range_high), 2),
            confidence=parsed_output.confidence,
            reason=reason,
            explanation=(
                "Data used: policy input, product prediction, and deterministic premium_estimation context. "
                "Value source: parsed OpenAI structured output. "
                "HITL review is required because this estimate is indicative and non-binding."
            ),
            missing_data=parsed_output.missing_data,
            hitl_required=True,
        )
    except Exception as exc:
        logger.exception("OpenAI structured estimation failed: %s", exc.__class__.__name__)
        return _error_llm_estimation(
            "OpenAI call or structured parsing failed. No LLM estimate was produced; HITL review required."
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
