## 14. Forward Evidence — ICEBERG, GLACIER & Proxies

Получает forward-spectrum evidence с помощью ICEBERG и GLACIER, включая author proxy-политику.

- Запускает модели в совместимых изолированных окружениях RDKit 2025.3.6.
- Собирает кандидатов из базового engine, PubChem и Engine 2.
- Выполняет ICEBERG/GLACIER scoring и фиксирует coverage/failures.
- Для молекул без обычного `[M+H]+` создаёт предусмотренные источником GLACIER proxy spectra.
- Сохраняет `ICE_SCORES` и GLACIER-сигналы для последующего rerank.

Это наиболее тяжёлый вычислительный блок; его код и сценарии subprocess сохранены.
