try:
    nt = pd.read_parquet(TABLE / 'natural_products.parquet',
                         columns=['np_pathway', 'in_casmi_train', 'in_casmi_pool', 'pubmed_articles'])
    candidate_joins = pd.read_parquet(TABLE / 'candidate_joins.parquet',
                                     columns=['ik14', 'tier_row', 'pubchemlite_row'])
    keys = pd.read_parquet(TABLE / 'natural_products.parquet', columns=['ik14']).ik14
    assert candidate_joins.ik14.equals(keys)
    nt = nt.assign(in_pubchem_tier=candidate_joins.tier_row.ge(0).to_numpy(),
                   in_pubchemlite=candidate_joins.pubchemlite_row.ge(0).to_numpy())
    nt = nt.assign(np_pathway=nt.np_pathway.fillna('unclassified'),
                   with_pubmed=nt.pubmed_articles.fillna(0).gt(0),
                   in_casmi_train=nt.in_casmi_train.astype(bool), in_casmi_pool=nt.in_casmi_pool.astype(bool))
    def composition(g):
        return pd.Series({'natural products': len(g),
                          'with training spectrum (%)': 100 * g.in_casmi_train.mean(),
                          'in candidate pool (%)': 100 * g.in_casmi_pool.mean(),
                          'with PubMed article (%)': 100 * g.with_pubmed.mean(),
                          'in PubChem tier (%)': 100 * g.in_pubchem_tier.mean(),
                          'in PubChemLite add-on (%)': 100 * g.in_pubchemlite.mean()})
    t = pd.DataFrame({k: composition(g) for k, g in nt.groupby('np_pathway')}).T
    t = t.sort_values('natural products', ascending=False)
    t.loc['all'] = composition(nt)
    t.index.name = 'pathway'
    fmt = {c: '{:.1f}' for c in t.columns if c.endswith('(%)')}
    fmt['natural products'] = '{:,.0f}'
    display(t.style.format(fmt))
    del nt
    pcl_docs = pd.read_parquet(POP / 'pubchemlite_annotations.parquet',
                               columns=['tier_row', 'lsid', 'lpmid', 'lotus_refs'])
    display(pd.DataFrame([{
        'PubChemLite add-on candidates': len(pcl_docs),
        'matched to pinned PubChem tier (%)': 100 * pcl_docs.tier_row.ge(0).mean(),
        'with documentation prior (%)': 100 * (pcl_docs.lsid + pcl_docs.lpmid).gt(0).mean(),
        'with LOTUS references (%)': 100 * pcl_docs.lotus_refs.gt(0).mean(),
    }]).style.hide(axis='index').format({'PubChemLite add-on candidates': '{:,}', **{
        c: '{:.1f}' for c in ['matched to pinned PubChem tier (%)',
                              'with documentation prior (%)', 'with LOTUS references (%)']}}))
    del pcl_docs
except Exception as exc:
    print('knowledge table unavailable:', type(exc).__name__, exc)