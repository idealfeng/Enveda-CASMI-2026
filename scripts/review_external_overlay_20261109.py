"""Independent stdlib/RDKit review of two external-overlay stages and CPU canary."""
from pathlib import Path
import ast,base64,copy,csv,hashlib,json,struct,sys,zlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from validation.metric import identity, assert_official_rdkit

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def source(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']
def frame(p):
    with Path(p).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def valid(s):
    values=s.split(';');keys=[identity(x) for x in values]
    return 1<=len(values)<=25 and all(values) and None not in keys and len(keys)==len(set(keys))

def main():
    assert_official_rdkit()
    baseline=read(ROOT/'submission/optimization_20261108/mass_guarded_head_tail_1108/notebook.ipynb')
    upstream_path=ROOT/'third_party/public_scan_alexchilton__casmi26-lb-0-484-peaks-to-structures-extlib_20261109/source.ipynb'
    upstream=read(upstream_path)
    original_tree=ast.parse(source(upstream['cells'][24]));fn=next(x for x in original_tree.body if isinstance(x,ast.FunctionDef) and x.name=='_apex_extlib_overlay')
    fn_raw=(ast.get_source_segment(source(upstream['cells'][24]),fn)+'\n').encode()
    helper_path=ROOT/'scripts/external_library_overlay_20261109.py'
    helper_tree=ast.parse(helper_path.read_text(encoding='utf-8'))
    observe=next(x for x in helper_tree.body if isinstance(x,ast.ClassDef) and x.name=='Observe')
    scope={'ast':ast};exec(compile(ast.Module(body=[observe],type_ignores=[]),'independent_transform','exec'),scope)
    original_function=ast.parse(fn_raw.decode());instrument=scope['Observe']();transformed=instrument.visit(copy.deepcopy(original_function))
    class RemoveObservers(ast.NodeTransformer):
        def visit_Expr(self,node):
            call=node.value
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id in ('_observe_reference','_observe_match'):return None
            return self.generic_visit(node)
    stripped=RemoveObservers().visit(copy.deepcopy(transformed))
    checks=dict(upstream_source_pin=sha(upstream_path)=='5ca30854be8f92e84a1510996ba71504537b849d3e7e2e77fd7c50ae2c1bf69c',
                only_three_observation_nodes_added=ast.dump(stripped,include_attributes=False)==ast.dump(original_function,include_attributes=False) and instrument.reference_sites==2 and instrument.match_sites==1,
                massbank_casmi_subset_filtered='(~mb_df.is_casmi_subset.astype(bool)) & mb_df.smiles.notna()' in fn_raw.decode())
    manifests={};details={};headers={}
    downloads=read(ROOT/'reports/public_baseline_scan_20261109_design/library_downloads.json')
    for item in downloads['files']:
        path=ROOT/Path(item['path'].replace('\\','/'))
        checks['download_'+item['file']]=path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
        with path.open('rb') as f:
            if path.suffix=='.npy':
                magic=f.read(8);n=struct.unpack('<H',f.read(2))[0];header=ast.literal_eval(f.read(n).decode().strip());headers[path.name]=header
                checks['header_'+item['file']]=magic==b'\x93NUMPY\x01\x00' and header['descr']=='<f4' and header['fortran_order'] is False
            else:
                first=f.read(4);f.seek(-4,2);checks['parquet_magic_'+item['file']]=first==f.read(4)==b'PAR1'
    checks['npy_shapes_match']=headers['ext_mz.npy']['shape']==headers['ext_in.npy']['shape']
    for name in ('public_alex_extlib','mass_guarded_extlib'):
        stage=ROOT/'submission/optimization_20261109'/name
        nb=read(stage/'notebook.ipynb');recipe=read(stage/'recipe.json');spec=read(stage/'branch_spec.json');receipt=read(stage/'prepare_receipt.json');metadata=read(stage/'kernel-metadata.json')
        branch_checks=dict(notebook_pin=sha(stage/'notebook.ipynb')==spec['notebook_sha256']==receipt['notebook_sha256'],
            metadata_pin=sha(stage/'kernel-metadata.json')==spec['metadata_sha256']==receipt['metadata_sha256'],
            recipe_pin=sha(stage/'recipe.json')==receipt['recipe_sha256'],
            helper_pin=sha(helper_path)==recipe['helper_sha256'],
            function_pin=hashlib.sha256(fn_raw).hexdigest()==recipe['original_function_sha256'],
            exact_constants=recipe['ranking_constants']==dict(TAU=.8,K_PEAKS=4,LIB_TAU=.9,precursor_ppm=10,precursor_da=.002,fragment_da=.015),
            datasets_versioned=all(x.rsplit('/',1)[1].isdigit() for x in metadata['dataset_sources']),
            libraries_attached='takumuhata/casmi26-extlib/2' in metadata['dataset_sources'] and 'samartalwar/casmi-2026-spectral-library-massbankharmonized/1' in metadata['dataset_sources'],
            private_offline_gpu=metadata['is_private'] is True and metadata['enable_gpu'] is True and metadata['enable_internet'] is False,
            all_code_compiles=True)
        for c in nb['cells']:
            if c['cell_type']=='code':compile(source(c),'independent_stage','exec')
        if name=='mass_guarded_extlib':
            branch_checks['exact_all_32_old_cells_retained']=len(baseline['cells'])==32 and nb['cells'][:32]==baseline['cells']
            branch_checks['exact_one_late_cell_appended']=len(nb['cells'])==33
            late=source(nb['cells'][-1])
            branch_checks['base_guarded_observer_bound']='GUARDED_TAIL_AUDIT' in late
        else:
            branch_checks['untouched_upstream_cells']=len(nb['cells'])==len(upstream['cells']) and all(source(a)==source(b) for i,(a,b) in enumerate(zip(upstream['cells'],nb['cells'])) if i not in (12,24))
            assign=next(n for n in ast.parse(source(nb['cells'][12])).body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='_external_core' for x in n.targets))
            decoded=zlib.decompress(base64.b64decode(ast.literal_eval(assign.value.args[0].args[0])))
            branch_checks['lossless_upstream_installer']=decoded==source(upstream['cells'][12]).encode()
            branch_checks['public_public_fallback_attachments']=not metadata['kernel_sources'] and not any(x.startswith('bgunshui/') for x in metadata['dataset_sources'])
            late=source(nb['cells'][24])
            branch_checks['public_fallback_failclosed_observer']="check('faithful_public_fallback'" in late and "models='public/public" in late
        tree=ast.parse(late)
        payloads=next(ast.literal_eval(n.value) for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='_external_payloads' for x in n.targets))
        branch_checks['exact_helper_payload']=base64.b64decode(payloads['external_library_overlay_20261109.py'])==helper_path.read_bytes()
        branch_checks['exact_original_function_payload']=base64.b64decode(payloads['alex_v12_external_function.py'])==fn_raw
        branch_checks['outer_global_failclosed']=any(isinstance(n,ast.ExceptHandler) and isinstance(n.type,ast.Name) and n.type.id=='BaseException' and "unlink(missing_ok=True)" in ast.unparse(n) for n in ast.walk(tree))
        for key,value in branch_checks.items():checks[name+'_'+key]=value
        details[name]=dict(checks=branch_checks,notebook_sha256=sha(stage/'notebook.ipynb'),helper_sha256=recipe['helper_sha256'],function_sha256=recipe['original_function_sha256'])
    canary_root=ROOT/'runs/external_overlay_actual_canary_20261109';verification=read(canary_root/'verification.json')
    checks['actual_five_file_canary_passed']=verification['status']=='passed' and all(verification['checks'].values())
    actual=canary_root/'hidden_actual';report=read(actual/'external_overlay_runtime.json');before=frame(actual/'submission_external_control.csv');proposal=frame(actual/'submission_external_proposed.csv');after=frame(actual/'submission.csv')
    matches={x['molecule_id']:x for x in report['actual_matches']};expected=[];accepted=[]
    for row in before:
        raw=row['smiles'];arr=raw.split(';');hit=matches.get(row['molecule_id']);value=raw
        if hit and hit['smiles'] is not None and hit['cosine'] is not None and hit['cosine']>=.8 and hit['matched_peaks']>=4:
            s=hit['smiles'];value=';'.join([s]+([x for x in arr if x!=s] if s in arr else arr))
            value=';'.join(value.split(';')[:25])
        expected.append(value);accepted.append(value if valid(value) else raw)
    checks['actual_scores_consumed_independent_reconstruction']=[r['smiles'] for r in proposal]==expected and [r['smiles'] for r in after]==accepted
    checks['actual_final_official_identity_valid']=all(valid(r['smiles']) for r in after)
    checks['actual_original_control_consumed']=sha(actual/'submission_pre_apex_extlib.csv')==sha(actual/'submission_external_control.csv')==report['control_sha256']
    checks['actual_final_sha_bound']=sha(actual/'submission.csv')==report['output_sha256']
    checks['both_real_reference_sources_loaded']=report['reference_counts']==dict(A=200724,B=124160)
    checks['actual_guarded_and_missing_queries_preserved']=next(r['smiles'] for r in after if r['molecule_id']=='protected')==next(r['smiles'] for r in before if r['molecule_id']=='protected') and next(r['smiles'] for r in after if r['molecule_id']=='missing_query')==next(r['smiles'] for r in before if r['molecule_id']=='missing_query')
    result=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,branches=details,npy_headers=headers,
        real_reference_counts=report['reference_counts'],real_hits=report['original_report']['hits'],accepted_changed_top1=report['changed_top1'],invalid_proposals_preserved=report['invalid_proposals_preserved'],
        observation_math_unchanged=True,own_public_scores=None,canary_is_interface_not_efficacy=True,
        explicit_adaptations=['fast-visible skip with required source hashes checked','three observation calls','per-query invalid/duplicate official identity proposal guard','global failure removes final CSV'],
        runtime_edges=['Missing query spectra keep that control, with no false observed-match record.','Protected original library>=.90 queries keep control.','No usable references from either required library is a global failure.','Missing/hash-mismatched/ambiguous source selection fails closed.','NaN/nonfinite cosine cannot create a positive match.','An empty overall control is not a meaningful hidden submission; upstream rejects it rather than silently scoring.','Public Alex fallback is public/public; no claimed newly trained second encoder.','Self-match canary validates wiring, not hidden coverage or leaderboard gain.'])
    out=ROOT/'reports/external_overlay_independent_review_20261109.json';out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],checks_passed=sum(checks.values()),checks_total=len(checks),failed=[k for k,v in checks.items() if not v],branches=details),ensure_ascii=False))
    if result['status']!='passed':raise ValueError('Independent external overlay review failed')

if __name__=='__main__':main()
