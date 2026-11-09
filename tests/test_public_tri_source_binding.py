"""Accept representation-only changes while rejecting changes to notebook contents."""
from pathlib import Path
from unittest import TestCase
import copy
import importlib.util
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('tri_source_binding_test_target',ROOT/'scripts/poll_public_tri_cloud.py')
action=importlib.util.module_from_spec(spec);spec.loader.exec_module(action)


class PublicTriSourceBindingTests(TestCase):
    def notebook(self):
        return dict(metadata=dict(language='python'),cells=[
            dict(cell_type='code',source=['a = 1\n','b = 2\n'],metadata={},outputs=[]),
            dict(cell_type='markdown',source=['credits\n'],metadata={})])

    def test_source_list_to_string_is_the_only_accepted_difference(self):
        first=self.notebook();second=copy.deepcopy(first)
        for cell in second['cells']:cell['source']=''.join(cell['source'])
        self.assertTrue(action.same_notebook_contents(json.dumps(first),json.dumps(second)))

    def test_changed_code_markdown_metadata_or_cell_count_is_rejected(self):
        for kind in ('code','markdown','metadata','cell_count'):
            with self.subTest(kind=kind):
                first=self.notebook();second=copy.deepcopy(first)
                if kind=='code':second['cells'][0]['source']=['a = 9\n','b = 2\n']
                elif kind=='markdown':second['cells'][1]['source']=['changed credits\n']
                elif kind=='metadata':second['metadata']['language']='other'
                else:second['cells'].pop()
                self.assertFalse(action.same_notebook_contents(json.dumps(first),json.dumps(second)))
