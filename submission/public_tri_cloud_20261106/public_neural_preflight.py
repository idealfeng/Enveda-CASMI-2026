
# Reproduction observer: file/config checks only, no scoring or ordering changes.
def _public_neural_preflight(public_bundle):
    from pathlib import Path
    import hashlib, json
    expected = {'original_source_sha256': '73c8bdc7799ffdad7ef756015c74c90365ee060122f2567f8a3c061ff42cc0df', 'smoke_source_sha256': 'b8ebb7ac69f726c191c6888c186b7cdffae72adf474b64c82611137da43a2b15', 'public_pins': {'features.py': 'a97ad9b3ab3711517864d56e497e1672cb29bb05683c72b52db9f9b0a17b1455', 'model.py': '2547418857386d1c2513fd1ab6c70961e6a96e73d9d495bbfe3052197e69dc39', 'config.json': '563fb2a2a81ca48ea094f9ab78c157a48a6e9a5503e85e6ce8f0fb3615c1cc03', 'final_model.pt': '44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642'}, 'models': {'v2': {'dataset_slug': 'casmi26-scorer-v2-model', 'checkpoint_sha256': 'c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46', 'config_sha256': '5ed9578966792110846b3bf7c11a34d8247fa8e57d168b37124d208924fd9524', 'config_flags': {'width': 192, 'heads': 6, 'layers': 3, 'embedding': 192, 'fp_bits': 2048, 'max_peaks': 96, 'min_peaks': 3, 'temperature': 0.1, 'fp_score_weight': 2.0, 'refit_full': True, 'external_paths': []}}, 'v4': {'dataset_slug': 'casmi26-scorer-v4-model', 'checkpoint_sha256': '10565a0d8c2c1cc903882ff7ba2a9b7b994ae169228bf0c9b6c4ae055ff4ec51', 'config_sha256': '3ee4f2ebe68d21bcd251214ecb23bdf0837b6c4cfae9efc467ca9fcabbdf69a4', 'config_flags': {'width': 256, 'heads': 8, 'layers': 3, 'embedding': 256, 'fp_bits': 2048, 'max_peaks': 96, 'min_peaks': 3, 'temperature': 0.1, 'fp_score_weight': 2.0, 'refit_full': True, 'external_paths': []}}}, 'lotus_sha256': '7684b51f72a2d4c073a8d2435fff14cce0a0e7364ac7904101b8f93990f0ac2f', 'flags': {'VARIANT': 'CUSTOM', 'CUSTOM': {'w_top': 0.25, 'w_mid': 0.75, 'rescue': 0}, 'RRF_OFFSET': 3.0, 'COMMIT_MODE': 'smoke', 'OUTSIDERS_PER_MOLECULE': 20, 'TIME_GUARD_HOURS': 7.5, 'ENABLE_TAIL_SLOT': True, 'PHYSICAL_POST_SECONDS': 1500, 'PHYSICAL': True, 'PROVENANCE': False, 'FRAG_ON_V2': True, 'ENABLE_K14_DEDUP': True, 'POP_W': 0.1, 'SPEC_W': 0.1, 'NP_W': 0.12, 'LIB_HIT_GATE': 0.78, 'PIN_OLD_LEADER': True, 'OUTSIDER_FILL': True, 'NP_PROMO_MARGIN': 0.055}}
    audit = dict(status='checking', observer_version=1,
        upstream_source_sha256=expected['original_source_sha256'],
        smoke_source_sha256=expected['smoke_source_sha256'],
        scoring_or_candidate_changes=False, inputs={}, flags={})
    target = Path(ROOT)/'public_neural_input_audit.json'
    def digest(path):
        h = hashlib.sha256()
        with Path(path).open('rb') as stream:
            for block in iter(lambda: stream.read(1 << 20), b''):
                h.update(block)
        return h.hexdigest()
    def save():
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(audit, indent=2)+'\n')
        temporary.replace(target)
    try:
        for name, value in expected['flags'].items():
            observed = globals().get(name)
            audit['flags'][name] = observed
            assert observed == value, 'Unexpected V30 configuration: '+name
        assert globals().get('RUN_PIPELINE') is True, 'A real visible smoke or hidden run is required'
        public_bundle = Path(public_bundle)
        actual = {name: digest(public_bundle/name) for name in expected['public_pins']}
        assert actual == expected['public_pins'], 'Actual public bundle does not match four original pins'
        audit['inputs']['public'] = dict(path=str(public_bundle), pins=actual)
        for name, model in expected['models'].items():
            hits = [p for p in Path(INPUT).rglob('final_model.pt') if model['dataset_slug'] in p.parts]
            assert len(hits) == 1, 'Expected exactly one native '+name+' checkpoint'
            folder = hits[0].parent
            checkpoint_sha = digest(folder/'final_model.pt')
            config_sha = digest(folder/'config_used.json')
            assert checkpoint_sha == model['checkpoint_sha256'], 'Native '+name+' checkpoint differs'
            assert config_sha == model['config_sha256'], 'Native '+name+' config differs'
            config = json.loads((folder/'config_used.json').read_text())
            assert all(config.get(k) == v for k, v in model['config_flags'].items()), 'Native '+name+' config flags differ'
            audit['inputs'][name] = dict(path=str(folder), checkpoint_sha256=checkpoint_sha,
                config_sha256=config_sha, config_flags={k: config.get(k) for k in model['config_flags']})
        checkpoints = [audit['inputs']['public']['pins']['final_model.pt']] + [
            audit['inputs'][name]['checkpoint_sha256'] for name in ('v2','v4')]
        assert len(set(checkpoints)) == 3, 'Three model checkpoints must be distinct'
        lotus = [p for p in Path(INPUT).rglob('candidates_lotus.parquet') if 'casmi26-lotus-candidates' in p.parts]
        assert len(lotus) == 1 and digest(lotus[0]) == expected['lotus_sha256'], 'Native LOTUS V2 input differs'
        audit['inputs']['lotus'] = dict(path=str(lotus[0]), bytes=lotus[0].stat().st_size,
            sha256=expected['lotus_sha256'])
        audit['status'] = 'passed'
        save()
        return audit
    except Exception as error:
        audit.update(status='failed', error_type=type(error).__name__, error_message=str(error)[:500])
        save()
        raise

PUBLIC_NEURAL_INPUT_AUDIT = _public_neural_preflight(BUNDLE)
