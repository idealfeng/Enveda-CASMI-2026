"""Prepare a two-head ensemble on the confirmed MASS base, with no Na component.

This is a local-only alternative deployment. It does not alter an existing
Notebook, active manifest, submitted model, or cloud receipt.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import build_learned_head_variants_20261108 as inherited

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'submission/optimization_20261108/mass_heads_only_compact'


def main():
    if OUT.exists():
        raise FileExistsError('Preserve the alternative frozen stage')
    inherited_path = Path(inherited.__file__)
    inherited_sha = hashlib.sha256(inherited_path.read_bytes()).hexdigest()
    # Freeze the inherited, reviewed function and make the two mechanism choices
    # explicit. All remaining installation/observer/source-pin machinery is reused.
    original = inspect.getsource(inherited.build)
    old_combined = "    combined = kind == 'heads_na'"
    old_selected = "    selected = SEEDS if combined else (SEEDS[0 if kind == 'head_seed0' else 1],)"
    if original.count(old_combined) != 1 or original.count(old_selected) != 1:
        raise ValueError('Reviewed builder interface changed')
    adapted = original.replace(old_combined, '    combined = False', 1)
    adapted = adapted.replace(old_selected, '    selected = SEEDS', 1)
    namespace = dict(vars(inherited))
    exec(compile(adapted, 'reviewed_builder_heads_only_adaptation', 'exec'), namespace)
    namespace['build']('heads_only', compact=True)
    if hashlib.sha256(inherited_path.read_bytes()).hexdigest() != inherited_sha:
        raise ValueError('Inherited source changed during local preparation')
    (OUT/'builder_adaptation.json').write_text(json.dumps(dict(
        inherited_builder=str(inherited_path.relative_to(ROOT)),
        inherited_builder_sha256=inherited_sha,
        adapted_function_sha256=hashlib.sha256(adapted.encode()).hexdigest(),
        changes=['combined=False: always use the original 0.481 MASS stage',
                 'selected=SEEDS: equal prediction mean of both frozen 2500-step heads'],
        no_na_component=True, no_cloud_writes=True), indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
