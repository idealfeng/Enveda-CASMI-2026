try:
    cols = ['inchikey14', 'compound_name', 'pubchem_cid', 'pop', 'n_depositors', 'n_vendors',
            'src_spectral_library', 'src_metabolite_pathway', 'src_chebi', 'log1p_mesh']
    pool = pd.read_csv(POP / 'pool_popularity.csv', usecols=cols)
    keys = ['RYYVLZVUVIJVGH', 'LPHGQDQBBGAPDZ']        # caffeine, isocaffeine (both C8H10N4O2)
    t = pool[pool.inchikey14.isin(keys)].set_index('inchikey14').loc[keys].reset_index()
    t = t[['compound_name', 'inchikey14', 'pubchem_cid', 'pop', 'n_depositors', 'n_vendors', 'log1p_mesh',
           'src_spectral_library', 'src_metabolite_pathway', 'src_chebi']]
    display(t.rename(columns={'compound_name': 'compound', 'n_depositors': 'depositors', 'n_vendors': 'vendors',
                              'log1p_mesh': 'ln(1 + MeSH terms)', 'src_spectral_library': 'spectral library',
                              'src_metabolite_pathway': 'metabolite/pathway', 'src_chebi': 'ChEBI'})
            .style.hide(axis='index').format({'pop': '{:.2f}', 'ln(1 + MeSH terms)': '{:.2f}'}))
    del pool
except Exception as exc:
    print('popularity table unavailable:', type(exc).__name__, exc)