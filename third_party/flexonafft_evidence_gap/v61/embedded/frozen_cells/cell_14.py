try:
    b = pd.read_csv(POP / 'BENCHMARK_SOURCES.csv')
    b = b[b.channel.eq('PubChem exact formula')]
    names = {'src_spectral_library': 'spectral libraries', 'src_metabolite_pathway': 'metabolite / pathway resources',
             'src_chebi': 'ChEBI', 'src_toxicology': 'EPA toxicology', 'src_lipidmaps': 'LIPID MAPS',
             'log1p_n_depositors': 'ln(1 + distinct depositors)', 'log1p_mesh': 'ln(1 + MeSH terms)'}
    b = b[b.signal.isin(names)].assign(signal=lambda d: d.signal.map(names))
    out = pd.DataFrame({'signal': b.signal, 'answers with signal > 0 (%)': 100 * b.answer_nonzero_fraction,
                        'competing candidates with signal > 0 (%)': 100 * b.decoy_nonzero_fraction_query_mean})
    for w in ('0.10', '0.25', '0.50'):
        if f'delta_{w}_mrr25' in b.columns:
            out[f'Δ MRR@25, w = {w}'] = b[f'delta_{w}_mrr25'].values
    print(f'documentation prior alone: MRR@25 = {float(b.baseline_pop_mrr25.iloc[0]):.4f} (250 molecules)')
    fmt = {c: '{:+.4f}' for c in out.columns if c.startswith('Δ')}
    fmt.update({c: '{:.1f}' for c in out.columns if c.endswith('(%)')})
    display(out.style.hide(axis='index').format(fmt))
except Exception as exc:
    print('benchmark table unavailable:', type(exc).__name__, exc)