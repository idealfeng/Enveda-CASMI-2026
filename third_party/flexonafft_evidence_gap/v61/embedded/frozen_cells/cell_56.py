try:
    # Figure 1 reads the final submission file and never reruns the ranking.
    example_ids = list(te.molecule_id.drop_duplicates())
    eligible_ids = [m for m in example_ids if BASE[m][2] < LIB_TAU and PC.get(m, {}).get('pc')]
    example_mid = eligible_ids[0] if eligible_ids else min(example_ids, key=lambda m: BASE[m][2])
    example_query = te[te.molecule_id.eq(example_mid)]
    main_smiles, main_keys, example_lib = BASE[example_mid]
    proposal = PC.get(example_mid, {})
    _ft = proposal.get('fz_top')
    if _ft is None and proposal.get('pc_fz'):
        _ft = proposal['pc_fz'][0]
    _bp = proposal.get('best_pool_fz')
    _delta = (_ft - _bp if _ft is not None and _bp is not None and np.isfinite(_bp) else 1e9)
    if not proposal.get('pc'):
        branch = 'no PubChem proposals'
    elif example_lib >= LIB_TAU:
        branch = 'strong library match: PubChem proposals not inserted'
    else:
        branch = 'PubChem proposals at ranks 2, 4, 6, 8, 10' if _delta > REL_TH else 'PubChem proposals at ranks 4, 8, 12, 16, 20'
        if (proposal.get('S') is not None and float(proposal['S']) > S_TAU and
            float(proposal.get('top_pop') or 0.0) >= POP_TAU) or _delta > 150.0:
            branch += ', leading proposal moved to rank 1'
    _v43_audits = json.loads(Path('experiment_audit_factorial.json').read_text())['rows']
    _v43_row = next(row for row in _v43_audits if row['molecule_id'] == str(example_mid))
    _final_names = {'glacier': 'GLACIER', 'ice_fallback': 'ICEBERG', 'frag_gap': 'fragment score',
                    'unrescored': 'none', 'no_engine': 'none', 'placeholder': 'none'}
    _stage = _final_names.get(_v43_row['branch'], _v43_row['branch'])
    if _v43_row['branch'] == 'ice_fallback' and not _v43_row.get('ice_finite_count'):
        _stage = 'none (no finite ICEBERG scores)'
    branch += '; formula-level scoring: ' + _stage
    delta_text = f' · Δ {_delta:.0f}' if _delta != 1e9 else ''
    display(Markdown(f'**{example_mid}** · {len(example_query)} spectra · '
        f'neutral mass {np.nanmedian(example_query.nm):.4f} Da · library match {example_lib:.3f} · '
        f'**{branch}**' + delta_text))
    _v43_final = pd.read_csv('submission.csv', dtype=str, keep_default_na=False).set_index('molecule_id')
    final_smiles = _v43_final.at[str(example_mid), 'smiles'].split(';')
    known = {name: {metric_identity(s) for s in candidates} for name, candidates in (
        ('main', BASE_TAIL_CANDIDATES[str(example_mid)]), ('PubChem', proposal.get('pc', [])),
        ('second engine', ENG.get(str(example_mid), {}).get('smiles', [])))}
    example_rows = []
    for rank, smiles in enumerate(final_smiles[:5], 1):
        identity = metric_identity(smiles)
        channels = [name for name, identities in known.items() if identity in identities]
        example_rows.append({'Rank': rank, 'Channel': ' + '.join(channels) or 'list filling',
                             'Connectivity key': identity[0], 'SMILES': smiles})
    display(Markdown('**Worked-example candidates.**'))
    display(pd.DataFrame(example_rows))
    drawn = [Chem.MolFromSmiles(s) for s in final_smiles[:3]]
    if all(m is not None for m in drawn):
        display(Draw.MolsToGridImage(drawn, molsPerRow=3, subImgSize=(360, 280), useSVG=True,
                                   legends=[f'Rank {i}' for i in range(1, len(drawn) + 1)]))
except Exception as exc:
    print('worked example unavailable:', type(exc).__name__, exc)
