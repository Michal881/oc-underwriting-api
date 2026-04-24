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

## Local static UI usage

The demo frontend is a single static file (`index.html`) and does not require any build tools or frontend dependencies.

### Option 1: open directly

1. In your file browser, open `index.html` from this repository.
2. The page calls the production endpoint directly:
   - `POST https://oc-underwriting-api.onrender.com/underwrite`

### Option 2: serve locally (recommended)

From the repository root:

```bash
python -m http.server 8080
```

Then open:

- `http://localhost:8080/index.html`

### Demo and safety notes

- Use only synthetic/anonymized examples in the UI.
- Results are support signals only and **not** a final underwriting decision.
- LLM output is indicative only and always requires human underwriter review (HITL).
- Never expose backend secrets (for example `OPENAI_API_KEY`) in frontend code.

