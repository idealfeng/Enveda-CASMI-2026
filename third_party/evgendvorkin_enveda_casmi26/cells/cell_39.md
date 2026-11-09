## 20. Frozen Reproduction — E004 Postflight Audit

Фиксирует точный контрольный output базового E004 и входные candidate lists.

- Проверяет согласованность smoke/full execution и обязательных строк submission.
- Контролирует GPU-статусы и RDKit обеих forward stages.
- Сохраняет `e004_candidate_inputs.json` и SHA256 промежуточных файлов.
- Создаёт `e004_verification.json` с provenance.

Это контроль воспроизводимости для последующего E006 overlay.
