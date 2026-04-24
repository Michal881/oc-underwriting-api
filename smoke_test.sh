#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"

PAYLOAD='{
  "product_family": "oc_zawodowe",
  "insured_activity": "syntetyczne usługi doradcze",
  "scope_of_insurance": "syntetyczny zakres OC zawodowej",
  "sum_guaranteed_amount": 2500000,
  "premium_amount": null,
  "turnover_amount": null,
  "rate_primary_per_mille": null,
  "deductible_amount": 5000,
  "covers_general_liability": 1,
  "covers_professional_liability": 1,
  "covers_product_liability": 0,
  "covers_completed_operations": 0,
  "covers_pure_financial_loss": 1,
  "covers_employers_liability": 0,
  "covers_documents_loss": 1,
  "covers_subcontractors": 0
}'

RESPONSE=$(curl -sS -X POST "$BASE_URL/underwrite" -H 'Content-Type: application/json' -d "$PAYLOAD")

echo "$RESPONSE" | python -c 'import json,sys
obj=json.load(sys.stdin)
assert "llm_estimation" in obj, "Missing llm_estimation"
llm=obj["llm_estimation"]
for key in ["status","estimated_premium","premium_range_low","premium_range_high","confidence","reason","missing_data","hitl_required"]:
    assert key in llm, f"Missing llm_estimation.{key}"
assert llm["hitl_required"] is True, "hitl_required must be true"
print("smoke test passed")'
