## 10. PubChem Channel — Fingerprints & Chemical Priors

Создаёт независимый PubChem retrieval channel с несколькими fingerprint representations и chemical priors.

- Запускает PubChem FPNet A+B и ансамбль пяти fold-safe FPNet models.
- Учитывает popularity, natural-product, LOTUS, synonyms и depositor-source evidence.
- Подключает дополнительные PubChem candidate supplements и делает mass-filtered поиск.
- Сохраняет ранжированные предложения PubChem и диагностику gate.

PubChem — отдельный кандидатный источник, а не подмена базового engine.
