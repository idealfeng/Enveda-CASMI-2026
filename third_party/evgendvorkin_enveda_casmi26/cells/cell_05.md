## 3. Competition Inputs — File Discovery

Определяет расположение официальных файлов соревнования без жёсткой привязки к единственному варианту пути.

- Ищет `train.parquet`, `test.parquet` и `sample_submission.csv`.
- Создаёт `DATA`, `TRAIN_PATH`, `TEST_PATH` и `SAMPLE_PATH`.
- Допускает явное переопределение путей теста и шаблона через переменные окружения.

В этой ячейке не читаются метки hidden test.
