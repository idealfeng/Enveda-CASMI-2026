"""Local CASMI MRR helpers, checked against the archived official V14 metric.

This module never installs dependencies. Rank keeps every nonempty submitted
guess, including malformed SMILES and repeated metric identities. Empty fields
between semicolons are removed, as in official V14, before rank/length checks.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Iterable

EXPECTED_RDKIT_VERSION = "2026.03.3"
OFFICIAL_METRIC_URL = "https://www.kaggle.com/code/metric/casmi-mean-reciprocal-rank"
OFFICIAL_METRIC_VERSION = 14
OFFICIAL_SOURCE_SHA256 = "bf8535f01bf73268a52819b38e7f6b205e37ec127c268e48081b780a10b609dd"


def assert_official_rdkit() -> str:
    import rdkit
    if rdkit.__version__ != EXPECTED_RDKIT_VERSION:
        raise RuntimeError(f"CASMI validation requires RDKit {EXPECTED_RDKIT_VERSION}; got {rdkit.__version__}")
    return rdkit.__version__


@lru_cache(maxsize=1)
def _runtime():
    assert_official_rdkit()
    from rdkit import Chem, rdBase
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem.MolStandardize import rdMolStandardize
    return Chem, rdBase, rdMolDescriptors, rdMolStandardize.TautomerEnumerator()


@lru_cache(maxsize=100_000)
def _identity(smiles: str) -> str | None:
    Chem, rdBase, _, canonicalizer = _runtime()
    with rdBase.BlockLogs():
        try:
            molecule = Chem.MolFromSmiles(smiles)
            if molecule is None:
                return None
            # InChIKey truncation alone does not remove stereo/tautomer coupling.
            Chem.RemoveStereochemistry(molecule)
            key = Chem.MolToInchiKey(canonicalizer.Canonicalize(molecule))
            return key[:14] if key else None
        except (ValueError, RuntimeError, TypeError):
            return None


def identity(smiles: str) -> str | None:
    """Tautomer-canonical, stereo-free InChIKey14; malformed input is a nonmatch."""
    assert_official_rdkit()
    return _identity(smiles) if isinstance(smiles, str) else None


@lru_cache(maxsize=100_000)
def heavy_atom_composition(smiles: str) -> tuple[tuple[str, int], ...] | None:
    """Official-style safe prefilter; full molecular formula is not a safe gate."""
    assert_official_rdkit()
    Chem, rdBase, _, _ = _runtime()
    with rdBase.BlockLogs():
        try:
            molecule = Chem.MolFromSmiles(smiles) if isinstance(smiles, str) else None
            if molecule is None:
                return None
            counts: dict[str, int] = {}
            for atom in molecule.GetAtoms():
                symbol = atom.GetSymbol()
                if symbol != "H":
                    counts[symbol] = counts.get(symbol, 0) + 1
            return tuple(sorted(counts.items()))
        except (ValueError, RuntimeError, TypeError):
            return None


@lru_cache(maxsize=100_000)
def molecular_formula(smiles: str) -> str | None:
    """RDKit formula for diagnostics only; never used to reject a metric match."""
    assert_official_rdkit()
    Chem, rdBase, descriptors, _ = _runtime()
    with rdBase.BlockLogs():
        try:
            molecule = Chem.MolFromSmiles(smiles) if isinstance(smiles, str) else None
            return descriptors.CalcMolFormula(molecule) if molecule is not None else None
        except (ValueError, RuntimeError, TypeError):
            return None


def parse_guesses(raw: str, max_rank: int | None = 25) -> list[str]:
    """Strip whitespace/drop empty semicolon fields; retain invalids/duplicates."""
    if max_rank is not None and (not isinstance(max_rank, int) or isinstance(max_rank, bool) or max_rank < 1):
        raise ValueError("max_rank must be a positive integer or None")
    if not isinstance(raw, str):
        raise ValueError("Prediction guesses must be a non-null string")
    guesses = [part.strip() for part in raw.split(";") if part.strip()]
    if not guesses:
        raise ValueError("Each molecule must have at least one nonempty guess")
    if max_rank is not None and len(guesses) > max_rank:
        raise ValueError(f"At most {max_rank} nonempty guesses are allowed; got {len(guesses)}")
    return guesses


def first_correct_rank(truth_identity: str, guesses: str | Iterable[str], max_rank: int = 25) -> int | None:
    if not isinstance(truth_identity, str) or len(truth_identity) != 14 or not truth_identity.isalpha() or not truth_identity.isupper():
        raise ValueError("truth_identity must be a valid InChIKey14")
    values = parse_guesses(guesses if isinstance(guesses, str) else ";".join(guesses), max_rank=max_rank)
    for rank, value in enumerate(values, 1):
        if identity(value) == truth_identity:
            return rank
    return None


def reciprocal_rank(truth_identity: str, guesses: str | Iterable[str], max_rank: int = 25) -> float:
    rank = first_correct_rank(truth_identity, guesses, max_rank)
    return 1.0 / rank if rank is not None else 0.0


def candidate_identity_set(guesses: str | Iterable[str], max_rank: int = 25) -> frozenset[str]:
    values = parse_guesses(guesses if isinstance(guesses, str) else ";".join(guesses), max_rank=max_rank)
    return frozenset(key for value in values if (key := identity(value)))
