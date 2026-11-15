# в”Ђв”Ђ Stage machinery: process runner, compact trace, and the four stage functions в”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђв”Ђ
import contextlib, importlib

STAGES = []           # (stage, seconds, status) for the run summary
STAGE_MARKS = {}      # stage -> [(frozen cell, START/DONE, seconds since stage start)]
FROZEN_STAGE = {
    2: 'Official RDKit 2026.03.3', 6: 'Competition files', 9: 'Asset inventory', 12: 'Documentation prior table',
    14: 'Prior benchmark table', 16: 'Natural-product panel', 18: 'Natural-product knowledge table',
    26: 'Datasets, priors and wheels', 27: 'Determinism patch', 28: 'Preflight', 30: 'Commit or rerun switch',
    32: 'Engine 2 В· two rankers', 34: 'PubChem channel', 36: 'Engine 1 В· library, pool, spectrum cache',
    37: 'Engine 1 В· models and rankers', 39: 'Engine 1 В· candidate lists', 41: 'GLACIER + ICEBERG forward models',
    43: 'Gated PubChem merge', 45: 'Two-engine fusion', 48: 'Metric audit and safe tail', 49: 'Metric-identity fusion',
    50: 'Postflight record', 51: 'Fragment score gap', 52: 'Window-40 overlay', 53: 'Engine 2 rank-2 placement',
    54: 'Execution receipt', 56: 'Example answer table'}
CELL_MARK = re.compile(r'^PIPELINE CELL (\d+) (START|DONE)')
KEY_LINE = re.compile(r'FAILED|ERROR|Traceback|merge stats|RANK2_OVERLAY|EXPORTED FROZEN|NEURAL FEATURES|'
                      r'NEURAL input failures|OUTSIDERS|engine lists \d+ |pubchem lists \d+|errors \d+ \|')
BASELINE = ROOT / 'submission_baseline0465.csv'
VARIANTS_DIR = ROOT / 'variants'
RESCUE_SLOTS = {'V3': 3, 'CUSTOM': int(CUSTOM.get('rescue', 0))}.get(VARIANT, 0)
PIPELINE_DONE = NEURAL_OK = OUTSIDERS_OK = CONSENSUS_OK = False
REPORT, MOVES, SUBMITTED, consensus = {}, pd.DataFrame(), None, None


