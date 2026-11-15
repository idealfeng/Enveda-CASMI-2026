
def _observe_guarded_head_tail():
    import hashlib,json
    from collections import Counter
    expected={'branch': 'mass_guarded_head_tail_1108', 'recipe_sha256': 'ba7ee5d3545fd6bc32159bbeed785e904dbf99beae0347984a8b7d5c8809e5d8', 'tail_module_sha256': 'ab01de6ba2ace14e736a69a93e7e2d86616871e45e424e2f26054791e3de7031', 'payload_pins': {'candidate_multispectrum_head.py': '6dc38d9d9dd59bff0ed791045573638c5566b2e1f84c0336c1b1bff383f886f0', 'learned_head_score.py': '14ba386cef89194c87cead728b23a670f83d425b2316a007d3f07901e5cf1a74', 'learned_head_runtime.json': 'b3e605208a660c00a48409226c8088a5aa63a8228dc69c8bafbd6ded80289de5', 'head_seed20261108_step2500.pt': '99e63aedb420217c817aeaaebd3d09ffa9620824a8d8833dcf55fd90ae903a53', 'head_seed20261109_step2500.pt': 'f29077ca350e48705cec93ed7a9716b2b718e965ba56cec859bb829bf4b7ba75'}, 'original_scorer_sha256': 'cb9e4d6732992e3310e951533fd0c644d3b515134ad03768c35e5a86551267d2', 'head_receipts': [{'sha256': '99e63aedb420217c817aeaaebd3d09ffa9620824a8d8833dcf55fd90ae903a53', 'step': 2500, 'seed': 20261108}, {'sha256': 'f29077ca350e48705cec93ed7a9716b2b718e965ba56cec859bb829bf4b7ba75', 'step': 2500, 'seed': 20261109}]}
    checks={}
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    def check(k,v):
        checks[k]=bool(v)
        assert v,k
    check('original_base_audit',BATCH_VARIANT_AUDIT.get('status')=='passed')
    check('late_module_pin',digest(CODE/'guarded_head_tail.py')==expected['tail_module_sha256'])
    check('head_payload_pins',all(digest(CODE/k)==v for k,v in expected['payload_pins'].items()))
    check('original_scorer_pin',digest(CODE/'neural_scores_original.py')==expected['original_scorer_sha256'])
    report=json.loads((ROOT/'guarded_tail_runtime.json').read_text())
    before=pd.read_csv(ROOT/'submission_guarded_tail_control.csv',dtype=str,keep_default_na=False)
    after=pd.read_csv(ROOT/'submission.csv',dtype=str,keep_default_na=False)
    check('audited_control_bound',digest(ROOT/'submission_guarded_tail_control.csv')==BATCH_VARIANT_AUDIT['csv_sha256']==report.get('control_sha256'))
    check('final_csv_bound',digest(ROOT/'submission.csv')==report.get('output_sha256'))
    check('exact_ids_order',after.molecule_id.tolist()==before.molecule_id.tolist()==SAMPLE_IDS)
    check('exact_prefix7',all(a.split(';')[:7]==b.split(';')[:7] for a,b in zip(before.smiles,after.smiles)))
    check('exact_candidate_multisets',all(Counter(a.split(';'))==Counter(b.split(';')) for a,b in zip(before.smiles,after.smiles)))
    if IS_RERUN:
        check('tail_execution',report.get('status') in ('applied','no_eligible') and report.get('mode')=='hidden_full')
        names=('control_matches_audited_base','exact_molecule_order','prefix7_exact','candidate_multiset_exact','official_identity_multiset_exact','formula_slots_exact','no_eligible_explicit')
        check('named_tail_checks',set(report.get('checks',{}))==set(names) and all(report['checks'][k] is True for k in names))
        check('dynamic_scope',report.get('rows')==len(SAMPLE_IDS)>0)
        formulas=True;identities=True;invalid_preserved=True
        for a,b in zip(before.smiles,after.smiles):
            old,new=a.split(';'),b.split(';')
            old_desc=[_guarded_tail.describe(s) for s in old];new_desc=[_guarded_tail.describe(s) for s in new]
            identities &= Counter(x[0] for x in old_desc)==Counter(x[0] for x in new_desc)
            formulas &= all(old_desc[i][1]==new_desc[i][1] for i in range(7,len(old)))
            if any(x[0] is None for x in old_desc) or len({x[0] for x in old_desc})!=len(old_desc):invalid_preserved &= old==new
        check('actual_formula_slots',formulas)
        check('actual_official_identity_multisets',identities)
        check('invalid_identity_query_preserved',invalid_preserved)
        if report['status']=='applied':
            check('actual_head_inference',report.get('model_invoked') is True and report.get('eligible_queries',0)>0 and report.get('eligible_candidate_rows',0)>0)
            frame,audit,binding=_guarded_tail.validate_score_audit(ROOT,expected['head_receipts'])
            check('actual_score_bindings',all(binding.values()) and report.get('head_receipts')==expected['head_receipts'])
            check('saved_score_hashes',report.get('evidence_sha256')==digest(ROOT/'guarded_tail_evidence.parquet') and report.get('queries_sha256')==digest(ROOT/'effective_query_spectra.parquet') and report.get('scores_sha256')==digest(ROOT/'guarded_tail_scores.parquet') and report.get('head_audit_sha256')==digest(ROOT/'guarded_tail_scores.parquet.head_audit.json'))
        else:
            check('explicit_no_eligible',report.get('model_invoked') is False and report.get('eligible_queries')==0 and report.get('eligible_candidate_rows')==0 and after.equals(before))
    else:
        check('fast_no_model',report.get('status')=='fast_static_no_model' and report.get('model_invoked') is False and not RUN_PIPELINE and not PIPELINE_DONE and after.equals(before))
    result=dict(status='passed',branch=expected['branch'],mode='hidden_full' if IS_RERUN else 'fast_static',recipe_sha256=expected['recipe_sha256'],checks=checks,
        head_executed=bool(report.get('model_invoked')),changed_queries=report.get('changed_queries',0),baseline_control_sha256=digest(ROOT/'submission_guarded_tail_control.csv'),csv_sha256=digest(ROOT/'submission.csv'))
    (ROOT/'guarded_tail_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
GUARDED_TAIL_AUDIT=_observe_guarded_head_tail()
