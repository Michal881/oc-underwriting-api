# OC Underwriting API

Demo API do predykcji produktu OC, estymacji składki ML/reguły oraz **indikatywnej estymacji LLM dla HITL**.

## Endpoint `/underwrite`

Zwraca trzy sekcje:

- `product_prediction` – klasyfikacja rodzaju produktu OC,
- `premium_estimation` – istniejąca estymacja ML/regułowa (bez zmian logiki),
- `llm_estimation` – estymacja indikatywna (niebinding) do review przez underwritera.

Przykładowy kształt odpowiedzi:

```json
{
  "product_prediction": {...},
  "premium_estimation": {...},
  "llm_estimation": {
    "status": "enabled",
    "estimated_premium": 18500,
    "premium_range_low": 16000,
    "premium_range_high": 22000,
    "confidence": "medium",
    "reason": "Indicative only, non-binding; requires underwriter review.",
    "missing_data": ["loss_history", "claims_frequency"],
    "hitl_required": true
  }
}
```

## Zachowanie LLM

- Jeśli `OPENAI_API_KEY` jest ustawiony, backend wywołuje OpenAI Responses API i wymusza JSON schema dla `llm_estimation`.
- LLM może zwrócić wskazanie składki nawet wtedy, gdy `premium_estimation.estimated` jest `null`.
- Gdy `OPENAI_API_KEY` nie jest skonfigurowany:
  - `status=disabled`,
  - wszystkie pola kwotowe ustawione na `null`,
  - `reason="OPENAI_API_KEY not configured"`,
  - `hitl_required=true`.
- Gdy wywołanie OpenAI kończy się błędem HTTP/sieci:
  - `status=error`,
  - bezpieczny komunikat błędu,
  - `hitl_required=true`.

## Uruchomienie

```bash
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Smoke test

`smoke_test.sh` sprawdza obecność `llm_estimation` oraz flagi `hitl_required` w odpowiedzi `/underwrite`.

```bash
./smoke_test.sh
```

## UI (`index.html`)

Widok prezentuje osobno:

- estymację ML/reguły,
- indikatywną estymację LLM,
- zakres składki,
- confidence,
- missing data,
- ostrzeżenie: "LLM estimate is indicative only and requires underwriter review."

Formularz zawiera też pole `deductible_amount` (franszyza redukcyjna).

## Bezpieczeństwo danych

W demonstracji używaj wyłącznie **syntetycznych scenariuszy** i nie wprowadzaj realnych danych klientów.
