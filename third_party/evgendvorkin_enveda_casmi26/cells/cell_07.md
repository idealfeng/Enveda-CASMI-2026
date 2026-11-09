## 4. Dataset Mounts — External Assets & Checkpoints

Находит подключённые Kaggle datasets по характерным файлам вместо угадывания mount paths.

- **V4G**: воспроизводимые исходники, checkpoints и пулы.
- **POP**: PubChem и natural-product priors.
- **PANEL**: benchmark dataset (в inference не анализируется, но включён в source inventory).
- **TABLE**: справочные external reference spectra.
- **FOLD**: пять fold-safe FPNet checkpoints.

Если `FOLD` отсутствует, notebook завершается до дорогостоящего inference.
