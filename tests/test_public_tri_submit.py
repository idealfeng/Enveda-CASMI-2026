"""Purely offline one-write/unknown-outcome boundaries for private tri-model V1."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import TestCase,mock
import json
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import submit_public_tri_cloud as submit


class SubmitTests(TestCase):
    def setUp(self):
        (ROOT/'.cache/tmp').mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(dir=ROOT/'.cache/tmp')
        self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        constants=dict(ROOT=self.root,RUN=self.root/'run.json',BINDING=self.root/'binding.json',
            VERIFY=self.root/'verify.json',STAGED=self.root/'notebook.ipynb',
            RECEIPT=self.root/'submission.json',RESULT=self.root/'status.json',HISTORY=self.root/'history.jsonl')
        for name,value in constants.items():
            patch=mock.patch.object(submit,name,value);patch.start();self.addCleanup(patch.stop)
        notebook=dict(nbformat=4,nbformat_minor=5,metadata={},cells=[dict(cell_type='code',source=['a=1\n'],metadata={},execution_count=None,outputs=[])])
        staged=json.dumps(notebook).encode();submit.STAGED.write_bytes(staged)
        notebook['cells'][0]['source']='a=1\n';self.server_source=json.dumps(notebook)
        self.run=dict(status='run_requested',target=submit.TARGET,version_number=1,
            notebook_sha256=submit.sha(staged),dataset_sources=['owner/data/versions/3'])
        self.write(submit.RUN,self.run)
        self.binding=dict(status='passed',target=submit.TARGET,version=1,
            checks={name:True for name in submit.REQUIRED_BINDING_CHECKS},staged_notebook_sha256=submit.sha(staged),
            server_source_sha256=submit.sha(self.server_source.encode()),dataset_sources=['owner/data'])
        self.write(submit.BINDING,self.binding)
        self.outputs=self.root/'outputs';self.outputs.mkdir()
        artifacts={'submission.csv':b'molecule_id,smiles\na,C\n',
            'public_neural_input_audit.json':b'{"status":"passed"}',
            'public_neural_execution_audit.json':b'{"status":"passed"}'}
        receipts=[]
        for name,raw in artifacts.items():
            path=self.outputs/name;path.write_bytes(raw)
            receipts.append(dict(name=name,path=str(path.relative_to(self.root)),bytes=len(raw),sha256=submit.sha(raw)))
        download=dict(status='downloaded',target=submit.TARGET,version=1,session_status='COMPLETE',missing_required=[],
            binding_sha256=submit.sha_file(submit.BINDING),notebook_sha256=self.run['notebook_sha256'],
            server_source_sha256=self.binding['server_source_sha256'],downloaded_files=receipts)
        self.write(self.outputs/'download_receipt.json',download)
        self.audit=dict(status='passed',target=submit.TARGET,version=1,
            checks={name:True for name in submit.REQUIRED_AUDIT_CHECKS},notebook_sha256=self.run['notebook_sha256'],
            downloaded_output_directory='outputs',submission_sha256=submit.sha(artifacts['submission.csv']),
            active_ids=[str(i) for i in range(12)],processed_molecules=12,input_molecules=400,
            placeholder_rows=388,submission_rows=400,is_full_run=False)
        self.write(submit.VERIFY,self.audit)

    def write(self,path,record):path.write_text(json.dumps(record),encoding='utf-8')

    def api(self):
        api=mock.MagicMock()
        api.kernels_status.return_value=NS(status=NS(name='COMPLETE'),failure_message='')
        api._kernel_version_label.return_value='v1'
        client=api.build_kaggle_client.return_value.__enter__.return_value
        client.kernels.kernels_api_client.get_kernel.return_value=NS(metadata=NS(ref=submit.TARGET,
            current_version_number=1,is_private=True,enable_internet=False,
            dataset_data_sources=['owner/data/versions/3'],kernel_data_sources=[]),blob=NS(source=self.server_source))
        client.competitions.competition_api_client.list_submissions.return_value=NS(
            submissions=[NS(ref=58021256,description='old'),NS(ref=77777777,description='unrelated')],next_page_token='')
        api.competition_get_submission_limits.return_value=NS(num_today=1,num_total=2,num_allowed_now=4)
        api.competition_submit_code.return_value=NS(ref=99000001,message='Success')
        client.competitions.competition_api_client.get_submission.return_value=NS(ref=99000001,
            description=submit.MESSAGE,file_name='submission.csv',status=NS(name='COMPLETE'),
            public_score='0.48123',error_description='',date=None)
        return api,client

    def test_only_one_code_write_after_durable_exclusive_claim(self):
        api,client=self.api()
        def response(**kwargs):
            claim=submit.read(submit.RECEIPT)
            self.assertEqual(claim['status'],'requesting_once')
            self.assertFalse(claim['automatic_retry_allowed'])
            self.assertEqual(claim['observed_existing_submission_refs'],[58021256,77777777])
            self.assertEqual(kwargs,dict(file_name='submission.csv',message=submit.MESSAGE,
                competition=submit.COMPETITION,kernel=submit.TARGET,kernel_version=1,quiet=True))
            return NS(ref=99000001,message='Success')
        api.competition_submit_code.side_effect=response
        with mock.patch.object(submit.os,'fsync',wraps=submit.os.fsync) as flush:
            result=submit.submit_once(api)
            self.assertGreaterEqual(flush.call_count,2)
        self.assertEqual(result['status'],'accepted')
        self.assertEqual(api.competition_submit_code.call_count,1)
        self.assertNotEqual(self.run['notebook_sha256'],self.binding['server_source_sha256'])
        api.kernels_status.assert_called_once_with(submit.TARGET+'/1')
        request=client.kernels.kernels_api_client.get_kernel.call_args.args[0]
        self.assertEqual(request.version_label,'v1')
        with self.assertRaises(RuntimeError):submit.submit_once(api)
        self.assertEqual(api.competition_submit_code.call_count,1)

    def test_bad_local_checks_and_changed_artifacts_stop_before_network(self):
        api,_=self.api()
        self.audit['checks']['official_rdkit']=1;self.write(submit.VERIFY,self.audit)
        with self.assertRaises(ValueError):submit.submit_once(api)
        api.kernels_status.assert_not_called()
        self.audit['checks']['official_rdkit']=True;self.write(submit.VERIFY,self.audit)
        (self.outputs/'submission.csv').write_bytes(b'changed')
        with self.assertRaises(ValueError):submit.submit_once(api)
        api.kernels_status.assert_not_called()

    def test_bad_stage_binding_and_false_full_scope_stop_locally(self):
        api,_=self.api()
        self.binding['checks']['source_semantics']=False;self.write(submit.BINDING,self.binding)
        with self.assertRaises(ValueError):submit.submit_once(api)
        self.binding['checks']['source_semantics']=True;self.write(submit.BINDING,self.binding)
        self.audit['is_full_run']=True;self.write(submit.VERIFY,self.audit)
        with self.assertRaises(ValueError):submit.submit_once(api)
        self.audit['is_full_run']=False;self.write(submit.VERIFY,self.audit)
        submit.STAGED.write_text('{}')
        with self.assertRaises(ValueError):submit.submit_once(api)
        api.kernels_status.assert_not_called()

    def test_running_live_or_wrong_remote_contents_never_claim_or_write(self):
        api,client=self.api();api.kernels_status.return_value.status.name='RUNNING'
        with self.assertRaises(ValueError):submit.submit_once(api)
        api.kernels_status.return_value.status.name='COMPLETE'
        client.kernels.kernels_api_client.get_kernel.return_value.blob.source='{"cells":[]}'
        with self.assertRaises(ValueError):submit.submit_once(api)
        self.assertFalse(submit.RECEIPT.exists());api.competition_submit_code.assert_not_called()

    def test_duplicate_description_on_next_page_stops_before_claim(self):
        api,client=self.api()
        client.competitions.competition_api_client.list_submissions.side_effect=[
            NS(submissions=[NS(ref=58021256,description='old')],next_page_token='page2'),
            NS(submissions=[NS(ref=99000001,description=submit.MESSAGE)],next_page_token='')]
        with self.assertRaises(ValueError):submit.submit_once(api)
        self.assertFalse(submit.RECEIPT.exists());api.competition_submit_code.assert_not_called()
        requests=client.competitions.competition_api_client.list_submissions.call_args_list
        self.assertEqual(requests[1].args[0].page_token,'page2')

    def test_no_allowance_never_claims(self):
        api,_=self.api();api.competition_get_submission_limits.return_value.num_allowed_now=0
        with self.assertRaises(ValueError):submit.submit_once(api)
        self.assertFalse(submit.RECEIPT.exists());api.competition_submit_code.assert_not_called()

    def test_network_unknown_persists_claim_and_never_retries_or_poll_reconciles(self):
        api,_=self.api()
        api.competition_submit_code.side_effect=TimeoutError('https://secret.invalid/?token=credential')
        result=submit.submit_once(api)
        self.assertEqual(result['status'],'request_outcome_unknown_no_retry')
        raw=submit.RECEIPT.read_text()
        self.assertNotIn('secret.invalid',raw);self.assertNotIn('credential',raw)
        with self.assertRaises(RuntimeError):submit.submit_once(api)
        with self.assertRaises(ValueError):submit.poll(api)
        self.assertEqual(api.competition_submit_code.call_count,1)

    def test_zero_or_boolean_response_ref_is_not_accepted(self):
        api,_=self.api();api.competition_submit_code.return_value.ref=0
        result=submit.submit_once(api)
        self.assertEqual(result['status'],'server_response_requires_review_no_retry')
        self.assertIsNone(result['submission_ref'])
        with self.assertRaises(ValueError):submit.poll(api)

    def test_poll_reads_only_the_fixed_positive_ref(self):
        api,client=self.api();submit.submit_once(api)
        api.reset_mock();result=submit.poll(api)
        self.assertEqual(result['public_score'],'0.48123');self.assertTrue(result['public_score_available'])
        api.competition_submit_code.assert_not_called();api.kernels_status.assert_not_called()
        request=client.competitions.competition_api_client.get_submission.call_args.args[0]
        self.assertEqual(request.ref,99000001)
        self.assertEqual(submit.read(submit.RESULT)['submission_ref'],99000001)

    def test_wrong_poll_identity_and_nonfinite_score_are_not_accepted(self):
        api,client=self.api();submit.submit_once(api)
        item=client.competitions.competition_api_client.get_submission.return_value
        item.ref=99000002
        with self.assertRaises(ValueError):submit.poll(api)
        self.assertFalse(submit.RESULT.exists())
        item.ref=99000001;item.public_score='nan'
        result=submit.poll(api)
        self.assertFalse(result['public_score_available']);self.assertIsNone(result['public_score'])
