## 18. Metric-Safe Tail — Overflow & DreaMS Recovery

Чистит финальный candidate list и заполняет только освобождённые позиции.

- Сохраняет исходный `baseline_submission.csv`.
- Удаляет invalid/metric-equivalent structures без ухудшения старых ranks.
- Добирает кандидатов из fusion overflow, base tail, Engine 2 и PubChem.
- При наличии DreaMS добавляет подходящие по neutral mass structures.
- Создаёт `candidate_audit.csv/json` и hashes.

Никакой скрытой ручной разметки или подглядывания в test labels.
