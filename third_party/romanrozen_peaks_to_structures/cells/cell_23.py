# What each layer did in this run, read from the files the stages wrote.
if SHOW:
    rep = {}
    for name in ('spectral_parallax_report.json', 'provenance_tournament_report.json', 'merge_report.json'):
        p = ROOT / name
        if p.is_file():
            try:
                rep[name] = json.loads(p.read_text())
            except Exception as exc:  # noqa: BLE001 - a report is only shown, never used
                rep[name] = {'unreadable': repr(exc)}
    base = pd.read_csv(BASELINE, dtype=str, keep_default_na=False) if BASELINE.is_file() else None
    final = pd.read_csv(ROOT / 'submission.csv', dtype=str, keep_default_na=False)
    layers = [('0.465 pipeline', BASELINE), ('V1, neural 0.25', VARIANTS_DIR / 'submission_V1.csv'),
              ('V2, ranks 2-25 at 0.50', VARIANTS_DIR / 'submission_V2.csv'),
              (f'{VARIANT}, ranks 2-25 at {CUSTOM["w_mid"]:.2f}', VARIANTS_DIR / f'submission_{VARIANT}.csv')]
    if globals().get('FRAG_ON_V2'):
        layers += [('submitted: CUSTOM + the fragment check\'s leader moves on the V2 order', ROOT / 'submission.csv')]
    elif PROVENANCE:
        layers += [('after the fragment check', ROOT / 'submission_physical0472_control.csv'),
                   ('after the provenance reranker (submitted)', ROOT / 'submission.csv')]
    else:
        layers += [('after the fragment check (submitted)' if PHYSICAL else 'submitted', ROOT / 'submission.csv')]
    prev, out = None, []
    for label, path in layers:
        if not path.is_file():
            continue
        f = pd.read_csv(path, dtype=str, keep_default_na=False).set_index('molecule_id').smiles
        if prev is not None:
            common = f.index.intersection(prev.index)
            moved = int((f[common] != prev[common]).sum())
            top1 = int(sum(a.split(';')[0] != b.split(';')[0] for a, b in zip(f[common], prev[common])))
            out.append({'layer': label, 'lists re-ordered vs previous': moved, 'rank 1 changed': top1})
        else:
            out.append({'layer': label, 'lists re-ordered vs previous': '-', 'rank 1 changed': '-'})
        prev = f
    table_html(pd.DataFrame(out).set_index('layer', drop=False), numeric=('lists re-ordered vs previous', 'rank 1 changed'))
    print('Commit run: the counts cover the 12 visible smoke molecules; the hidden scoring rerun is not shown to anyone.')
    for k, v in rep.items():
        print(k, json.dumps(v)[:600])