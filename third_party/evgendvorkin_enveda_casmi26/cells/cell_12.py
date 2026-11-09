# v42 determinism policy, adapted from its restored tree to E006's original mounts.
# E006 cell6 has already verified the original v4b manifest and all its hashes.
def _v43_patch_engine(source_root, work_root):
    import hashlib
    from pathlib import Path
    source_root = Path(source_root).resolve(strict=True)
    work_root = Path(work_root)
    original = source_root / 'casmi' / 'engine.py'
    raw = original.read_bytes()
    old = 'ad = max(set(adducts), key=adducts.count)'
    new = 'ad = max(adducts, key=adducts.count)'
    text = raw.decode('utf-8')
    assert text.count(old) == 1, 'Expected exactly one source main-engine adduct tie'
    patched = text.replace(old, new, 1).encode('utf-8')
    assert source_root != work_root.resolve() and source_root not in work_root.resolve().parents
    work_root.mkdir(parents=True, exist_ok=True)
    # Preserve the original relative source tree. Only engine.py is copied/changed.
    for source in sorted(source_root.rglob('*')):
        if '__pycache__' in source.parts or source.suffix == '.pyc':
            continue
        dest = work_root / source.relative_to(source_root)
        if source.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        elif source == original:
            assert not dest.is_symlink(), 'Patched engine must be a work-tree file'
            if dest.exists():
                assert dest.read_bytes() == patched, 'Existing work-tree patch differs'
            else:
                dest.write_bytes(patched)
        else:
            if dest.is_symlink():
                assert dest.resolve(strict=True) == source.resolve(strict=True)
            else:
                assert not dest.exists(), 'Existing work-tree source differs'
                dest.symlink_to(source)
    assert original.read_bytes() == raw, 'Mounted source changed'
    assert (work_root / 'casmi/engine.py').read_bytes() == patched
    return dict(applied=True, original_source_root=str(source_root), work_source_root=str(work_root),
        original_sha256=hashlib.sha256(raw).hexdigest(), patched_sha256=hashlib.sha256(patched).hexdigest(),
        original_line=old, patched_line=new, subprocess_pythonhashseed='0',
        torch_seed=0, cuda_seed=0, cudnn_deterministic=True, cudnn_benchmark=False)

V43_DETERMINISM = _v43_patch_engine(V4CODE, '/kaggle/working/v43_v4code')
V4CODE = V43_DETERMINISM['work_source_root']
os.environ['PYTHONHASHSEED'] = '0'
