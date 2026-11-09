## 12. Main Engine — Full FPNet & V1FE Rankers

Загружает основной candidate engine и ансамбль LightGBM rankers.

- Инициализирует `Library`, `Pool` и FPNet full1 (с предусмотренным fallback).
- Использует V1FE family features для спектральной и структурной оценки кандидатов.
- Проверяет derivation self-test и совместимость RDKit.
- Строит функцию `rank_score()` с точной проверкой наличия всех feature columns.

Этот engine формирует основную независимую ranked list.
