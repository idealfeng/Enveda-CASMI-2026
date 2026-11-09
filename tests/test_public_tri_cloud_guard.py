"""Cloud Save&Run duplicate/overwrite guards, with a mocked API only."""
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock
import importlib.util
import json
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('public_tri_cloud_guard_target',ROOT/'scripts/start_public_tri_cloud.py')
action=importlib.util.module_from_spec(spec)
spec.loader.exec_module(action)


class PublicTriCloudGuardTests(TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(dir=ROOT/'.cache/tmp')
        self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name)
        self.stage=self.base/'stage';self.stage.mkdir()
        self.receipt=self.base/'claim.json'
        self.metadata=dict(id=action.TARGET,is_private=True,enable_internet=False,enable_gpu=True,
            dataset_sources=sorted(action.EXPECTED_DATASETS),kernel_sources=[],model_sources=[],
            competition_sources=['enveda-CASMI26-molecule-id-mass-spectra'])
        (self.stage/'notebook.ipynb').write_text('{"cells":[]}')
        self.write_metadata()
        for key,value in [('STAGE',self.stage),('RECEIPT',self.receipt)]:
            patch=mock.patch.object(action,key,value);patch.start();self.addCleanup(patch.stop)

    def write_metadata(self):
        (self.stage/'kernel-metadata.json').write_text(json.dumps(self.metadata))
        (self.stage/'prepare_receipt.json').write_text(json.dumps(dict(status='prepared',target=action.TARGET,
            notebook_sha256=action.sha(self.stage/'notebook.ipynb'),metadata_sha256=action.sha(self.stage/'kernel-metadata.json'))))

    def api(self):
        api=mock.MagicMock();api.kernels_list.return_value=[]
        api.kernels_push.return_value=SimpleNamespace(ref='/code/'+action.TARGET,
            url='https://www.kaggle.com/code/'+action.TARGET,version_number=1,error='',
            invalid_tags=[],invalid_dataset_sources=[],invalid_competition_sources=[],invalid_kernel_sources=[],invalid_model_sources=[])
        return api

    def test_existing_claim_prevents_all_api_reads_and_writes(self):
        self.receipt.write_text('{"status":"request_outcome_unknown_no_retry"}')
        with mock.patch.object(action,'make_api') as make:
            with self.assertRaises(RuntimeError):action.main()
            make.assert_not_called()

    def test_changed_source_or_public_online_metadata_prevents_network(self):
        for kind in ('source','privacy','internet'):
            with self.subTest(kind=kind):
                self.metadata['is_private']=kind!='privacy';self.metadata['enable_internet']=kind=='internet'
                self.write_metadata()
                if kind=='source':(self.stage/'notebook.ipynb').write_text('changed')
                with mock.patch.object(action,'make_api') as make:
                    with self.assertRaises(ValueError):action.main()
                    make.assert_not_called()

    def test_existing_remote_notebook_is_never_overwritten(self):
        api=self.api();api.kernels_list.return_value=[SimpleNamespace(ref=action.TARGET)]
        with mock.patch.object(action,'make_api',return_value=api):
            with self.assertRaises(ValueError):action.main()
        api.kernels_push.assert_not_called();self.assertFalse(self.receipt.exists())

    def test_claim_is_durable_before_single_run_and_unknown_outcome_is_not_retried(self):
        api=self.api()
        def write_once(*args,**kwargs):
            self.assertEqual(json.loads(self.receipt.read_text())['status'],'requesting_create_and_run')
            self.assertIs(kwargs['no_run'],False)
            raise TimeoutError()
        api.kernels_push.side_effect=write_once
        with mock.patch.object(action,'make_api',return_value=api):
            with self.assertRaises(TimeoutError):action.main()
            with self.assertRaises(RuntimeError):action.main()
        api.kernels_push.assert_called_once()
        self.assertEqual(json.loads(self.receipt.read_text())['status'],'request_outcome_unknown_no_retry')

    def test_server_target_mismatch_is_not_accepted(self):
        api=self.api();api.kernels_push.return_value.ref='/code/stormseye/unexpected'
        with mock.patch.object(action,'make_api',return_value=api):result=action.main()
        self.assertEqual(result['status'],'server_response_requires_review')
