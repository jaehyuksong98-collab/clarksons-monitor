# Executed verification — 23 November 2026

- Original source model SHA-256: `ed6c63def51a044806153a97e6d0d8c8c57f3c8252befc6f80f1f82eeebd7048`.
- Local offline suite: 10 tests passed, including real PDF extraction, period mismatch, broken listing, invalid metric rejection, original package-byte preservation, cached forecast preservation, no-result/no-write, failure/no-checkpoint, and synthetic FY-to-H2 comparison arithmetic.
- Live official listing: no FY2026 announcement. Production returned `no_new_result`, generated news/Word output and did not produce an Excel file.
- Real H1 2026 replay: passed, 14 metrics with PDF pages and source hashes; an output Excel copy with three added sheets and a Word report were generated. H1 was NOT scored as H2/FY actuals.
- News collection: five official company articles, including the CFO appointment, Demeter Energy, Stegra, LME membership and Clarksons Securities Oslo commentary, were retrieved after filtering obvious training/talent posts.
- Initial GitHub Actions validation: https://github.com/jaehyuksong98-collab/clarksons-monitor/actions/runs/45270018134 — completed `success`. Dependency installation, 10 tests, live collection, historical replay and artifact upload passed.
- Initial local failure: workbook reconstruction omitted the original shared-strings relationship. Fixed by retaining original package registrations and adding only the new sheet registrations. The preservation regression test passes.
- Future FY2026 announcement extraction is unproven until that PDF exists. Numerical comparison arithmetic has unit-test coverage only. Causal attribution and independent media remain manual.

Artifacts are private and temporary; Actions artifacts retain outputs for 30 days. Main has not been created or updated. Twice-weekly production scheduling awaits approval/main; the new feature branch is temporarily the empty repository's default branch.
