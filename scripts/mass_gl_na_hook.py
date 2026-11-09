"""Runtime adapter: score real H+/Na+ observations through pinned GLACIER."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

RUNNER_SHA = '5c4f74313ac54263d05d987c39d012d81ec57c5f35e1095ecd49a5bcb6440fca'
CHECKPOINT_SHA = '9192e4c2eeafe83317d5a2c2641e1fc4d68934488757a4faafeb66f2ab397a12'
SOURCE_ADAPTATION = 'GLACIER real H+/Na+ spectrum coverage; original candidate lists and actual per-spectrum mean'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def select_items(items):
    result = []
    for item in items:
        spectra = [s for s in item['spectra']
                   if s.get('adduct') in ('[M+H]+', '[M+Na]+')]
        if spectra:
            result.append(dict(item, spectra=spectra))
    return result


def record_report(package, items, selected, scores, workdir, output):
    package, workdir = Path(package), Path(workdir)
    expected = select_items(items)
    actual_input = json.loads((workdir / 'gl_in.json').read_text())
    meta = json.loads((workdir / 'gl_out.json.meta.json').read_text())
    finite = lambda value: isinstance(value, (int, float)) and math.isfinite(value)
    checks = dict(
        exact_original_candidate_and_spectrum_selection=selected == expected == actual_input,
        original_runner_pin=sha(package / 'gl_runner.py') == RUNNER_SHA,
        original_checkpoint_pin=sha(package / 'ckpt/glacier.pt') == CHECKPOINT_SHA,
        runtime_success=meta.get('status') == 'ok' and not meta.get('errors'),
        exact_query_set=set(scores) == {str(item['mid']) for item in expected},
        original_candidate_sets=all(set(scores.get(str(item['mid']), {})) == set(item['cands'])
                                    for item in expected),
        all_selected_candidates_finite=all(finite(scores.get(str(item['mid']), {}).get(s))
                                           for item in expected for s in item['cands']),
        no_adduct_relabel=all(s.get('adduct') in ('[M+H]+', '[M+Na]+')
                             for item in selected for s in item['spectra']),
    )
    report = dict(status='passed' if all(checks.values()) else 'failed', checks=checks,
                  aggregation='original GL runner mean of actual finite candidate-spectrum scores',
                  budget_seconds=4000,
                  queries=len(selected), candidates=sum(len(i['cands']) for i in selected),
                  spectra=sum(len(i['spectra']) for i in selected),
                  h_spectra=sum(s['adduct'] == '[M+H]+' for i in selected for s in i['spectra']),
                  na_spectra=sum(s['adduct'] == '[M+Na]+' for i in selected for s in i['spectra']),
                  na_queries=sum(any(s['adduct'] == '[M+Na]+' for s in i['spectra']) for i in selected),
                  original_runner_sha256=RUNNER_SHA, original_checkpoint_sha256=CHECKPOINT_SHA,
                  runtime=meta, source_adaptation=SOURCE_ADAPTATION,
                  pretrained_na_coverage_known=False)
    Path(output).write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    if not all(checks.values()):
        raise RuntimeError('GL Na coverage audit failed: ' + repr(checks))
    return report


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Expected exactly one source adaptation site: ' + before[:100])
    return text.replace(before, after)


def adapt_cell41(text):
    """Retain the frozen source pin; adapt only its executed cell 41 explicitly."""
    before = "    gl_items = [dict(it, spectra=[s for s in it['spectra'] if s.get('adduct') == '[M+H]+']) for it in items]   # v29: GLACIER on [M+H]+ only (v27: +0.006)\n    gl_items = [it for it in gl_items if it['spectra']]"
    text = replace_once(text, before,
                        "    gl_items = select_items(items)  # real H+ and Na+, no relabeling")
    text = replace_once(text,
                        "    print('v29 GLACIER [M+H]+ only: molecules', len(gl_items), 'of', len(items))",
                        "    print('GLACIER real H+/Na+: molecules', len(gl_items), 'of', len(items))")
    text = replace_once(text,
                        "    print('GL meta', open(meta_f).read()[:1500] if os.path.exists(meta_f) else 'missing')",
                        "    print('GL meta', open(meta_f).read()[:1500] if os.path.exists(meta_f) else 'missing')\n"
                        "    GL_NA_REPORT = record_report(GL_PKG, items, gl_items, GL_SCORES, '/kaggle/working/gl_work', '/kaggle/working/gl_na_runtime.json')")
    text = replace_once(text,
                        "# N1A complement: Seyit Kaan Gunes; integration as in Ahmed Berat Ozer v15 / guhongbin v465.",
                        "assert GL_NA_REPORT.get('status') == 'passed', 'Expanded GL run must complete; no silent fallback'\n"
                        "# N1A complement: Seyit Kaan Gunes; integration as in Ahmed Berat Ozer v15 / guhongbin v465.")
    # A real Na observation may cover a formerly H-blind query. Keep real GL and
    # discard proxy overlap just as original hidden N1 did; exercise this in visible runs too.
    text = replace_once(text,
                        "    if not IS_RERUN:\n        assert not _n1_clash, ('N1 molecule already scored by the H1 run', _n1_clash[:5])",
                        "    _glna_real_na_mids = {str(it['mid']) for it in gl_items if any(s.get('adduct') == '[M+Na]+' for s in it['spectra'])}\n"
                        "    _n1_real = {m: v for m, v in _n1_real.items() if m not in _n1_clash}\n"
                        "    if not IS_RERUN:\n"
                        "        assert set(_n1_clash) <= _glna_real_na_mids, ('Unexpected real-GL/proxy clash', _n1_clash[:5])")
    return "from gl_na_hook import select_items, record_report\nGL_NA_REPORT = {}\n" + text
