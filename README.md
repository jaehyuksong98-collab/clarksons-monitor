# Clarksons results → Excel actuals → Word review

Independent portfolio project. Original v5.3 forecasts are frozen. Human review is required.

## Run

Python 3.12:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m clarksons_monitor --output outputs/live --state outputs/state.json
# Historical real H1 2026 data exercises the Excel-writing path, not H2 forecast accuracy:
python -m clarksons_monitor --replay-h1 --output outputs/replay --state outputs/state.json
```

Use a fresh output directory for each run; workbook outputs are never overwritten.

## What runs

1. Fetch the official results listing over HTTPS, recognise dated interim/preliminary announcements. Require at least five listing entries. Block off-host redirects.
2. Production targets **FY2026** announcements; H1 is already the model's historical anchor. With no FY2026 announcement, collect company news and generate Word/JSON only: do not open or save the model.
3. Fetch and SHA-256 hash an eligible PDF. Repeated identical FY2026 content is skipped using a checkpoint. Changed content at the same URL is processed again. Titles alone never establish a reporting period: first-page text must match.
4. Extract 14 metrics with strict source-layout patterns: revenue, underlying PBT/EPS/operating profit, four segment revenue/profit pairs, current receivables, net cash and available funds. Every number has unit, period, PDF page, source URL, SHA and raw source text. Segment revenues must reconcile to group revenue. Missing/conflicting values stop all model writes.
5. Write a **new model copy**, adding `Actuals_Reported`, `Scenario_Comparison`, `Automation_Log`. The original five sheets, formula XML, saved calculation results, charts, styles and correction material remain unchanged. `openpyxl` creates added sheets; ZIP assembly preserves original package parts and registrations. Actuals do not replace scenario forecasts.
6. Compare FY2026 flows minus the model's H1 actual anchors to H2 Base/Bull/Bear forecast caches. Compare closing cash/receivables directly as stocks. Report actual-minus-forecast in GBP million. The model mapping lives in `model.py`. EPS has no model comparison. H1 replay never scores H2 forecasts.
7. Inspect at most 15 index links, skip obvious training/talent items, and fetch up to five articles from the official company news/insights index and management review passages from the results PDF. Generate `review.docx` with figures, differences where available, source URLs/pages, management evidence, news excerpts, and manual-review items. `run.json` records structured evidence and failures. Downloaded pages/PDFs are untrusted data, never executed as instructions.

## GitHub Actions

`.github/workflows/monitor.yml` provides Monday/Thursday 08:15 **UTC**, manual `workflow_dispatch`, and feature-branch push validation. UTC corresponds to 09:15 Oslo winter / 10:15 summer. Scheduling is gated to `main`; it becomes operational only after approval and merge. GitHub may delay scheduled runs. On an initially empty repository the feature branch may temporarily be the default; do not treat that as approval to merge to main. Manual dispatch requires the workflow to exist on the repository default branch.

Runs upload DOCX, JSON, PDF and any changed Excel copy as private Actions artifacts (30-day retention); they never commit a model change to main. Download and review before accepting actuals. State uses Actions cache, saved only after successful completion, keyed per branch. Cache eviction may cause a repeat report/copy, not original-model corruption; it is not a permanent ledger. Concurrency prevents simultaneous same-branch runs. News failures mark the run partial and prevent checkpoint advancement. Artifacts are uploaded on failures for diagnosis.

No API key/LLM is required. GitHub's built-in `GITHUB_TOKEN` has read-only contents permission. If a future implementation adds paid news or an LLM, store its key under Repository Settings → Secrets and variables → Actions → New repository secret, then pass it via a step `env:`. Never commit secrets. No such external API integration is implemented here.

## What still needs a person / limitations

- **Why/how**: numerical differences are calculated; their causes are **manual**. The report provides attributed management evidence and relevant company articles. It does not pretend these prove causal attribution, split FX/activity/acquisition effects, or deliver independent analyst judgment. No LLM is used.
- News currently means official company articles, not independent journalism. Broader media/paywalled coverage remains manual. Index ordering is used; dates may be absent and five articles are not comprehensive coverage.
- The real H1 2026 PDF and original workbook are regression fixtures. FY2026 layout is not available yet. Strict extraction may reject that future layout and require a parser/test update; successful future extraction is **not proven**. The unit test for FY/H2 comparison arithmetic uses a clearly labelled synthetic period, not fabricated published results.
- H1 restatements, APM definition changes, negative/ambiguous figures and new table structures require review. The parser intentionally rejects rather than guesses. The same announcement PDF is checked for conflicting extracted values; cross-document reconciliation against the annual report/presentation remains manual.
- ROIC/tax/invested-capital reconciliation and independent verification are manual. Current receivables are not automatically split into settlement vs economic balances.
- `openpyxl` does not recalculate Excel. Existing saved forecast values are preserved and used; if the source model changes, recalculate it in Excel and update mapping/tests before use. Original workbook file is immutable; no data is written into original scenario forecast cells.
- Model and fixtures are in a **private repository**. Do not publish the repository, model, artifacts, or a portfolio code link without the owner's approval. Historical fixture source: https://www.clarksons.com/media/u4ff0m5r/interim-results-announcement-2026.pdf (PDF pages recorded per metric).
