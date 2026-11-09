## 7. Preflight — Input, RDKit & GPU Validation

Выполняет read-only проверку окружения до запуска отдельных GPU subprocesses.

- Требует **Python 3.12**, официальный RDKit 2026.03.3 и GPU T4.
- Сверяет `molecule_id` официальных test и sample submission.
- Сохраняет `E004_PREFLIGHT` для дальнейших asserts и provenance.
- Не создаёт CUDA-контекст в главном процессе.

Ошибки окружения обнаруживаются раньше затратного inference.
