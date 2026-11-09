# Snapshot of the fragment check's own output (V2 order) before the m1 merge overwrites submission.csv.
import shutil
if (ROOT / 'submission.csv').is_file():
    shutil.copy2(ROOT / 'submission.csv', ROOT / 'submission_physical_V2.csv')
