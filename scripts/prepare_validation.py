"""Prepare source/identity-isolated labeled diagnostics without models or GPU work."""
from pathlib import Path
import argparse
import os
import sys

WORKSPACE = Path(__file__).resolve().parent.parent
for name in ['OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
    os.environ[name] = '4'
os.environ.setdefault('PYTHONPYCACHEPREFIX', str(WORKSPACE / '.cache' / 'pycache-validation'))
sys.path.insert(0, str(WORKSPACE))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train', type=Path, default=WORKSPACE / 'enveda-CASMI26-molecule-id-mass-spectra' / 'train.parquet')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--np-count', type=int, default=24)
    parser.add_argument('--cross-count', type=int, default=24)
    parser.add_argument('--cross-dev', type=int, default=200)
    parser.add_argument('--cross-final', type=int, default=250)
    parser.add_argument('--seed', type=int, default=20261104)
    parser.add_argument('--max-spectra', type=int, default=12)
    parser.add_argument('--batch-size', type=int, default=4096)
    parser.add_argument('--frozen-splits', type=Path, help='Reuse an existing hashed split without selecting a new final set')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(WORKSPACE.resolve()):
        raise ValueError('All generated files must stay in the D-drive workspace')
    from validation.datasets import prepare_validation
    prepare_validation(args.train, output, np_count=args.np_count, cross_count=args.cross_count,
                       cross_dev=args.cross_dev, cross_final=args.cross_final, seed=args.seed,
                       max_spectra=args.max_spectra, batch_size=args.batch_size, frozen_splits=args.frozen_splits)


if __name__ == '__main__':
    main()
