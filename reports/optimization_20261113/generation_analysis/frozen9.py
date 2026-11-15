ROLE = {
    'casmi26-v4b-models': 'main engine: code, four LightGBM boosters, generator',
    'casmi26-fpnet-full1': 'main engine: full1 fingerprint model',
    'casmi26-v2-pool': 'main engine: 710,701-structure candidate pool with fragments and fingerprints',
    'casmi26-v3-models': 'PubChem channel: FPNet A+B models and code; ensemble adds fold-safe FPNet from the fifth dataset',
    'casmi26-fp-models-v2': 'second engine: single and merged fingerprint models',
    'casmi26-ranker-features': 'second engine: ranker training features',
    'casmi26-simulated-ranker-rows': 'second engine: simulated ranker training rows',
    'coconut-casmi26-candidates': 'second engine: COCONUT candidates with fingerprints',
    'chebi-lipidmaps-casmi26': 'earlier ChEBI and LIPID MAPS candidate bank (kept for reproducibility)',
    'casmi-chebi-lmsd-structures': 'second engine: standardised ChEBI and LIPID MAPS candidates (sergiomalv)',
    'casmi26-pubchemlite-cc0-candidate-fingerprints': 'second engine: PubChemLite CC0 candidates (franciscoangulo)',
    'casmi26-iceberg': 'forward model ICEBERG and its inference wrapper',
    'casmi26-glacier': 'forward model GLACIER and its inference wrapper',
    'hengck23-dreams-enveda-casmi26': 'candidates for unfilled ranks (mass-compatible DreaMS structures)',
    'rdkit-2026-3-3-wheel': 'RDKit 2026.03.3 (metric identity)',
    'rdkit-wheels': 'RDKit 2025.03.6 (simulator environment)',
}
try:
    rows = []
    for d in sorted(p for p in V4G.iterdir() if p.is_dir()):
        files = [f for f in d.rglob('*') if f.is_file()]
        rows.append((d.name, ROLE.get(d.name, ''), len(files), round(sum(f.stat().st_size for f in files) / 1e9, 3)))
    flat = [f for f in V4G.iterdir() if f.is_file()]
    rows.append(('(top level)', 'original v4g inference inputs and attribution files', len(flat),
                 round(sum(f.stat().st_size for f in flat) / 1e9, 3)))
    display(pd.DataFrame(rows, columns=['folder', 'role', 'files', 'size (GB)']).style.hide(axis='index')
            .format({'files': '{:,}', 'size (GB)': '{:.3f}'}))
except Exception as exc:
    print('folder table unavailable:', type(exc).__name__)