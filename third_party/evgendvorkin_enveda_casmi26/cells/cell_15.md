## 8. Smoke Switch — Fast Commit vs Full Rerun

Разделяет быстрый commit и полноценный scoring rerun.

- Сверяет сигнатуру visible dummy test и переменную `KAGGLE_IS_COMPETITION_RERUN`.
- В smoke режиме запускает первые **12** молекул и снижает `ICE_BUDGET` до 300.
- В scoring режиме запускает **все** молекулы без smoke-ограничения.
- Сохраняет sample submission для всех обязательных `molecule_id`.

Visible smoke — только тест работоспособности, не оценка качества модели.
