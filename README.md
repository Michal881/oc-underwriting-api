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
    "status": "ok",
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

- Jeśli `OPENAI_API_KEY` jest ustawiony, backend wywołuje OpenAI Python SDK (`client.beta.chat.completions.parse`) i wymusza odpowiedź zgodną z modelem Pydantic `LlmEstimationOutput`.
- Parsing odbywa się wyłącznie przez structured output SDK (brak primary path opartego o `output_text` i brak ręcznego parsowania free-form JSON).
- `llm_estimation.status="ok"` jest zwracane wyłącznie wtedy, gdy OpenAI zwróci poprawnie sparsowany obiekt Pydantic.
- `premium_estimation` pozostaje deterministycznym źródłem ML/reguł i nie jest podmieniane/fabrykowane przez `llm_estimation`.
- Gdy `OPENAI_API_KEY` nie jest skonfigurowany:
  - `status=disabled`,
  - wszystkie pola kwotowe ustawione na `null`,
  - `reason="OPENAI_API_KEY not configured"`,
  - `hitl_required=true`.
- Gdy wywołanie OpenAI lub structured parsing kończy się błędem:
  - `status=error`,
  - bezpieczny komunikat błędu (bez fallbackowych/fikcyjnych wartości składki),
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
