## 17. Metric Identity — Canonicalization & Safe Extension

Создаёт согласованное с соревнованием представление identity кандидата.

- Удаляет stereochemistry перед tautomer canonicalization.
- Получает canonical InChIKey14 и heavy-atom composition.
- Кеширует `metric_identity()`.
- Определяет `safe_extend()`, `first_ranks()` и проверку монотонности рангов.

Так избегаем повторных metric-equivalent структур в top-25.
