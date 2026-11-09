## 24. Final Audit — Submission, Dataset Hashes & Receipt

Проверяет итоговый submission и собирает полный provenance для будущих воспроизведений.

- Сверяет `molecule_id`, ограничения 1–25 и uniqueness metric identities.
- Проверяет согласованность E004 → E006 → Rank-2.
- Хеширует подключённые datasets, manifests и output files.
- Сохраняет `v43_execution_receipt.json` и инвентаризацию `v43_mounted_input_hashes.json`.

Сам audit не меняет предсказания; public MRR здесь не вычисляется.
