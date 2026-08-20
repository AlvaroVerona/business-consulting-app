# Manual test scenario: Fermento (Malasaña wine bar)

A fictional business, invented for live end-to-end testing of the app
against a real running Ollama model — this is not part of the hermetic
pytest suite (`sidecar/tests`, which uses `FakeLLM` stand-ins). It exists to
answer "is the output actually useful for a real question", not "is the
code correct" (that's what the automated tests are for).

## The scenario

Two technically-trained founders (an enologist and a food-science/
biochemistry engineer) open a natural-wine bar in Malasaña, Madrid in March
2026. Strong first three months, then a real slump from June onward driven
by three compounding causes: small direct-import suppliers with unreliable
lead times, spoilage waste on opened natural wines (short shelf life once
opened, no added sulfites), and the seasonal Madrid-in-August effect on a
nightlife-dependent business. Reduced opening hours from July onward. One
unexplored opportunity mentioned in passing (a nearby hotel asking about
private tastings) that the founders haven't acted on.

This is deliberately not a toy dataset — it's built so the deterministic
financial engine, the deterministic concern/opportunity detection, and the
LLM-driven agents (business understanding, hypothesis generation, executive
synthesis) all have real signal to work with, and so a bad or hallucinated
answer is recognizable as such against ground truth in the documents.

## Files

- `memo_fermento.md` — founders' narrative memo. Feeds `BusinessUnderstandingAgent`
  and Quick Answer's evidence citations. Note it's written in Spanish.
- `financiero_fermento.csv` — 6 months of revenue/COGS/opex (March-August 2026).
  Feeds the deterministic financial engine (`analysis/financial.py`,
  `period_extractor.py`). Uses Peninsular Spanish column headers
  (`coste_ventas`, not `costo_de_ventas`) — this exposed a real gap in
  `period_extractor.py`'s alias list (only had the Latin American Spanish
  term), fixed in the same change that added this fixture.
- `carta_fermento.csv` — 16-wine list across Spain/France/Georgia/Argentina/
  Italy/Portugal with producer names, grape varieties, and glass/bottle
  pricing. Extra grounding material for evidence citations, not structured
  for the financial engine.

Expected financial pattern: revenue rises March→May, falls May→August; gross
margin degrades from ~40% to ~53% cost-of-sales ratio over the same period
(supplier substitutions at worse pricing + spoilage waste). Opex is close to
flat (~2,250-2,600€/month, mostly rent).

## How to replicate

Sidecar running locally (`cd sidecar && uv run uvicorn src.main:app --reload --port 8765`),
Ollama running with `llama3.1` pulled. From the repo root:

```bash
BASE=http://127.0.0.1:8765

COMPANY_ID=$(curl -s -X POST $BASE/companies \
  -H 'Content-Type: application/json' \
  -d '{"name": "Fermento", "industry": "Hostelería / vino natural"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

PROJECT_ID=$(curl -s -X POST $BASE/companies/$COMPANY_ID/projects \
  -H 'Content-Type: application/json' \
  -d '{"name": "Diagnóstico agosto 2026", "description": "Caída de ventas y márgenes desde junio"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

for f in memo_fermento.md financiero_fermento.csv carta_fermento.csv; do
  curl -s -X POST $BASE/projects/$PROJECT_ID/documents -F "file=@manual-tests/fermento-winebar/$f" > /dev/null
done

curl -s -X POST $BASE/projects/$PROJECT_ID/analysis/financial | python3 -m json.tool
curl -s -X POST $BASE/projects/$PROJECT_ID/concerns/detect | python3 -m json.tool
curl -s -X POST $BASE/projects/$PROJECT_ID/opportunities/detect | python3 -m json.tool
curl -s -X POST $BASE/projects/$PROJECT_ID/deep-analysis | python3 -m json.tool
curl -s -X POST $BASE/projects/$PROJECT_ID/issue-trees \
  -H 'Content-Type: application/json' \
  -d '{"question": "¿Por qué han caído las ventas y el margen desde junio?"}' | python3 -m json.tool
```

Or drive it through the packaged app (`open App/.build/app/BusinessConsultant.app`)
using the same company/project name and uploading the three files by hand.
