## 19. Metric Fusion — Unique Identity Voting

Проверяет эффект устранения duplicate-vote bias при двух-engine fusion.

- Считает не более одного голоса на metric identity внутри каждого engine.
- Уплотняет уникальные ranks перед weighted RRF.
- Возвращает shortlist, учитывая GLACIER rerank и metric-safe fill.
- Сохраняет `submission_reference.csv` и `experiment_audit.csv/json`.

Это исходный экспериментальный overlay, а не ручной подбор новых весов.
