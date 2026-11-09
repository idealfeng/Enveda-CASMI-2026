## 13. Candidate Generation — Base Lists & Popularity

Прогоняет основной engine по тестовым молекулам и формирует initial candidate lists.

- Объединяет измеренные MS/MS spectra по `molecule_id`, вычисляет neutral mass.
- Генерирует и ранжирует pool/generated candidates.
- Добавляет popularity prior к pool-кандидатам (`POOLPOP_MU=0.15`).
- Сохраняет `BASE`, число inference errors и `BASE_TAIL_CANDIDATES`.

Важен не только top-1, но и сохранение overflow для финального top-25.
