"""No-network boundary checks for the V1 downloader and official-identity audit."""
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock
import hashlib
import json
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import download_public_tri_cloud as download
import verify_public_tri_cloud as verify


class Response:
    def __init__(self,raw=b'{}',length=True,url='https://example.invalid/output'):
        self.raw=raw;self.url=url;self.headers={'Content-Length':str(len(raw))} if length else {}
        self.blocks_read=0
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def raise_for_status(self):pass
    def iter_content(self,size):
        for start in range(0,len(self.raw),4):
            self.blocks_read+=1
            yield self.raw[start:start+4]


class OutputTests(TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(dir=ROOT/'.cache/tmp')
        self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.run=self.root/'run.json';self.binding=self.root/'binding.json'
        self.run.write_text(json.dumps(dict(target=download.TARGET,status='run_requested',version_number=1,notebook_sha256='a'*64)))
        self.binding.write_text(json.dumps(dict(target=download.TARGET,status='passed',version=1,
            checks=dict(private=True,internet_off=True,source_semantics=True),
            staged_notebook_sha256='a'*64,server_source_sha256='b'*64)))
        for module in (download,verify):
            for name,value in [('ROOT',self.root),('RUN_RECEIPT',self.run),('BINDING',self.binding)]:
                patch=mock.patch.object(module,name,value);patch.start();self.addCleanup(patch.stop)

    def api(self,files):
        api=mock.MagicMock()
        api.kernels_status.return_value=SimpleNamespace(status=SimpleNamespace(name='COMPLETE'),failure_message='')
        api._kernel_version_label.return_value='v1'
        api.build_kaggle_client.return_value.__enter__.return_value.kernels.kernels_api_client.list_kernel_session_output.return_value=SimpleNamespace(
            files=[SimpleNamespace(file_name=name,url='https://example.invalid/'+name) for name in files],
            next_page_token='',log='')
        return api

    def test_complete_v1_only_downloads_whitelisted_small_files(self):
        names=list(download.REQUIRED)+['huge_unselected.pt','n1x:unselected-cache.bin']
        api=self.api(names);called=[]
        def get(url,**kwargs):
            called.append(url)
            self.assertEqual(kwargs['timeout'],(15,45))
            return Response(b'molecule_id,smiles\na,C\n' if url.endswith('.csv') else b'{"status":"passed"}',url=url)
        result=download.download(self.root/'outputs',api=api,get=get)
        self.assertEqual(result['status'],'downloaded')
        self.assertEqual(len(called),3)
        self.assertNotIn('example.invalid',json.dumps(result))
        request=api.build_kaggle_client.return_value.__enter__.return_value.kernels.kernels_api_client.list_kernel_session_output.call_args.args[0]
        self.assertEqual(request.version_label,'v1')
        self.assertEqual(api.kernels_status.call_args.args[0],download.TARGET+'/1')

    def test_semantic_binding_does_not_require_raw_notebook_bytes_equal(self):
        run,binding=download.prerequisites()
        self.assertNotEqual(run['notebook_sha256'],binding['server_source_sha256'])
        changed=json.loads(self.binding.read_text());changed['checks']['source_semantics']=False
        self.binding.write_text(json.dumps(changed))
        api=self.api(download.REQUIRED)
        with self.assertRaises(ValueError):download.download(self.root/'blocked',api=api)
        api.kernels_status.assert_not_called()

    def test_running_version_and_existing_directory_are_not_downloaded(self):
        api=self.api(download.REQUIRED)
        api.kernels_status.return_value.status.name='RUNNING'
        result=download.download(self.root/'running',api=api,get=mock.Mock())
        self.assertEqual(result['status'],'download_failed')
        api.build_kaggle_client.assert_not_called()
        with self.assertRaises(ValueError):download.download(self.root/'running',api=self.api(download.REQUIRED))

    def test_filename_escape_and_https_downgrade_rejected(self):
        for name in ('../outside.json','/absolute.csv','C:/outside.csv','nested\\outside.csv'):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):download.destination_for(self.root,name)
        import requests
        with self.assertRaises(ValueError):download.fetch_bounded('http://example.invalid/a',20,requests,get=mock.Mock())
        with self.assertRaises(ValueError):download.fetch_bounded('https://example.invalid/a',20,requests,
            get=lambda *a,**k:Response(url='http://example.invalid/redirect'))

    def test_declared_and_streaming_caps_are_enforced(self):
        import requests
        response=Response(b'12345678')
        with self.assertRaises(ValueError):download.fetch_bounded('https://example.invalid/a',7,requests,get=lambda *a,**k:response)
        self.assertEqual(response.blocks_read,0)
        with self.assertRaises(ValueError):download.fetch_bounded('https://example.invalid/a',7,requests,
            get=lambda *a,**k:Response(b'12345678',length=False))

    def test_read_retries_are_bounded_and_403_is_not_retried(self):
        import requests
        call=mock.Mock(side_effect=requests.exceptions.Timeout())
        with mock.patch.object(download.time,'sleep'):
            with self.assertRaises(requests.exceptions.Timeout):download.retry_read(call,requests)
        self.assertEqual(call.call_count,3)
        forbidden=requests.exceptions.HTTPError(response=SimpleNamespace(status_code=403))
        call=mock.Mock(side_effect=forbidden)
        with self.assertRaises(requests.exceptions.HTTPError):download.retry_read(call,requests)
        self.assertEqual(call.call_count,1)

    def fixtures(self,duplicate=False):
        output=self.root/'verify_outputs';output.mkdir()
        sample=self.root/'sample.csv'
        ids=[f'm_{i:04}' for i in range(400)]
        sample.write_text('molecule_id,smiles\n'+''.join(mid+',C\n' for mid in ids))
        (output/'submission.csv').write_text('molecule_id,smiles\n'+''.join(
            mid+(',C;C\n' if duplicate and index==0 else ',C;CC\n') for index,mid in enumerate(ids)))
        pre=dict(status='passed',upstream_source_sha256=verify.UPSTREAM_SHA,smoke_source_sha256=verify.SMOKE_SHA,
            scoring_or_candidate_changes=False,inputs=dict(public=dict(pins=verify.PUBLIC_PINS),lotus=dict(sha256=verify.LOTUS_SHA),
                **{name:dict(value) for name,value in verify.MODELS.items()}))
        (output/'public_neural_input_audit.json').write_text(json.dumps(pre))
        models={}
        for name in ('public','v2','v4'):
            pins=dict(verify.PUBLIC_PINS)
            if name!='public':pins.update({'final_model.pt':verify.MODELS[name]['checkpoint_sha256'],'config.json':verify.MODELS[name]['config_sha256']})
            models[name]=dict(pins=pins,active_candidates=24,usable_candidates=24,usable_molecules=12,unsupported_molecules=[])
        runtime=dict(status='passed',upstream_source_sha256=verify.UPSTREAM_SHA,smoke_source_sha256=verify.SMOKE_SHA,
            scoring_or_candidate_changes=False,input_audit_sha256=verify.sha(output/'public_neural_input_audit.json'),
            checks={name:True for name in verify.REQUIRED_RUNTIME_CHECKS|{'visible_smoke12','visible_all_active_usable'}},
            models=models,active_ids=ids[:12],processed_molecules=12,input_molecules=400,placeholder_rows=388,
            is_full_run=False,combined_score_max_abs_difference=0,submission=dict(rows=400,
                sha256=verify.sha(output/'submission.csv'),bytes=(output/'submission.csv').stat().st_size))
        (output/'public_neural_execution_audit.json').write_text(json.dumps(runtime))
        receipt=dict(status='downloaded',target=verify.TARGET,version=1,session_status='COMPLETE',missing_required=[],
            notebook_sha256='a'*64,server_source_sha256='b'*64,binding_sha256=verify.sha(self.binding),downloaded_files=[])
        for name in download.REQUIRED:
            receipt['downloaded_files'].append(dict(name=name,path=str((output/name).relative_to(self.root)),
                bytes=(output/name).stat().st_size,sha256=verify.sha(output/name)))
        (output/'download_receipt.json').write_text(json.dumps(receipt))
        return output,sample

    def test_verifier_accepts_inactive_lotus_rows_and_records_duplicate_slots(self):
        output,sample=self.fixtures(duplicate=True)
        from validation import metric
        with mock.patch.object(verify,'SAMPLE',sample),mock.patch.object(metric,'assert_official_rdkit',return_value='2026.03.3'), \
             mock.patch.object(metric,'identity',side_effect=lambda value:{'C':'A'*14,'CC':'B'*14}.get(value)):
            result=verify.verify(output)
        self.assertEqual(result['status'],'passed')
        self.assertEqual(result['placeholder_rows'],388)
        self.assertEqual(result['csv_identity_diagnostics']['duplicate_identity_slots'],1)
        self.assertTrue(result['warnings'])

    def test_changed_downloaded_csv_is_rejected_before_identity_evaluation(self):
        output,sample=self.fixtures()
        with (output/'submission.csv').open('a') as stream:stream.write('unexpected,C\n')
        with mock.patch.object(verify,'SAMPLE',sample):
            with self.assertRaises(ValueError):verify.verify(output)
