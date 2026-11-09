"""Verify lossless compact packaging and the actual deployed learned-head observer."""
import ast
import base64
import contextlib
import hashlib
import io
import json
from pathlib import Path
import zlib

from review_head_observers_20261108 import fixture,read,sha,source,write

ROOT=Path(__file__).resolve().parents[1]


def main():
    stage=ROOT/'submission/optimization_20261108/mass_heads_na_compact'
    old_stage=ROOT/'submission/optimization_20261108/mass_heads_na'
    before=sha(stage/'notebook.ipynb')
    current,old=read(stage/'notebook.ipynb'),read(old_stage/'notebook.ipynb')
    receipt=read(stage/'prepare_receipt.json')
    text=source(current['cells'][11]);tree=ast.parse(text)
    assignment=next(n for n in tree.body if isinstance(n,ast.Assign)
                    and any(isinstance(t,ast.Name) and t.id=='_casmi_compact_source' for t in n.targets))
    encoded=ast.literal_eval(assignment.value.args[0].args[0])
    decoded=zlib.decompress(base64.b64decode(encoded))
    scope={}
    with contextlib.redirect_stdout(io.StringIO()):exec(compile(text,'actual-lossless-wrapper','exec'),scope)
    checks=dict(notebook_sha_matches_receipt=before==receipt['notebook_sha256'],
        notebook_sha_expected_final=before=='4b985a2a0e2cb501be2fb045993cf1fc182886cfc6bf818c102c54f4d5bbb4a6',
        decoded_cell11_byte_identical=decoded==source(old['cells'][11]).encode('utf-8'),
        decoded_source_guard=scope['_casmi_compact_source']==decoded,
        embedded_module_hashes=all(hashlib.sha256(v.encode()).hexdigest()==scope['MODULE_SHA256'][k]
                                   for k,v in scope['MODULES'].items()),
        frozen_source_pin=hashlib.sha256(base64.b64decode(scope['FROZEN_B64'])).hexdigest()==scope['FROZEN_SHA256'],
        actual_head_installer_byte_identical=source(current['cells'][14])==source(old['cells'][14]),
        unchanged_other_cell_texts=len(current['cells'])==len(old['cells']) and all(
            source(a)==source(b) for i,(a,b) in enumerate(zip(current['cells'],old['cells'])) if i not in (11,31)),
        source_under_one_mib=(stage/'notebook.ipynb').stat().st_size<1024*1024)
    # An otherwise valid new compressed payload must hit the guard before executing it.
    bad_payload=base64.b64encode(zlib.compress(decoded+b'\n# altered payload\n')).decode()
    bad=text.replace(encoded,bad_payload)
    try:exec(compile(bad,'corrupt-lossless-wrapper-fixture','exec'),{})
    except AssertionError:checks['altered_decoded_source_rejected_before_execution']=True
    else:checks['altered_decoded_source_rejected_before_execution']=False
    def remove_expected(cell):
        node=ast.parse(source(cell))
        fn=next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name=='_observe_learned_head')
        for n in fn.body:
            if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='expected' for t in n.targets):
                n.value=ast.Constant(None)
        return ast.dump(node,include_attributes=False)
    checks['head_observer_only_rebound_identity']=remove_expected(current['cells'][31])==remove_expected(old['cells'][31])
    fast=fixture(stage,'fast');hidden=fixture(stage,'hidden');optional=fixture(stage,'hidden',outsider=False)
    checks.update(actual_fast_observer=fast['accepted'],actual_hidden_main_outside_observer=hidden['accepted'],
                  original_optional_outside_skip=optional['accepted'])
    failures=('bad_coverage','bad_query_coverage','bad_encoder','bad_head_receipt','bad_output_hash',
              'bad_evidence_hash','bad_query_hash','bad_row_count','bad_error_scope','head_not_applied',
              'bad_status','corrupt_adapter','corrupt_checkpoint','corrupt_original','corrupt_runtime','bad_outsider_coverage')
    rejected={key:fixture(stage,'hidden',key) for key in failures}
    checks.update({key+'_rejected':not value['accepted'] for key,value in rejected.items()})
    checks['no_stage_bytes_changed']=sha(stage/'notebook.ipynb')==before
    report=dict(status='passed' if all(checks.values()) else 'failed',branch='mass_heads_na_compact',
        notebook_sha256=before,metadata_sha256=sha(stage/'kernel-metadata.json'),
        decoded_cell11_sha256=hashlib.sha256(decoded).hexdigest(),source_bytes=(stage/'notebook.ipynb').stat().st_size,
        checks=checks,fast=fast,hidden=hidden,optional_skipped=optional,rejected=rejected,
        no_gpu_cloud_training_or_predictions=True,no_stage_bytes_changed=True,
        fixture_scope='Lossless packaging and actual head observer; no model-quality or score claim')
    out=ROOT/'reports/head_submission_review_20261108/compact';out.mkdir(parents=True,exist_ok=True)
    write(out/'verification.json',report)
    print(json.dumps(dict(status=report['status'],checks_passed=sum(checks.values()),checks_total=len(checks),
                         notebook_sha256=before,source_bytes=report['source_bytes']),indent=2))
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
