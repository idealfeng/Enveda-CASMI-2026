"""Run the actual pairwise-dominance changed cell and existing score replay."""
from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'scripts/check_evidence_early_20261114.py'


def main():
    source=BASE.read_text(encoding='utf-8')
    for old,new in {
        'import evidence_early_overlay_20261114 as overlay':'import evidence_pairwise_overlay_20261114 as overlay',
        "OUT=ROOT/'reports/optimization_20261114/evidence_early_components'":"OUT=ROOT/'reports/optimization_20261114/evidence_pairwise_components'",
        "ARMS=('gl_evidence_early','dual_evidence_agreement')":"ARMS=('dual_evidence_agreement',)",
        "stage=ROOT/'submission/optimization_20261114'/arm":"stage=ROOT/'submission/optimization_20261114'/arm/'revision2'",
        "ROOT/'scripts/evidence_early_overlay_20261114.py'":"ROOT/'scripts/evidence_pairwise_overlay_20261114.py'",
    }.items():
        if old not in source:raise ValueError('Missing source anchor')
        source=source.replace(old,new)
    ast.parse(source)
    scope=dict(__name__='_pairwise_components',__file__=str(BASE))
    exec(compile(source,str(BASE),'exec'),scope)
    scope['main']()


if __name__=='__main__':main()
