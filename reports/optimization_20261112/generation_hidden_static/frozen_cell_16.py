try:
    panel = pd.read_parquet(PANEL / 'panel.parquet')
    summary = {'molecules': len(panel)}
    for c in ('n_spectra', 'n_views', 'spectra'):
        if c in panel.columns and pd.api.types.is_numeric_dtype(panel[c]):
            summary['spectra'] = int(panel[c].sum()); break
    for c in ('true_mass', 'neutral_mass', 'mass'):
        if c in panel.columns:
            summary['median neutral mass (Da)'] = float(panel[c].median()); break
    display(pd.DataFrame([summary]).style.hide(axis='index')
            .format({'spectra': '{:,}', 'median neutral mass (Da)': '{:.1f}'}))
    rows = []
    for f in sorted(PANEL.glob('*.parquet')):
        names = pq.read_schema(f).names
        rows.append((f.name, pq.ParquetFile(f).metadata.num_rows, len(names),
                     ', '.join(names[:7]) + (', …' if len(names) > 7 else '')))
    for d in sorted(p for p in PANEL.iterdir() if p.is_dir()):
        rows.append((d.name + '/', None, None, ', '.join(sorted(p.name for p in d.iterdir())[:5])))
    display(pd.DataFrame(rows, columns=['file', 'rows', 'columns', 'contents']).style.hide(axis='index')
            .format({'rows': lambda v: '' if pd.isna(v) else f'{int(v):,}',
                     'columns': lambda v: '' if pd.isna(v) else f'{int(v)}'}))
except Exception as exc:
    print('panel summary unavailable:', type(exc).__name__, exc)

try:
    prior_summary = (pd.read_csv(PANEL / 'prior_rule_summary.csv')
                     .replace({'rule': {'v10 composite prior': 'composite prior (Section 2)'}})
                     .rename(columns={'queries': 'molecules', 'truth_present': 'answer among candidates',
                                      'mrr25': 'MRR@25', 'delta_documentation': 'Δ vs documentation'}))
    print('Prior-only ranking of the PubChem candidates with the answer formula; 250 molecules, ties averaged')
    display(prior_summary.style.hide(axis='index').format(
        {'MRR@25': '{:.4f}', 'Δ vs documentation': '{:+.4f}'}))
except Exception as exc:
    print('cached public prior replay unavailable:', type(exc).__name__, exc)

try:
    audit = _json.loads((FOLD / 'SPLIT_AUDIT.json').read_text())
    contract = _json.loads((FOLD / 'MODEL_INPUTS.json').read_text())
    display(pd.DataFrame([{
        'fold-safe output bits': contract['output_bits'],
        'excluded structure rows': audit['excluded_structure_rows'],
        'panel identities excluded': audit['panel_truth_keys_excluded'],
        'panel identities in its training set': audit['panel_training_overlap'],
    }]).style.hide(axis='index').format('{:,}'))
    replay = pd.DataFrame(_json.loads((FOLD / 'PANEL_REPLAY_PUBLIC.json').read_text())['notebook_summary'])
    replay = replay[replay.protocol.eq('v10_prior') &
                    (replay['fold0 weight'].eq(0) | np.isclose(replay['fold0 weight'], 1 / 3))].copy()
    replay.insert(0, 'fingerprint logits', np.where(replay['fold0 weight'].eq(0), 'A+B', 'A+B + 0.5 fold0'))
    print('PubChem-channel shortlist with the documentation prior; 250 molecules')
    display(replay.drop(columns=['protocol', 'fold0 weight']).style.hide(axis='index').format(
        {c: '{:.4f}' for c in ['MRR@25', 'top-1', 'delta MRR', 'delta MRR 95% low', 'delta MRR 95% high']}))
except Exception as exc:
    print('fold-safe public audit unavailable:', type(exc).__name__, exc)
