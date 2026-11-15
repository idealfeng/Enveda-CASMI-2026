"""Execute the pinned corrected baseline once, then export its final candidates."""
import os,sys,json,hashlib
from pathlib import Path
from IPython.display import display
if __name__=='__main__':
    source=Path(sys.argv[1]); expected=sys.argv[2]; root=Path(sys.argv[3]).resolve()
    assert hashlib.sha256(source.read_bytes()).hexdigest()==expected, 'Source hash differs'
    assert not os.environ.get('INC_PANEL'), 'Replay input is not allowed'
    root.mkdir(parents=True,exist_ok=True); os.chdir(root)
    assert not (root/'work/spec_meta.parquet').exists(), 'Fresh pipeline directory required'
    assert not (root/'submission.csv').exists(), 'Fresh pipeline directory required'
    scope={'__name__':'__main__','display':display}
    for i,c in enumerate(json.loads(source.read_text())['cells']):
        if c['cell_type']!='code': continue
        print(f'PIPELINE CELL {i} START',flush=True)
        exec(compile(''.join(c['source']),f'pipeline_cell_{i}','exec'),scope)
        print(f'PIPELINE CELL {i} DONE',flush=True)
    assert 'candidate_promotion_evidence' in scope, 'Candidate-specific promotion fix missing'
    from export_evidence import export
    export(scope,root)
    (root/'execution_receipt.json').write_text(json.dumps(dict(source_sha256=expected,
        mode='submission',source_adaptations=[],candidate_promotion_fix=True,
        is_full_run=bool(scope['IS_RERUN']),processed_molecules=int(scope['te'].molecule_id.nunique())),indent=2))
