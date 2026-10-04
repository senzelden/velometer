# M6 rulings

## Task 1a

Items of the M5 known follow-ups closed by ruling instead of a fix (one line each: item, why,
cost).

- T11, English Status column: no change. The cell already prints the country's `status` from
  `trust.yaml` (`CountryFact.status`), and the table lists trusted countries only, so the value is
  "trusted" by design (a pending country must not appear in the published methodology, M5 spec
  section 3.3). Cost: none; the follow-up described a state the code had already left.
- T6, "the reconcile `--check` assertion is weak": `tests/test_report_data.py` has no `--check`
  assertion, so the nearest one was tightened instead: `test_reconcile_check_exits_1_until_the_gap_is_explained`
  now matches the whole stderr line `missing explanation: ### berlin/cc_network_km`, not the bare key
  (the exit code was already asserted). Cost: if the follow-up meant another test, it stays open.
