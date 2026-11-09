## 5. Model Assets — Fold FPNet, Priors & Compatibility

Фиксирует основную конфигурацию ранжирования и проверяет источники моделей и химических priors.

- Проверяет SHA256 пяти fold-safe FPNet checkpoints.
- Подключает popularity, depositor-source, natural-product, LOTUS и synonym signals.
- Загружает пути v3/v4 моделей, candidate pools, PubChem и simulator wheels.
- Проверяет manifest файлов и совместимость RDKit 2025.3.6 для forward simulators.
- Сохраняет авторский **шестой PubChem slot на rank 24** поверх пяти основных слотов, без каких-либо изменений.

Исполняемый блок полностью идентичен исходной версии автора.
