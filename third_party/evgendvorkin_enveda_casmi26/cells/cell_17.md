## 9. Engine 2 — Retrieval, BIO/AFIX & Two Rankers

Создаёт независимый Engine 2 в отдельном процессе с двумя rankers и расширенными источниками кандидатов.

- Встраивает и запускает исходные модули `pv.py`, `pv_fp.py` и `casmi_engine.py`.
- Использует library/analog retrieval, BIO, AFIX, структурные fingerprints и fragment evidence.
- Учитывает добавленные автором источники стандартизированных ChEBI/LIPID MAPS и PubChemLite.
- Строит уникальные ranked candidates и сохраняет выход Engine 2 для fusion.

Embedded Python-код сохранён целиком, без сокращений.
