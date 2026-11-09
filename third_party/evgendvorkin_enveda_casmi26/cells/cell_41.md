## 21. Fragment Gap — MetFrag-Lite Without Forward Coverage

Вычисляет независимое объяснение фрагментных пиков для blind spots forward models.

- Встраивает исходный `frag_rescore.py` (MetFrag-lite) с numba-кешированием.
- Учитывает до двух разрывов связей, ion/adduct carriers и hydrogen shifts.
- Применяет расчёт только когда отсутствует GLACIER и finite ICEBERG evidence.
- Сохраняет per-candidate scores в `FRAG_GAP`; ошибка приводит к штатному fallback.

Этот scorer не заменяет GLACIER, а закрывает пробелы покрытия.