def run_stage(args, log, name, quiet=None):
    """Run one stage in its own process; keep the full log on disk and print a compact trace."""
    quiet = QUIET_LOGS if quiet is None else quiet
    env = {**os.environ, 'PYTHONHASHSEED': '0', 'PYTHONUNBUFFERED': '1'}
    env.pop('INC_PANEL', None)
    t0, marks, tail = time.time(), [], collections.deque(maxlen=150)
    print(f'в–¶ {name}', flush=True)
    with open(log, 'w') as handle:
        proc = subprocess.Popen([str(a) for a in args], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            handle.write(line); handle.flush()
            t = time.time() - t0
            tail.append(line)
            m = CELL_MARK.match(line)
            if m:
                cell, kind = int(m.group(1)), m.group(2)
                marks.append((cell, kind, t))
                if quiet and kind == 'DONE' and cell in FROZEN_STAGE:
                    start = next((s for c, k, s in reversed(marks) if c == cell and k == 'START'), t)
                    if t - start >= 1:
                        print(f'  вњ“ {t / 60:6.1f} min   {FROZEN_STAGE[cell]:<40s} {t - start:8,.0f} s', flush=True)
                continue
            if not quiet:
                if len(line) < 5000:
                    print(line, end='', flush=True)
            elif KEY_LINE.search(line) and len(line) < 800:
                print('      ' + line.strip()[:180], flush=True)
        status = proc.wait()
    seconds = time.time() - t0
    STAGE_MARKS[name] = marks
    STAGES.append((name, seconds, 'ok' if status == 0 else f'exit {status}'))
    if status:
        print(''.join(tail))
        raise RuntimeError(f'{name} failed with exit code {status}; full log: {log}')
    print(f'  done in {minutes(seconds)}', flush=True)
    return seconds


def materialise_sources():
    """Stage 0: write and verify the pinned sources, find the neural bundle, install the official RDKit."""
    global FROZEN
    t0 = time.time()
    for name, text in MODULES.items():
        (CODE / name).write_text(text)
        assert hashlib.sha256((CODE / name).read_bytes()).hexdigest() == MODULE_SHA256[name], name
    FROZEN = CODE / 'frozen_0465.ipynb'
    FROZEN.write_bytes(base64.b64decode(FROZEN_B64))
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest() == FROZEN_SHA256, 'Pinned pipeline source differs'
    assert sys.version_info[:2] in ((3, 12), (3, 13)), 'Python 3.12 or 3.13 is required'
    if str(CODE) not in sys.path:
        sys.path.insert(0, str(CODE))
    from bundle import find_bundle
    from pathlib import Path as _BPath
    def _find_bundle_safe():
        try:
            return find_bundle(str(INPUT), ROOT, MODEL_PINS)
        except AssertionError:
            _cands = [p.parent for p in _BPath('/kaggle/input').rglob('final_model.pt')
                      if (p.parent / 'config.json').is_file() and 'casmi-spectrum-model-v1' in str(p)]
            print('BUNDLE FALLBACK candidates', len(_cands), flush=True)
            assert _cands, 'public model bundle not found'
            return str(sorted(_cands, key=lambda p: len(str(p)))[0])
    bundle = _find_bundle_safe()
    (CODE / 'bootstrap.py').write_text(''.join(json.loads(FROZEN.read_text())['cells'][2]['source']))
    run_stage([sys.executable, CODE / 'bootstrap.py'], ROOT / 'bootstrap.log', 'Official RDKit wheel', quiet=False)
    STAGES[-1] = ('Sources and RDKit wheel', time.time() - t0, 'ok')
    tiles([('Pipeline source', FROZEN_SHA256[:12] + 'вЂ¦', 'SHA-256 verified'),
           ('Helper modules', f'{len(MODULES)}', '6 public + 2 new, SHA-256 verified'),
           ('Neural bundle', Path(bundle).name, '4 files, SHA-256 verified'),
           ('Stage 0', minutes(time.time() - t0), 'including the wheel install')])
    return bundle


def run_public_pipeline():
    """Stage 1: every cell of the pinned pipeline in one process, then the export of its final lists."""
    if not RUN_PIPELINE:
        note('Fast commit.', 'The pipeline is skipped in this commit run; the scoring rerun executes every stage.', BLUE)
        return False
    assert not (ROOT / 'work/spec_meta.parquet').exists() and not (ROOT / 'submission.csv').exists(), \
        'Start from a fresh session (Run All after a restart)'
    seconds = run_stage([sys.executable, CODE / 'runner.py', FROZEN, FROZEN_SHA256, ROOT],
                        ROOT / 'submission_pipeline.log', 'Public 0.465 pipeline')
    receipt = json.loads((ROOT / 'execution_receipt.json').read_text())
    full = receipt['is_full_run']
    tiles([('Molecules ranked', f"{receipt['processed_molecules']:,}", 'hidden test' if full else 'visible smoke subset'),
           ('Answer rows', f'{len(SAMPLE_IDS):,}', 'all ranked' if full else 'placeholders elsewhere'),
           ('Pipeline time', minutes(seconds), 'one process, every cell'),
           ('Baseline file', BASELINE.name, 'kept for reference')])
    return True


def score_final_lists():
    """Stage 2a: the public scorer on exactly the exported candidates."""
    try:
        run_stage([sys.executable, CODE / 'neural_scores.py', BUNDLE, 'final_model.pt',
                   ROOT / 'frozen_candidate_evidence.parquet', ROOT / 'effective_query_spectra.parquet',
                   ROOT / 'neural_candidate_features.parquet', 'cuda'],
                  ROOT / 'submission_neural.log', 'Neural scorer В· final lists')
        return True
    except Exception as exc:
        note('Neural scorer failed.', f'The 0.465 answers will be submitted. {type(exc).__name__}: {str(exc)[:300]}', RED)
        return False


def score_outside_candidates(needed):
    """Stage 2b (optional): collect and score candidates ranked just outside the final lists."""
    elapsed_h = (time.time() - NB_T0) / 3600
    if not needed:
        return False
    if elapsed_h >= TIME_GUARD_HOURS:
        note('Tail rescue skipped.', f'The session has run {elapsed_h:.1f} h (guard {TIME_GUARD_HOURS} h).', YELLOW)
        return False
    try:
        run_stage([sys.executable, CODE / 'outsiders.py', FROZEN, ROOT, ROOT / 'frozen_candidate_evidence.parquet',
                   ROOT / 'outsider_evidence.parquet', OUTSIDERS_PER_MOLECULE],
                  ROOT / 'outsiders.log', 'Outside candidates В· collect')
        if not len(pd.read_parquet(ROOT / 'outsider_evidence.parquet')):
            return False
        run_stage([sys.executable, CODE / 'neural_scores.py', BUNDLE, 'final_model.pt',
                   ROOT / 'outsider_evidence.parquet', ROOT / 'effective_query_spectra.parquet',
                   ROOT / 'outsider_neural_features.parquet', 'cuda'],
                  ROOT / 'outsiders_neural.log', 'Neural scorer В· outside candidates')
        return True
    except Exception as exc:
        note('Tail rescue disabled.', f'{type(exc).__name__}: {str(exc)[:300]}', YELLOW)
        return False


def show_neural_summary():
    if not NEURAL_OK:
        return
    nf = pd.read_parquet(ROOT / 'neural_candidate_features.parquet')
    act = nf[nf.processed.astype(bool)]
    n_out = len(pd.read_parquet(ROOT / 'outsider_neural_features.parquet')) if OUTSIDERS_OK else 0
    tiles([('Candidates scored', f'{len(act):,}', f'{act.molecule_id.nunique():,} molecules'),
           ('Scored molecules', f'{int(act.groupby("molecule_id").neural_ok.all().sum()):,}', 'all spectra usable'),
           ('Spectra per molecule', f'{act.groupby("molecule_id").n_spectra.first().median():.0f}', 'median used by the scorer'),
           ('Outside candidates', f'{n_out:,}', 'scored for the tail rescue' if n_out else 'not needed for this variant')])


def build_consensus():
    """Stage 3a: the public 0.466 file, its exact rebuild, then every variant."""
    global consensus
    try:
        consensus = importlib.import_module('consensus')
        from submission import apply as public_apply
        evidence = ROOT / 'neural_candidate_features.parquet'
        with contextlib.redirect_stdout(io.StringIO()):      # the public helper prints its own report
            public_apply(evidence, BASELINE, ROOT / 'submission_public0466.csv', weight=0.25, offset=3.0)
        consensus.build_variants(evidence, BASELINE, ROOT / 'variants_check', {'V1': consensus.PRESETS['V1']}, 3.0)
        mine = pd.read_csv(ROOT / 'variants_check/submission_V1.csv', dtype=str, keep_default_na=False)
        public = pd.read_csv(ROOT / 'submission_public0466.csv', dtype=str, keep_default_na=False)
        assert mine.equals(public), 'V1 differs from the public 0.466 file'
        presets = dict(consensus.PRESETS)
        if VARIANT == 'CUSTOM':
            presets['CUSTOM'] = dict(w_top=float(CUSTOM['w_top']), w_mid=float(CUSTOM['w_mid']),
                                     rescue=int(CUSTOM.get('rescue', 0)), label='Custom weights')
        report, moves = consensus.build_variants(
            evidence, BASELINE, VARIANTS_DIR, presets, RRF_OFFSET,
            ROOT / 'outsider_neural_features.parquet' if OUTSIDERS_OK else None)
        print('V1 rebuilt exactly: the new code reproduces the public 0.466 file row for row.')
        return True, report, moves
    except Exception as exc:
        note('Consensus layer disabled.', f'{type(exc).__name__}: {str(exc)[:400]}', RED)
        return False, {}, pd.DataFrame()


def identity_map():
    keys = {}
    for path in (ROOT / 'neural_candidate_features.parquet', ROOT / 'outsider_neural_features.parquet'):
        if path.is_file():
            f = pd.read_parquet(path, columns=['smiles', 'metric_key'])
            keys.update({s: k for s, k in zip(f.smiles, f.metric_key) if isinstance(k, str)})
    return keys


def well_formed(path, same_candidates=True):
    """Minimal checks that do not depend on the new modules."""
    f = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert list(f.columns) == ['molecule_id', 'smiles'] and f.molecule_id.tolist() == SAMPLE_IDS, 'rows'
    lists = f.smiles.str.split(';')
    assert lists.map(len).between(1, 25).all(), 'list length'
    assert lists.map(lambda v: all(x.strip() for x in v) and len(set(v)) == len(v)).all(), 'SMILES'
    if same_candidates and BASELINE.is_file():
        b = pd.read_csv(BASELINE, dtype=str, keep_default_na=False)
        assert all(sorted(x.split(';')) == sorted(y.split(';')) for x, y in zip(b.smiles, f.smiles)), 'candidates'


def choose_and_submit():
    """Stage 3b: chosen variant -> V1 -> V0 -> public 0.466 file -> baseline file (-> sample in a fast commit)."""
    t0 = time.time()
    chain = []
    if CONSENSUS_OK:
        chain += [(n, VARIANTS_DIR / f'submission_{n}.csv') for n in dict.fromkeys([VARIANT, 'V1', 'V0'])]
    chain += [('public 0.466 file', ROOT / 'submission_public0466.csv'), ('baseline file', BASELINE)]
    chosen = None
    for name, path in chain:
        if not path.is_file():
            continue
        try:
            rescue = name in REPORT and REPORT[name].get('rescued', 0) > 0
            if rescue:
                consensus.validate(path, SAMPLE_IDS, BASELINE, allow_new=True, identity_of=identity_map())
            well_formed(path, same_candidates=not rescue)
            chosen = (name, path)
            break
        except Exception as exc:
            note(f'{name} rejected.', f'{type(exc).__name__}: {str(exc)[:300]}', YELLOW)
    if chosen is None:
        assert not IS_RERUN, 'No valid answer file in the scoring rerun'
        chosen = ('sample (fast commit)', COMP / 'sample_submission.csv')
    shutil.copyfile(chosen[1], ROOT / 'submission.csv')
    STAGES.append(('Consensus and checks', time.time() - t0, 'ok'))
    return chosen[0]


def show_variant_board():
    if CONSENSUS_OK:
        board = pd.DataFrame([{
            'Variant': k, 'Rule': v['label'], 'Leader weight': f"{v['w_top']:.2f}",
            'Ranks 2вЂ“25 weight': f"{v['w_mid']:.2f}", 'Tail rescue': v['rescue'] or 'вЂ“',
            'Rows re-ordered': f"{v['changed_rows']:,}", 'Rank 1 changed': f"{v['changed_top1']:,}",
            'Rescued': f"{v['rescued']:,}"} for k, v in REPORT.items()])
        board.index = board.Variant
        table_html(board, highlight=SUBMITTED, numeric=board.columns[2:])
    sub = pd.read_csv(ROOT / 'submission.csv', dtype=str, keep_default_na=False)
    tiles([('Submitted', SUBMITTED, 'copied to submission.csv'),
           ('Rows', f'{len(sub):,}', 'one per molecule, sample order'),
           ('Candidates per row', f'{sub.smiles.str.count(";").add(1).median():.0f}', 'median, at most 25'),
           ('SHA-256', hashlib.sha256((ROOT / 'submission.csv').read_bytes()).hexdigest()[:12] + 'вЂ¦', 'of submission.csv')])