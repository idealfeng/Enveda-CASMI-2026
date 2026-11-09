## 11. Library Preparation — Spectrum Cache & External References

Готовит training spectra cache и расширяет библиотечное свидетельство внешними спектрами.

- Создаёт symlinks на pool features и training-structure assets.
- Строит `work` cache из `train.parquet`.
- Подключает заранее проверенные external reference spectra из Natural Product Knowledge Table.
- Контролирует hash pins и совместимость записей; при ошибке может откатиться на исходную библиотеку.

В отличие от EDA-блоков это непосредственно влияет на retrieval evidence.
