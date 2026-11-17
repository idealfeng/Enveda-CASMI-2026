MODEL.save_model(str(WORK / 'isomer_ranker_model.txt'))
META = dict(features=F, thresholds={k: (v['margin'] if v else None) for k, v in TH.items()}, threshold_detail=TH,
            params={k: v for k, v in PARAMS.items() if k != 'num_threads'}, nround=NROUND, best_iteration=None,
            k1=[IR.K1_CHAN, IR.K1_FZ, IR.K1_POP], cap=IR.CAP, mass_tol=IR.MASS_TOL, max_spectra=IR.MAX_SPECTRA,
            molecules=len(MOLS), fitted_on=int(sum(M['y'].any() for M in MOLS)), seed=SEED, rdkit=rdBase.rdkitVersion,
            lightgbm=lgb.__version__, report=REPORT)
(WORK / 'isomer_ranker_meta.json').write_text(json.dumps(META, indent=1))
(WORK / 'isomer_ranker_report.json').write_text(json.dumps(REPORT, indent=1))
print(sorted(p.name for p in WORK.iterdir()))