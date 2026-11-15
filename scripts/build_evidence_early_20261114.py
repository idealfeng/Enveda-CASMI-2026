"""Freeze two actual aggregate-evidence explorations on the exact champion."""
from pathlib import Path
import base64
import copy
import hashlib
import importlib.util
import json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'submission/optimization_20261109/mass_guarded_extlib'
MODULE=ROOT/'scripts/evidence_early_overlay_20261114.py'
CHAMPION='2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7'
ARMS={
    'gl_evidence_early': dict(title='CASMI26 gl evidence early 1114',
        target='stormseye/casmi26-gl-evidence-early-1114',
        method='Same-formula observed ranks2-25: standardized original rank prior plus GL evidence, fixed weight1; original top1 and strong library/AB rows remain'),
    'dual_evidence_agreement': dict(title='CASMI26 dual evidence agreement 1114',
        target='stormseye/casmi26-dual-evidence-agreement-1114',
        method='GL and ICE agree on a same-formula candidate at original rank<=10, with both standardized winner margins>=.1 and common coverage>=.8: swap it to top1; strong library/AB rows remain'),
}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def main():
    assert sha(BASE/'notebook.ipynb')==CHAMPION
    spec=importlib.util.spec_from_file_location('_evidence_frozen',MODULE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    payload=MODULE.read_bytes();pin=sha(MODULE);parent=read(BASE/'notebook.ipynb')
    for branch,arm in ARMS.items():
        out=ROOT/'submission/optimization_20261114'/branch
        if out.exists():raise FileExistsError('Preserve frozen evidence stage')
        recipe=dict(branch=branch,target=arm['target'],parent_ref=58156482,parent_public=.488,
            parent_notebook_sha256=CHAMPION,method=arm['method'],configuration=module.CONFIGS[branch],
            score_sources=['gl_work/gl_out.json','ice_work/ice_out.json'],
            score_missing_policy='Raw string then official key; unambiguous same-identity alias only; missing/NaN/ambiguous stays missing, never zero.',
            module_sha256=pin,module_local=MODULE.relative_to(ROOT).as_posix(),
            original_cells_unchanged=len(parent['cells']),new_training=False,new_candidates=False,
            new_spectra=False,uses_aggregate_scores=True,uses_per_CE_trace=False,
            full_pipeline_local_validation=False,truth_metrics_computed=False,gain_claim=False,
            experiment_type='user_authorized_speculative_submission',
            comparison_scope='Complete exact original .488 then evidence; this changes how existing simulator evidence influences final ranks, not a new model or a CE consensus feature.')
        raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode();rp=hashlib.sha256(raw).hexdigest()
        cell=r'''
# Fixed actual forward-spectrum evidence exploration after complete champion AB.
import base64 as _eb64,hashlib as _eh,importlib.util as _ei
try:
    _evidence_payload=_eb64.b64decode(__PAYLOAD__)
    assert _eh.sha256(_evidence_payload).hexdigest()==__MODULE_PIN__
    (CODE/'evidence_early_overlay.py').write_bytes(_evidence_payload)
    _evidence_spec=_ei.spec_from_file_location('_actual_evidence_early',CODE/'evidence_early_overlay.py')
    _evidence_module=_ei.module_from_spec(_evidence_spec);_evidence_spec.loader.exec_module(_evidence_module)
    EVIDENCE_EARLY_REPORT=_evidence_module.run(ROOT,IS_RERUN,SAMPLE_IDS,EXTERNAL_OVERLAY_AUDIT,__BRANCH__,__RECIPE_PIN__)
    EVIDENCE_EARLY_AUDIT=_evidence_module.audit(ROOT,IS_RERUN,SAMPLE_IDS,EXTERNAL_OVERLAY_AUDIT,__BRANCH__,__RECIPE_PIN__,__MODULE_PIN__)
except BaseException:
    (ROOT/'submission.csv').unlink(missing_ok=True)
    raise
'''
        for k,v in dict(__PAYLOAD__=repr(base64.b64encode(payload).decode()),__MODULE_PIN__=repr(pin),
                        __BRANCH__=repr(branch),__RECIPE_PIN__=repr(rp)).items():cell=cell.replace(k,v)
        book=copy.deepcopy(parent);book['cells'].append(dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=cell))
        assert book['cells'][:-1]==parent['cells']
        for c in book['cells']:
            if c['cell_type']=='code':compile(''.join(c['source']),'frozen_evidence_stage','exec')
        meta=read(BASE/'kernel-metadata.json');meta.update(id=arm['target'],title=arm['title'])
        out.mkdir(parents=True);save(out/'notebook.ipynb',book);save(out/'kernel-metadata.json',meta);(out/'recipe.json').write_bytes(raw)
        review=dict(status='passed',target=arm['target'],version=1,notebook_sha256=sha(out/'notebook.ipynb'),
            checks=dict(exact_parent_pin=True,all_original_cells_unchanged=True,original_head_AB_retained=True,
                only_one_appended_cell=True,original_dataset_pins_retained=True,private_offline_gpu=True,
                module_payload_pinned=True,source_compiles=True,errors_fail_closed=True),
            boundary='Static stage binding only; real changed components separately checked, not new full production inference or efficacy.')
        save(out/'static_review.json',review)
        audits=copy.deepcopy(read(BASE/'branch_spec.json')['required_runtime_audits'])
        audits.append(dict(name='evidence_early_audit.json',expected_fields=dict(status='passed',branch=branch,mode='fast_static',recipe_sha256=rp),
            required_true_checks=['base_ab_passed','control_bound','final_bound','module_pin','configuration_exact',
                'recipe_branch_bound','sample_ids_exact','csv_schema','candidate_multisets','official_identities','fast_no_evidence']))
        branch_spec=dict(name=branch,target=arm['target'],version=1,stage_dir=out.relative_to(ROOT).as_posix(),
            notebook_sha256=sha(out/'notebook.ipynb'),metadata_sha256=sha(out/'kernel-metadata.json'),
            description='CASMI26 20261114 '+branch+' actual GL ICE scores after original 0488 V1',
            validation_mode='fast_static',static_review_path=(out/'static_review.json').relative_to(ROOT).as_posix(),required_runtime_audits=audits)
        save(out/'branch_spec.json',branch_spec)
        receipt=dict(status='prepared_pending_component_smoke',branch=branch,notebook_sha256=branch_spec['notebook_sha256'],
            recipe_sha256=rp,module_sha256=pin,parent_sha256=CHAMPION,no_cloud_write=True)
        save(out/'prepare_receipt.json',receipt);print(json.dumps(receipt))


if __name__=='__main__':main()
