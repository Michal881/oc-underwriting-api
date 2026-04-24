import json
import logging
import os
from json import JSONDecoder
from typing import Literal, Optional
from urllib import error, request

import joblib
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
LLM_LOG_TRUNCATE_CHARS = 1000


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
    status: Literal["ok", "disabled", "error", "fallback"]
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


def _extract_first_json_object(text: str) -> Optional[dict]:
    candidate = (text or "").strip()
    if not candidate:
        return None

    try:
        obj = json.loads(candidate)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    decoder = JSONDecoder()
    for index, char in enumerate(candidate):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(candidate[index:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue

    return None


def _truncate_for_log(value: str, max_chars: int = LLM_LOG_TRUNCATE_CHARS) -> str:
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}...<truncated>"


def _clean_llm_json_text(text: str) -> str:
    candidate = (text or "").strip()
    if not candidate:
        return ""

    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()

    first_brace = candidate.find("{")
    last_brace = candidate.rfind("}")
    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        candidate = candidate[first_brace : last_brace + 1]

    return candidate.strip()


def _extract_llm_data(parsed_response: dict) -> tuple[Optional[dict], str]:
    if not isinstance(parsed_response, dict):
        return None, ""

    output_parsed = parsed_response.get("output_parsed")
    if isinstance(output_parsed, dict):
        return output_parsed, json.dumps(output_parsed, ensure_ascii=False)

    for item in parsed_response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if isinstance(content.get("parsed"), dict):
                parsed_obj = content["parsed"]
                return parsed_obj, json.dumps(parsed_obj, ensure_ascii=False)

    if isinstance(parsed_response.get("output_text"), str):
        text = parsed_response["output_text"]
        cleaned = _clean_llm_json_text(text)
        extracted = _extract_first_json_object(cleaned)
        return extracted, cleaned

    return None, ""


def _is_effectively_empty_policy(policy_data: dict) -> bool:
    fields_to_check = [
        "product_family",
        "insured_activity",
        "scope_of_insurance",
        "insured_products",
        "sum_guaranteed_amount",
        "turnover_amount",
        "rate_primary_per_mille",
        "premium_amount",
        "deductible_amount",
    ]
    for key in fields_to_check:
        value = policy_data.get(key)
        if isinstance(value, str) and value.strip():
            return False
        if value not in (None, ""):
            return False
    return True


def _heuristic_estimate(policy_data: dict, premium_estimation: dict) -> Optional[float]:
    ml_or_rules = premium_estimation.get("estimated")
    if isinstance(ml_or_rules, (int, float)):
        return float(ml_or_rules)
    if isinstance(policy_data.get("premium_amount"), (int, float)):
        return float(policy_data["premium_amount"])
    if isinstance(policy_data.get("turnover_amount"), (int, float)) and isinstance(
        policy_data.get("rate_primary_per_mille"), (int, float)
    ):
        return float(policy_data["turnover_amount"]) * float(policy_data["rate_primary_per_mille"]) / 1000
    if isinstance(policy_data.get("sum_guaranteed_amount"), (int, float)):
        return float(policy_data["sum_guaranteed_amount"]) * 0.003
    return None


def generate_llm_estimation(policy_data, product_prediction, premium_estimation) -> LLMEstimation:
    api_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    logger.info(
        "Starting LLM estimation. openai_api_key_present=%s model=%s",
        bool(api_key),
        model_name,
    )
    if not api_key:
        return _fallback_llm_estimation("OPENAI_API_KEY not configured", premium_estimation)

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
            "Return ONLY valid JSON. No text. No markdown. No explanations. "
            "JSON object must be exactly: "
            "{"
            '"estimated_premium":number,'
            '"confidence":"low|medium|high",'
            '"reason":"string"'
            "}. "
            "Provide a speculative, non-binding HITL estimate. "
            "If data is incomplete, still provide a rough estimate unless the policy input is completely empty. "
            "Reason must explicitly say this estimate is indicative only and requires underwriter review."
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
            raw_response = json.dumps(parsed, ensure_ascii=False)
            logger.info("Raw OpenAI response (truncated): %s", _truncate_for_log(raw_response))
            output_text = parsed.get("output_text") if isinstance(parsed, dict) else None
            logger.info(
                "LLM response diagnostics: model=%s output_text_length=%s",
                model_name,
                len(output_text) if isinstance(output_text, str) else 0,
            )
            llm_data, parsed_input = _extract_llm_data(parsed)
            logger.info("Exact LLM content being parsed: %s", parsed_input)
            if llm_data is None:
                return _fallback_llm_estimation(
                    (
                        "OpenAI response could not be parsed into structured JSON; indicative fallback prepared for "
                        f"HITL only. Raw LLM text: {_truncate_for_log((parsed_input or output_text or '').strip())}"
                    ),
                    premium_estimation,
                )

            est = llm_data.get("estimated_premium")
            if not isinstance(est, (int, float)):
                if _is_effectively_empty_policy(policy_data):
                    est = 0.0
                else:
                    est = _heuristic_estimate(policy_data, premium_estimation)
            if isinstance(est, (int, float)):
                est = round(float(est), 2)
            low = llm_data.get("premium_range_low")
            high = llm_data.get("premium_range_high")
            if not isinstance(low, (int, float)) and isinstance(est, (int, float)):
                low = round(est * 0.8, 2)
            if not isinstance(high, (int, float)) and isinstance(est, (int, float)):
                high = round(est * 1.2, 2)

            reason = str(llm_data.get("reason") or "").strip() or "Indicative only, non-binding estimate."
            if "underwriter review" not in reason.lower():
                reason = f"{reason} Requires underwriter review."

            normalized = {
                "status": "ok",
                "estimated_premium": est if isinstance(est, (int, float)) else None,
                "premium_range_low": round(float(low), 2) if isinstance(low, (int, float)) else None,
                "premium_range_high": round(float(high), 2) if isinstance(high, (int, float)) else None,
                "confidence": llm_data.get("confidence") if llm_data.get("confidence") in {"low", "medium", "high"} else "low",
                "reason": reason,
                "missing_data": llm_data.get("missing_data") if isinstance(llm_data.get("missing_data"), list) else [],
                "hitl_required": True,
            }
            return LLMEstimation.model_validate(normalized)
    except (json.JSONDecodeError, ValueError):
        return _fallback_llm_estimation(
            "Invalid OpenAI JSON payload; indicative fallback prepared for HITL only.",
            premium_estimation,
        )
    except (error.HTTPError, error.URLError, Exception):
        return _fallback_llm_estimation(
            "OpenAI exception occurred; indicative fallback prepared for HITL only.",
            premium_estimation,
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
