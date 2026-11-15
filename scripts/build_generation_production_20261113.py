"""Freeze an unchanged-generation-algorithm source-pin repair for production replay."""
from pathlib import Path
import ast
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT/'scripts/build_generation_variant_20261112_r3.py'
SOURCE = ORIGINAL.read_text(encoding='utf-8')
SOURCE = SOURCE.replace("OUT = ROOT/'submission/optimization_20261112/generation_expand/revision3'",
                        "OUT = ROOT/'submission/optimization_20261113/generation_production'")
SOURCE = SOURCE.replace("MODULE = ROOT/'scripts/generation_runtime_patch_20261112_r3.py'",
                        "MODULE = ROOT/'scripts/generation_runtime_patch_20261113.py'")
SOURCE = SOURCE.replace("BRANCH = 'generation_expand_r3'", "BRANCH = 'generation_production'")
SOURCE = SOURCE.replace("target='stormseye/casmi26-generation-expand-r3-1112'",
                        "target='stormseye/casmi26-generation-production-1113'")
SOURCE = SOURCE.replace("title='CASMI26 generation expand r3 1112'", "title='CASMI26 generation production 1113'")
SOURCE = SOURCE.replace("CASMI26 20261112 generation r3 CODE path repair parents12 products300 audited V1",
                        "CASMI26 20261113 generation production source pin repaired parents12 products300 V1")
SOURCE = SOURCE.replace("scripts/generation_runtime_patch_20261112_r3.py", "scripts/generation_runtime_patch_20261113.py")
SOURCE = SOURCE.replace("Audit path resolution only; generation algorithm and runner unchanged from revision2",
                        "Bind exact engine source after original FROZEN determinism patch; generation algorithm and runner unchanged")
ast.parse(SOURCE)

if __name__ == '__main__':
    exec(compile(SOURCE, str(ORIGINAL), 'exec'), dict(__name__='__main__', __file__=str(ORIGINAL)))
