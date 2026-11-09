"""Offline protection tests for new fast-commit neural-only branches."""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build_aggressive',ROOT/'scripts/build_aggressive_variants_20261107.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)


class VariantTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        import pandas as pd
        self.np,self.pd=np,pd
        temp=ROOT/'.cache/variant-fixtures-20261107';temp.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=temp);self.base=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()

    def blend_scope(self,weights):
        parsed=ast.parse(build.SCHEDULER.replace('__RECIPE__','{}').replace('__RECIPE_SHA__','fixture'))
        functions=[node for node in parsed.body if isinstance(node,ast.FunctionDef) and node.name in ('_batch_sha','_batch_blend')]
        scope=dict(Path=Path,hashlib=hashlib,pd=self.pd,np=self.np,BATCH_RECIPE={'weights':weights})
        exec(compile(ast.Module(body=functions,type_ignores=[]),'fixture-blend','exec'),scope)
        return scope

    def frames(self):
        common=dict(molecule_id=['a','a','b','b'],smiles=['C','CC','C','CC'],baseline_rank=[1,2,1,2],
            processed=[True,True,True,True],neural_ok=[True,True,False,False],n_spectra=[1,1,0,0])
        a=self.pd.DataFrame(common);b=a.copy()
        a['neural_score']=[.25,.75,0.,0.];b['neural_score']=[.75,.25,0.,0.]
        for column in ('neural_cos','neural_fp','neural_std'):
            a[column]=[.1,.2,0.,0.];b[column]=[.3,.1,0.,0.]
        paths={'public':self.base/'public.parquet','v2':self.base/'v2.parquet'}
        a.to_parquet(paths['public'],index=False);b.to_parquet(paths['v2'],index=False)
        return a,b,paths

    def test_blend_exact_and_common_unsupported(self):
        a,b,paths=self.frames();scope=self.blend_scope({'public':.5,'v2':.5})
        report=scope['_batch_blend'](paths,self.base/'combined.parquet')
        combined=self.pd.read_parquet(self.base/'combined.parquet')
        self.assertEqual(report['combined_score_max_abs_difference'],0.)
        self.assertEqual(report['usable_candidates'],2)
        self.assertEqual(report['usable_molecules'],1)
        self.assertTrue(combined.neural_score.eq(0.).all())
        self.assertEqual(combined.neural_ok.tolist(),a.neural_ok.tolist())

    def test_changed_coverage_and_keys_rejected(self):
        a,b,paths=self.frames();scope=self.blend_scope({'public':.5,'v2':.5})
        b.loc[2,'neural_ok']=True;b.to_parquet(paths['v2'],index=False)
        with self.assertRaises(AssertionError):scope['_batch_blend'](paths,self.base/'bad.parquet')
        b=a.iloc[:3];b.to_parquet(paths['v2'],index=False)
        with self.assertRaises(AssertionError):scope['_batch_blend'](paths,self.base/'bad2.parquet')

    def test_full_fast_scheduler_and_observer_never_call_models(self):
        recipe=json.loads((ROOT/'submission/aggressive_20261107/flex_tri_only/recipe.json').read_text())
        inputs=self.base/'input';inputs.mkdir();public=inputs/'public';public.mkdir()
        def put(folder,name,value):
            folder.mkdir(parents=True,exist_ok=True);p=folder/name;p.write_bytes(value)
            return hashlib.sha256(value).hexdigest()
        recipe['public_pins']={name:put(public,name,('public-'+name).encode()) for name in build.PUBLIC_PINS}
        for name,wanted in recipe['models'].items():
            folder=inputs/wanted['slug']
            wanted['checkpoint']=put(folder,'final_model.pt',('weights-'+name).encode())
            wanted['config']=put(folder,'config_used.json',('config-'+name).encode())
        work=self.base/'work';work.mkdir();comp=self.base/'competition';comp.mkdir()
        ids=['m'+str(i).zfill(4) for i in range(400)]
        self.pd.DataFrame({'molecule_id':ids,'smiles':['CCO']*400}).to_csv(comp/'sample_submission.csv',index=False)
        calls=[]
        def pipeline():calls.append('pipeline-fast-return');return False
        def forbidden(*args,**kwargs):raise AssertionError('A fast-static fixture called a model/consensus stage')
        import shutil
        scope=dict(recipe['config'],Path=Path,pd=self.pd,np=self.np,hashlib=hashlib,shutil=shutil,json=json,
            ROOT=work,INPUT=inputs,COMP=comp,SAMPLE_IDS=ids,RUN_PIPELINE=False,IS_RERUN=False,
            materialise_sources=lambda:str(public),run_public_pipeline=pipeline,
            score_final_lists=forbidden,score_outside_candidates=forbidden,build_consensus=forbidden,
            choose_and_submit=forbidden,run_stage=forbidden)
        scheduler=build.SCHEDULER.replace('__RECIPE__',repr(recipe)).replace('__RECIPE_SHA__','fixture')
        exec(compile(scheduler,'fixture-fast-scheduler','exec'),scope)
        observer=build.OBSERVER.replace('__RECIPE_SHA__','fixture')
        exec(compile(observer,'fixture-fast-observer','exec'),scope)
        result=json.loads((work/'batch_variant_audit.json').read_text())
        self.assertEqual(result['status'],'passed');self.assertEqual(result['mode'],'fast_static')
        self.assertEqual(result['processed_molecules'],0);self.assertEqual(result['submission_rows'],400)
        self.assertIsNone(result['main_ensemble']);self.assertTrue(all(result['checks'].values()))
        self.assertEqual(calls,['pipeline-fast-return'])


if __name__=='__main__':unittest.main()
