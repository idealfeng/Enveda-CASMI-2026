## 22. Adaptive Fusion — E006, ICEBERG & GLACIER Proxy

Финальная обработка E006 собирает metric-aware shortlist и выбирает forward evidence для каждого случая.

- Реконструирует same-run E004 control и сравнивает его с сохранённым submission.
- Работает с окном **40** metric-unique candidates.
- При наличии GLACIER использует основной rerank; в blind spots подключает ICEBERG или `FRAG_GAP`.
- Сохраняет proxy-aware GLACIER+ICEBERG logic из источника.
- Создаёт `experiment_verification.json` и factorial audit.

Это основной final reranking исходной версии; остальные настройки и slot policy сохранены без изменений.
