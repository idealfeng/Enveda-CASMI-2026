## 16. Two-Engine Fusion — RRF & Forward Re-Rank

Комбинирует основной список с Engine 2 через reciprocal-rank fusion.

- Использует `ALPHA=0.6` и `KRR=3`.
- Сохраняет `PREFUSION_LISTS` и `FUSION_OVERFLOW`.
- Применяет предусмотренный source forward rerank с GLACIER-specific logic.
- Формирует обновлённый `submission.csv`.

Результат остаётся доступен как baseline для metric-aware overlay.
