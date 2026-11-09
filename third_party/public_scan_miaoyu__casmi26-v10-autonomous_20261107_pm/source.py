"""CASMI 2026: V15 Autonomous Pipeline Grand Fusion Submission.

Major Upgrades in V15:
  1. Multi-CE Targeted Class 1 Matching (Zero-OOM, all 10/20/40/60 eV retained).
  2. Native C++ Spectral Entropy (Shannon Entropy + Jensen-Shannon divergence).
  3. HORIZON First-Principles C++17 Formula Explanation & Noise-Clearing.
  4. 1056d Golden Sweet Spot PMDBarcode (306 PMD bits + 750 core bins [50, 800] Da) + PMD_FPNet_1056d (Val Cos 0.5685).
  5. Multi-CE Exclusive Diagnostic Fragment Reranker (w_excl=3.0).
  6. Test-Time Congener MS2 Modified Cosine Network & Murcko Scaffold Consensus (w_cos=0.50).
  7. High-Resolution timsTOF -1.7 ppm Continuous Gaussian Mass Prior + Molecular Rigidity (+0.10*rings -0.08*rot).
  8. Dedicated LOTUS Organism-Verified Secondary Metabolite Prior (+0.50) & Safe Tail Backfill.
"""
import sys
import os
import time
import glob
import re
import gc
import subprocess
from pathlib import Path
from collections import defaultdict

print("========================================================================", flush=True)
print("=== CASMI 2026: V15 Autonomous Pipeline Grand Fusion (Local MRR@25: 0.5019) ===", flush=True)
print("========================================================================", flush=True)
t_start = time.time()

# ---------------------------------------------------------
# 1. Offline RDKit Installation (if needed)
# ---------------------------------------------------------
try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, rdMolDescriptors, Descriptors
    from rdkit.Chem.Scaffolds import MurckoScaffold
    from rdkit import RDLogger
    RDLogger.DisableLog('rdApp.*')
    print("RDKit already available in environment.", flush=True)
except ImportError:
    print("Attempting offline wheel install for RDKit...", flush=True)
    wheel_paths = glob.glob('/kaggle/input/**/rdkit*.whl', recursive=True)
    if wheel_paths:
        wheel_file = wheel_paths[0]
        print(f"Installing {wheel_file}...", flush=True)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-index",
                               f"--find-links={os.path.dirname(wheel_file)}", wheel_file])
        from rdkit import Chem
        from rdkit.Chem import AllChem, rdMolDescriptors, Descriptors
        from rdkit.Chem.Scaffolds import MurckoScaffold
        from rdkit import RDLogger
        RDLogger.DisableLog('rdApp.*')
        print("RDKit installed successfully!", flush=True)
    else:
        raise RuntimeError("RDKit wheel not found!")

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import torch
import torch.nn as nn

# ---------------------------------------------------------
# 2. Locate Datasets & Compile HORIZON C++ Engine
# ---------------------------------------------------------
def locate_file(pattern, base_dirs=None):
    if base_dirs is None:
        base_dirs = ['/kaggle/input', 'scratch/casmi26', '/Users/yufree/kaggle_data', '.', '/kaggle/src', '/kaggle/working', os.path.dirname(os.path.abspath(__file__))]
    for b in base_dirs:
        if os.path.exists(b):
            matches = glob.glob(f"{b}/**/{pattern}", recursive=True)
            if matches:
                return matches[0]
    raise FileNotFoundError(f"Could not locate {pattern}")

TEST_PATH = locate_file('test.parquet')
TRAIN_PATH = locate_file('train.parquet')
MODEL_PATH = locate_file('pmd_fpnet_1056d_best.pt')
COCONUT_PATH = locate_file('coconut_clean.parquet')
HORIZON_CPP = locate_file('horizon_casmi.cpp')
HORIZON_DIR = os.path.dirname(HORIZON_CPP)

LOTUS_PATH = None
try:
    LOTUS_PATH = locate_file('candidates_lotus.parquet')
except Exception:
    pass

print(f"Test Parquet:        {TEST_PATH}", flush=True)
print(f"Train Parquet:       {TRAIN_PATH}", flush=True)
print(f"Model Checkpoint:    {MODEL_PATH}", flush=True)
print(f"COCONUT Parquet:     {COCONUT_PATH}", flush=True)
print(f"LOTUS Candidates:    {LOTUS_PATH}", flush=True)
print(f"HORIZON Source:      {HORIZON_CPP}", flush=True)

# Compile HORIZON engine locally or in /kaggle/working
is_darwin = (sys.platform == 'darwin')
lib_name = 'libhorizon_casmi.dylib' if is_darwin else 'libhorizon_casmi.so'
lib_target = os.path.join(os.getcwd(), lib_name)

if not os.path.exists(lib_target):
    compiler = 'clang++' if is_darwin else 'g++'
    cmd = [compiler, "-O3", "-std=c++17", "-shared", "-fPIC",
           HORIZON_CPP, f"-I{HORIZON_DIR}", "-o", lib_target]
    print(f"Compiling HORIZON with native Spectral Entropy: {' '.join(cmd)}...", flush=True)
    subprocess.check_call(cmd)

sys.path.insert(0, HORIZON_DIR)
from horizon_casmi import Horizon
hz = Horizon(lib_target)
print("HORIZON C++17 engine loaded (Native Spectral Entropy + Subformula Explain enabled).", flush=True)

# ---------------------------------------------------------
# 3. Adduct Physics & Neutral Mass Map
# ---------------------------------------------------------
ADDUCT_MAP = {
    '[M+H]+': (1.007276, 1, 1),
    '[M-H]-': (-1.007276, -1, 1),
    '[M+Na]+': (22.989221, 1, 1),
    '[M+K]+': (38.963158, 1, 1),
    '[M+NH4]+': (18.033826, 1, 1),
    '[M+Cl]-': (34.969401, -1, 1),
    '[M+FA-H]-': (44.998203, -1, 1),
    '[M+CH2O2-H]-': (44.998203, -1, 1),
    '[M+C2H4O2-H]-': (59.013853, -1, 1),
    '[M-H2O+H]+': (-17.003289, 1, 1),
    '[M-2H2O+H]+': (-35.013854, 1, 1),
    '[M-H4O2+H]+': (-35.013854, 1, 1),
    '[M-H2O-H]-': (-19.017841, -1, 1),
    '[2M+H]+': (1.007276, 1, 2),
    '[2M+Na]+': (22.989221, 1, 2),
    '[2M-H]-': (-1.007276, -1, 2),
    '[M-H2+H]+': (-0.992724, 1, 1),
    '[M-2H2+H]+': (-3.008276, 1, 1),
    '[M+H2+H]+': (3.022828, 1, 1),
    '[M+2H2+H]+': (5.038380, 1, 1),
    '[M+O+H]+': (17.002191, 1, 1),
    '[M-O+H]+': (-14.987638, 1, 1),
    '[M-CO+H]+': (-26.987638, 1, 1),
    '[M-CO2+H]+': (-42.982553, 1, 1),
    '[M-CH2O+H]+': (-28.995403, 1, 1),
    '[M-CH3OH+H]+': (-31.018389, 1, 1),
    '[M-NH3+H]+': (-16.018724, 1, 1),
}

def calc_neutral_mass(prec_mz, adduct):
    if adduct in ADDUCT_MAP:
        delta, _, mult = ADDUCT_MAP[adduct]
        return (prec_mz - delta) / mult
    return prec_mz - 1.007276

NORM_ADDUCT = {
    '[M+H]+': '[M+H]+',
    '[M+Na]+': '[M+Na]+',
    '[M+K]+': '[M+K]+',
    '[M+NH4]+': '[M+NH4]+',
    '[M-H]-': '[M-H]-',
    '[M+Cl]-': '[M+Cl]-',
    '[M+FA-H]-': '[M-H]-',
    '[M+CH2O2-H]-': '[M-H]-',
    '[M+C2H4O2-H]-': '[M-H]-',
    '[2M+H]+': '[M+H]+',
    '[2M+Na]+': '[M+Na]+',
    '[2M-H]-': '[M-H]-',
    '[M-H2O+H]+': '[M+H]+',
    '[M-2H2O+H]+': '[M+H]+',
    '[M-H4O2+H]+': '[M+H]+',
    '[M-H2O-H]-': '[M-H]-',
}

atom_masses = {
    'H': 1.007825032, 'C': 12.0000000, 'N': 14.003074004, 'O': 15.99491462,
    'F': 18.9984032, 'Na': 22.98976928, 'P': 30.97376163, 'S': 31.97207100,
    'Cl': 34.96885268, 'K': 38.96370668, 'Br': 78.9183371, 'I': 126.904473
}
def parse_formula_mw(f):
    matches = re.findall(r'([A-Z][a-z]*)(\d*)', f)
    return sum(atom_masses.get(elem, 0.0) * (int(count) if count else 1) for elem, count in matches if elem)

# ---------------------------------------------------------
# 4. Super PMDBarcode Setup (Embedded 306 bits + 1000 dims)
# ---------------------------------------------------------
"""Super PMDBarcode Codebook (306 bits) - SpectraVerse + CASMI Natural Products."""

SUPER_PREC_BINS = [(101, 'H', 1.00782, 6.67, 'CASMI_NP'), (202, 'H2', 2.01565, 16.35, 'CASMI_NP'), (1402, 'CH2', 14.01565, 11.92, 'SpectraVerse'), (1501, 'HN', 15.010899, 5.12, 'SpectraVerse'), (1502, 'CH3', 15.023475, 48.34, 'SpectraVerse'), (1602, 'H2N', 16.018724, 12.11, 'SpectraVerse'), (1603, 'CH4', 16.0313, 28.34, 'SpectraVerse'), (1700, 'HO', 17.00274, 13.56, 'SpectraVerse'), (1703, 'H3N', 17.026549, 6.96, 'SpectraVerse'), (1801, 'H2O', 18.010565, 51.81, 'SpectraVerse'), (2701, 'CHN', 27.010899, 19.76, 'SpectraVerse'), (2799, 'CO', 27.994915, 31.65, 'SpectraVerse'), (2801, 'N2', 28.00615, 22.38, 'CASMI_NP'), (2803, 'C2H4', 28.0313, 13.92, 'SpectraVerse'), (2900, 'CHO', 29.00274, 12.55, 'SpectraVerse'), (2903, 'CH3N', 29.026549, 7.44, 'SpectraVerse'), (2904, 'C2H5', 29.039125, 9.41, 'SpectraVerse'), (3001, 'CH2O', 30.010565, 14.56, 'SpectraVerse'), (3101, 'HNO', 31.005814, 6.17, 'SpectraVerse'), (3102, 'CH3O', 31.01839, 9.03, 'SpectraVerse'), (3104, 'CH5N', 31.042199, 18.13, 'SpectraVerse'), (3105, 'C2H7', 31.054775, 5.95, 'SpectraVerse'), (3203, 'CH4O', 32.02622, 89.0, 'CASMI_NP'), (3302, 'H3NO', 33.021464, 6.01, 'SpectraVerse'), (3303, 'CH5O', 33.03404, 22.94, 'SpectraVerse'), (3305, 'H5N2', 33.045273, 6.74, 'SpectraVerse'), (3399, 'H2S', 33.98772, 6.0, 'CASMI_NP'), (3403, 'H4NO', 34.029289, 10.78, 'SpectraVerse'), (3501, 'H3O2', 35.013304, 11.33, 'SpectraVerse'), (3802, 'C3H2', 38.01565, 25.0, 'CASMI_NP'), (3901, 'C2HN', 39.0109, 14.0, 'CASMI_NP'), (3999, 'C2O', 39.99491, 26.5, 'CASMI_NP'), (4001, 'CN2', 40.006148, 8.81, 'SpectraVerse'), (4103, 'C2H3N', 41.026549, 6.01, 'SpectraVerse'), (4104, 'C3H5', 41.039125, 6.78, 'SpectraVerse'), (4200, 'CNO', 41.997989, 6.82, 'SpectraVerse'), (4202, 'CH2N2', 42.021798, 7.2, 'SpectraVerse'), (4205, 'C3H6', 42.04695, 17.56, 'CASMI_NP'), (4301, 'CHNO', 43.005814, 17.77, 'SpectraVerse'), (4304, 'C2H5N', 43.042199, 10.24, 'SpectraVerse'), (4305, 'C3H7', 43.054775, 5.53, 'SpectraVerse'), (4398, 'CHS', 43.981588, 17.77, 'SpectraVerse'), (4399, 'CO2', 43.989829, 25.58, 'SpectraVerse'), (4402, 'H2N3', 44.024872, 15.62, 'SpectraVerse'), (4499, 'CH2S', 44.989413, 7.87, 'SpectraVerse'), (4500, 'CHO2', 44.997654, 10.32, 'SpectraVerse'), (4502, 'CH3NO', 45.021464, 18.07, 'SpectraVerse'), (4505, 'CH5N2', 45.045273, 14.43, 'SpectraVerse'), (4506, 'C2H7N', 45.05785, 77.75, 'CASMI_NP'), (4600, 'CH3S', 45.997238, 57.44, 'SpectraVerse'), (4601, 'CH2O2', 46.00548, 64.85, 'CASMI_NP'), (4700, 'HNO2', 47.00073, 5.64, 'CASMI_NP'), (4704, 'CH5NO', 47.037114, 6.46, 'SpectraVerse'), (4800, 'CH4S', 48.00337, 11.5, 'CASMI_NP'), (4802, 'CH4O2', 48.021129, 17.48, 'SpectraVerse'), (5304, 'C4H5', 53.039125, 18.03, 'SpectraVerse'), (5402, 'C2H2N2', 54.021798, 7.21, 'SpectraVerse'), (5403, 'C3H4N', 54.034374, 26.33, 'SpectraVerse'), (5405, 'C4H6', 54.04695, 23.11, 'CASMI_NP'), (5501, 'C2HNO', 55.005814, 6.95, 'SpectraVerse'), (5504, 'C3H5N', 55.042199, 6.7, 'SpectraVerse'), (5505, 'C4H7', 55.054775, 8.8, 'SpectraVerse'), (5598, 'C2HS', 55.981588, 9.35, 'SpectraVerse'), (5599, 'C2O2', 55.989829, 8.45, 'SpectraVerse'), (5600, 'CN2O', 56.00106, 23.33, 'CASMI_NP'), (5602, 'CH2N3', 56.024872, 9.18, 'SpectraVerse'), (5606, 'C4H8', 56.0626, 24.83, 'SpectraVerse'), (5705, 'C2H5N2', 57.045273, 14.03, 'SpectraVerse'), (5706, 'C3H7N', 57.05785, 71.6, 'CASMI_NP'), (5707, 'C4H9', 57.070425, 5.55, 'SpectraVerse'), (5802, 'CH2N2O', 58.016713, 5.07, 'SpectraVerse'), (5807, 'C3H8N', 58.065674, 6.23, 'SpectraVerse'), (5907, 'C3H9N', 59.073499, 10.9, 'SpectraVerse'), (6003, 'CH4N2O', 60.032363, 7.22, 'SpectraVerse'), (6102, 'CH3NO2', 61.01638, 68.0, 'CASMI_NP'), (6203, 'C2H7S', 62.028538, 15.94, 'SpectraVerse'), (6303, 'CH5NO2', 63.03203, 11.67, 'CASMI_NP'), (6307, 'H7N4', 63.06707, 13.57, 'CASMI_NP'), (6400, 'CH4OS', 63.99829, 6.0, 'CASMI_NP'), (6405, 'H6N3O', 64.051087, 8.61, 'SpectraVerse'), (6704, 'C4H5N', 67.042199, 8.36, 'SpectraVerse'), (6803, 'C4H4O', 68.026215, 7.21, 'SpectraVerse'), (6806, 'C5H8', 68.0626, 10.55, 'SpectraVerse'), (6905, 'C3H5N2', 69.045273, 10.24, 'SpectraVerse'), (6906, 'C4H7N', 69.05785, 19.2, 'CASMI_NP'), (6907, 'C5H9', 69.070425, 6.92, 'SpectraVerse'), (7005, 'C3H6N2', 70.053098, 6.75, 'SpectraVerse'), (7007, 'C4H8N', 70.065674, 10.77, 'SpectraVerse'), (7107, 'C4H9N', 71.073499, 10.68, 'SpectraVerse'), (7207, 'C3H8N2', 72.06875, 5.25, 'CASMI_NP'), (7306, 'C2H7N3', 73.063997, 7.44, 'SpectraVerse'), (7308, 'C3H9N2', 73.076573, 10.63, 'SpectraVerse'), (7309, 'C4H11N', 73.08915, 72.8, 'CASMI_NP'), (7403, 'C3H7S', 74.028538, 17.19, 'SpectraVerse'), (7506, 'C2H7N2O', 75.055838, 10.82, 'SpectraVerse'), (7708, 'CH9N4', 77.08272, 14.86, 'CASMI_NP'), (7806, 'C2H8NO2', 78.055503, 6.54, 'SpectraVerse'), (7807, 'CH8N3O', 78.06674, 8.73, 'CASMI_NP'), (7906, 'H7N4O', 79.06199, 6.15, 'CASMI_NP'), (7995, 'HOPS', 79.948575, 5.11, 'SpectraVerse'), (8004, 'C4H4N2', 80.037448, 8.81, 'SpectraVerse'), (8205, 'C4H6N2', 82.0531, 7.35, 'CASMI_NP'), (8207, 'C5H8N', 82.065674, 7.95, 'SpectraVerse'), (8208, 'C6H10', 82.07825, 7.51, 'CASMI_NP'), (8303, 'H7N2OP', 83.027909, 8.74, 'SpectraVerse'), (8307, 'C5H9N', 83.073499, 10.05, 'SpectraVerse'), (8400, 'C4H4S', 84.00337, 5.36, 'CASMI_NP'), (8403, 'C3H4N2O', 84.032363, 5.55, 'SpectraVerse'), (8409, 'C6H12', 84.0939, 7.1, 'SpectraVerse'), (8506, 'C3H7N3', 85.063997, 7.07, 'SpectraVerse'), (8508, 'C4H9N2', 85.076573, 10.72, 'SpectraVerse'), (8509, 'C5H11N', 85.08915, 21.08, 'CASMI_NP'), (8608, 'C4H10N2', 86.0844, 9.9, 'CASMI_NP'), (8706, 'C3H7N2O', 87.055838, 12.49, 'SpectraVerse'), (8710, 'C5H13N', 87.104799, 5.51, 'SpectraVerse'), (8808, 'C4H10NO', 88.076239, 8.11, 'SpectraVerse'), (8810, 'C4H12N2', 88.10005, 13.67, 'CASMI_NP'), (9109, 'C3H11N2O', 91.087138, 6.04, 'SpectraVerse'), (9110, 'C2H11N4', 91.09837, 19.0, 'CASMI_NP'), (9406, 'C2H10N2P', 94.05647, 8.74, 'SpectraVerse'), (9507, 'C6H9N', 95.073499, 5.8, 'SpectraVerse'), (9509, 'C7H11', 95.086075, 6.78, 'SpectraVerse'), (9607, 'C5H8N2', 96.06875, 5.74, 'CASMI_NP'), (9609, 'C7H12', 96.0939, 5.71, 'CASMI_NP'), (9707, 'C6H9O', 97.06534, 5.22, 'SpectraVerse'), (9708, 'C5H9N2', 97.076573, 7.51, 'SpectraVerse'), (9709, 'C6H11N', 97.08915, 17.27, 'CASMI_NP'), (9803, 'C5H7S', 98.028538, 7.97, 'SpectraVerse'), (9808, 'C5H10N2', 98.0844, 7.08, 'CASMI_NP'), (9906, 'C4H7N2O', 99.055838, 11.93, 'SpectraVerse'), (9910, 'C6H13N', 99.104799, 8.8, 'SpectraVerse'), (10008, 'C5H10NO', 100.076239, 7.95, 'SpectraVerse'), (10010, 'C5H12N2', 100.10005, 27.8, 'CASMI_NP'), (10112, 'C6H15N', 101.12045, 13.33, 'CASMI_NP'), (10511, 'C3H13N4', 105.114021, 6.18, 'SpectraVerse'), (11110, 'C7H13N', 111.104799, 5.5, 'SpectraVerse'), (11208, 'C6H10NO', 112.076239, 6.32, 'SpectraVerse'), (11210, 'C6H12N2', 112.10005, 6.97, 'CASMI_NP'), (11412, 'C6H14N2', 114.1157, 22.87, 'CASMI_NP'), (11613, 'C6H16N2', 116.13135, 15.6, 'CASMI_NP'), (11711, 'C4H13N4', 117.114021, 7.61, 'SpectraVerse'), (12512, 'C8H15N', 125.12045, 6.47, 'CASMI_NP'), (12612, 'C7H14N2', 126.1157, 19.86, 'CASMI_NP'), (12813, 'C7H16N2', 128.13135, 132.5, 'CASMI_NP'), (12911, 'C5H13N4', 129.114021, 8.49, 'SpectraVerse'), (13914, 'C9H17N', 139.1361, 5.91, 'CASMI_NP'), (14013, 'C8H16N2', 140.13135, 18.0, 'CASMI_NP'), (14111, 'C6H13N4', 141.114021, 7.13, 'SpectraVerse'), (14215, 'C8H18N2', 142.147, 38.0, 'CASMI_NP'), (15114, 'C10H17N', 151.1361, 10.2, 'CASMI_NP'), (15415, 'C9H18N2', 154.147, 14.11, 'CASMI_NP'), (15616, 'C9H20N2', 156.16265, 34.25, 'CASMI_NP'), (16615, 'C10H18N2', 166.147, 5.85, 'CASMI_NP'), (16816, 'C10H20N2', 168.16265, 22.0, 'CASMI_NP'), (17018, 'C10H22N2', 170.1783, 18.5, 'CASMI_NP'), (18016, 'C11H20N2', 180.16265, 5.64, 'CASMI_NP'), (19619, 'C12H24N2', 196.19395, 30.67, 'CASMI_NP'), (24524, 'C14H31NO2', 245.235478, 5.56, 'SpectraVerse')]

SUPER_FRAG_BINS = [(202, 'H2', 2.01565, 10.65, 'CASMI_NP'), (302, 'H3', 3.023475, 8.94, 'SpectraVerse'), (1200, 'C', 12.0, 15.98, 'CASMI_NP'), (1301, 'CH', 13.007825, 7.32, 'SpectraVerse'), (1402, 'CH2', 14.01565, 12.52, 'CASMI_NP'), (1501, 'HN', 15.010899, 11.61, 'SpectraVerse'), (1502, 'CH3', 15.023475, 15.13, 'SpectraVerse'), (1599, 'O', 15.99492, 11.11, 'CASMI_NP'), (1602, 'H2N', 16.018724, 6.67, 'SpectraVerse'), (1603, 'CH4', 16.0313, 12.71, 'SpectraVerse'), (1700, 'HO', 17.00274, 12.64, 'SpectraVerse'), (1703, 'H3N', 17.026549, 7.15, 'SpectraVerse'), (1801, 'H2O', 18.010565, 20.04, 'SpectraVerse'), (2400, 'C2', 24.0, 14.15, 'SpectraVerse'), (2501, 'C2H', 25.007825, 7.17, 'SpectraVerse'), (2600, 'CN', 26.003074, 7.27, 'SpectraVerse'), (2602, 'C2H2', 26.01565, 12.19, 'CASMI_NP'), (2701, 'CHN', 27.010899, 14.29, 'SpectraVerse'), (2702, 'C2H3', 27.023475, 11.01, 'SpectraVerse'), (2799, 'CO', 27.994915, 18.74, 'SpectraVerse'), (2801, 'N2', 28.006148, 6.54, 'SpectraVerse'), (2802, 'CH2N', 28.018724, 5.82, 'SpectraVerse'), (2803, 'C2H4', 28.0313, 13.96, 'SpectraVerse'), (2900, 'CHO', 29.00274, 11.47, 'SpectraVerse'), (2901, 'HN2', 29.013973, 5.24, 'SpectraVerse'), (2903, 'CH3N', 29.026549, 8.77, 'SpectraVerse'), (3000, 'NO', 29.997989, 6.47, 'SpectraVerse'), (3001, 'CH2O', 30.010565, 13.92, 'SpectraVerse'), (3002, 'H2N2', 30.021798, 5.59, 'SpectraVerse'), (3005, 'C2H6', 30.04695, 5.05, 'CASMI_NP'), (3101, 'HNO', 31.005814, 9.96, 'SpectraVerse'), (3102, 'CH3O', 31.01839, 5.07, 'SpectraVerse'), (3104, 'CH5N', 31.042199, 6.89, 'SpectraVerse'), (3198, 'HS', 31.981588, 8.37, 'SpectraVerse'), (3199, 'O2', 31.989829, 5.16, 'SpectraVerse'), (3203, 'CH4O', 32.02622, 8.47, 'CASMI_NP'), (3204, 'H4N2', 32.037448, 5.05, 'SpectraVerse'), (3298, 'HP', 32.979897, 6.49, 'SpectraVerse'), (3299, 'H2S', 32.989413, 6.6, 'SpectraVerse'), (3302, 'H3NO', 33.021464, 6.88, 'SpectraVerse'), (3303, 'CH5O', 33.03404, 7.25, 'SpectraVerse'), (3400, 'H3S', 33.997238, 8.16, 'SpectraVerse'), (3500, 'H3P', 34.995547, 7.61, 'SpectraVerse'), (3501, 'H3O2', 35.013304, 6.76, 'SpectraVerse'), (3600, 'C3', 36.0, 7.34, 'CASMI_NP'), (3701, 'C3H', 37.007825, 6.82, 'SpectraVerse'), (3800, 'C2N', 38.003074, 5.82, 'SpectraVerse'), (3802, 'C3H2', 38.01565, 11.21, 'CASMI_NP'), (3901, 'C2HN', 39.010899, 10.04, 'SpectraVerse'), (3902, 'C3H3', 39.023475, 9.94, 'SpectraVerse'), (3999, 'C2O', 39.994915, 11.76, 'SpectraVerse'), (4001, 'CN2', 40.006148, 6.37, 'SpectraVerse'), (4002, 'C2H2N', 40.018724, 5.55, 'SpectraVerse'), (4003, 'C3H4', 40.0313, 13.95, 'SpectraVerse'), (4100, 'C2HO', 41.00274, 10.25, 'SpectraVerse'), (4101, 'CHN2', 41.013973, 5.5, 'SpectraVerse'), (4103, 'C2H3N', 41.026549, 8.37, 'SpectraVerse'), (4200, 'CNO', 41.997989, 5.96, 'SpectraVerse'), (4202, 'CH2N2', 42.021798, 5.87, 'SpectraVerse'), (4203, 'C2H4N', 42.034374, 5.16, 'SpectraVerse'), (4205, 'C3H6', 42.04695, 7.37, 'CASMI_NP'), (4301, 'CHNO', 43.005814, 11.57, 'SpectraVerse'), (4304, 'C2H5N', 43.042199, 8.58, 'SpectraVerse'), (4305, 'C3H7', 43.054775, 5.49, 'SpectraVerse'), (4397, 'CS', 43.97207, 5.07, 'CASMI_NP'), (4398, 'CHS', 43.981588, 9.1, 'SpectraVerse'), (4399, 'CO2', 43.989829, 5.6, 'SpectraVerse'), (4400, 'N2O', 44.001063, 5.24, 'SpectraVerse'), (4402, 'H2N3', 44.024872, 12.32, 'SpectraVerse'), (4406, 'C3H8', 44.0626, 5.71, 'SpectraVerse'), (4499, 'CH2S', 44.989413, 8.11, 'SpectraVerse'), (4500, 'CHO2', 44.997654, 5.56, 'SpectraVerse'), (4501, 'HN2O', 45.008888, 5.24, 'SpectraVerse'), (4502, 'CH3NO', 45.021464, 9.65, 'SpectraVerse'), (4505, 'CH5N2', 45.045273, 5.12, 'SpectraVerse'), (4506, 'C2H7N', 45.05785, 7.31, 'CASMI_NP'), (4600, 'CH3S', 45.997238, 14.36, 'SpectraVerse'), (4601, 'CH2O2', 46.00548, 5.45, 'CASMI_NP'), (4602, 'H2N2O', 46.016713, 6.81, 'SpectraVerse'), (4699, 'H2NS', 46.992487, 6.65, 'SpectraVerse'), (4702, 'H3N2O', 47.024538, 5.64, 'SpectraVerse'), (4704, 'CH5NO', 47.037114, 5.02, 'SpectraVerse'), (4799, 'H2NP', 47.990796, 7.92, 'SpectraVerse'), (4802, 'CH4O2', 48.021129, 7.95, 'SpectraVerse'), (4803, 'H4N2O', 48.032363, 7.58, 'SpectraVerse'), (4899, 'HO3', 48.992569, 5.67, 'SpectraVerse'), (4900, 'H3NP', 48.998621, 9.04, 'SpectraVerse'), (4902, 'H3NO2', 49.016378, 6.88, 'SpectraVerse'), (5001, 'H4NP', 50.006446, 13.92, 'SpectraVerse'), (5099, 'H3OP', 50.990461, 5.55, 'SpectraVerse'), (5102, 'C4H3', 51.023475, 9.84, 'SpectraVerse'), (5199, 'C3O', 51.994915, 9.26, 'SpectraVerse'), (5201, 'C2N2', 52.006148, 6.06, 'SpectraVerse'), (5203, 'C4H4', 52.0313, 13.8, 'SpectraVerse'), (5300, 'C3HO', 53.00274, 7.92, 'SpectraVerse'), (5303, 'C3H3N', 53.02655, 7.97, 'CASMI_NP'), (5304, 'C4H5', 53.039125, 5.06, 'SpectraVerse'), (5400, 'C2NO', 53.997989, 5.34, 'SpectraVerse'), (5402, 'C2H2N2', 54.021798, 5.83, 'SpectraVerse'), (5403, 'C3H4N', 54.034374, 6.25, 'SpectraVerse'), (5405, 'C4H6', 54.04695, 9.89, 'CASMI_NP'), (5501, 'C2HNO', 55.005814, 8.05, 'SpectraVerse'), (5504, 'C3H5N', 55.042199, 7.74, 'SpectraVerse'), (5505, 'C4H7', 55.054775, 6.02, 'SpectraVerse'), (5598, 'C2HS', 55.981588, 9.09, 'SpectraVerse'), (5599, 'C2O2', 55.989829, 5.82, 'SpectraVerse'), (5602, 'CH2N3', 56.024872, 10.45, 'SpectraVerse'), (5606, 'C4H8', 56.0626, 8.7, 'SpectraVerse'), (5699, 'C2H2S', 56.989413, 7.72, 'SpectraVerse'), (5701, 'CHN2O', 57.008888, 5.36, 'SpectraVerse'), (5705, 'C2H5N2', 57.045273, 5.54, 'SpectraVerse'), (5802, 'CH2N2O', 58.016713, 6.44, 'SpectraVerse'), (5807, 'C3H8N', 58.065674, 5.23, 'SpectraVerse'), (5907, 'C3H9N', 59.0735, 6.03, 'CASMI_NP'), (6003, 'CH4N2O', 60.032363, 6.74, 'SpectraVerse'), (6203, 'C2H7S', 62.028538, 6.08, 'SpectraVerse'), (6205, 'CH6N2O', 62.048013, 6.23, 'SpectraVerse'), (6503, 'C4H3N', 65.026549, 7.4, 'SpectraVerse'), (6605, 'C5H6', 66.04695, 7.34, 'CASMI_NP'), (6700, 'H3O4', 67.003133, 5.84, 'SpectraVerse'), (6704, 'C4H5N', 67.042199, 7.05, 'SpectraVerse'), (6705, 'C5H7', 67.054775, 5.88, 'SpectraVerse'), (6806, 'C5H8', 68.0626, 8.92, 'SpectraVerse'), (6905, 'C3H5N2', 69.045273, 5.76, 'SpectraVerse'), (6906, 'C4H7N', 69.05785, 6.67, 'CASMI_NP'), (7007, 'C4H8N', 70.065674, 6.9, 'SpectraVerse'), (7107, 'C4H9N', 71.0735, 7.72, 'CASMI_NP'), (7309, 'C4H11N', 73.08915, 7.05, 'CASMI_NP'), (7403, 'C3H7S', 74.028538, 8.19, 'SpectraVerse'), (8006, 'C6H8', 80.0626, 8.55, 'SpectraVerse'), (8105, 'C4H5N2', 81.045273, 5.01, 'SpectraVerse'), (8106, 'C5H7N', 81.05785, 5.86, 'CASMI_NP'), (8207, 'C5H8N', 82.065674, 7.68, 'SpectraVerse'), (8303, 'H7N2OP', 83.027909, 6.17, 'SpectraVerse'), (8307, 'C5H9N', 83.0735, 9.04, 'CASMI_NP'), (8403, 'C3H4N2O', 84.032363, 5.25, 'SpectraVerse'), (8409, 'C6H12', 84.0939, 5.51, 'SpectraVerse'), (8509, 'C5H11N', 85.08915, 7.26, 'CASMI_NP'), (8605, 'C3H6N2O', 86.048013, 5.16, 'SpectraVerse'), (8806, 'C3H8N2O', 88.063663, 5.34, 'SpectraVerse'), (9609, 'C7H12', 96.0939, 5.96, 'SpectraVerse'), (9709, 'C6H11N', 97.08915, 5.83, 'CASMI_NP'), (9803, 'C5H7S', 98.028538, 6.86, 'SpectraVerse'), (10809, 'C8H12', 108.0939, 6.58, 'SpectraVerse'), (11010, 'C7H12N', 110.096974, 5.24, 'SpectraVerse'), (11110, 'C7H13N', 111.1048, 5.46, 'CASMI_NP'), (11208, 'C6H10NO', 112.076239, 5.63, 'SpectraVerse'), (15315, 'C10H19N', 153.15175, 5.12, 'CASMI_NP')]

N_PREC_BITS = 158
N_FRAG_BITS = 148
N_CORE_BITS = 306
N_TOTAL_DIMS = N_CORE_BITS + 1000


print(f"Super PMDBarcode initialized: {N_PREC_BITS} prec bits + {N_FRAG_BITS} frag bits = {N_CORE_BITS} core bits -> {N_TOTAL_DIMS} total dims.", flush=True)

prec_dict = {b[0]: i for i, b in enumerate(SUPER_PREC_BINS)}
frag_dict = {b[0]: i + N_PREC_BITS for i, b in enumerate(SUPER_FRAG_BINS)}
prec_bins_set = set(prec_dict.keys())
frag_bins_set = set(frag_dict.keys())

def compute_1056d_barcode(mzs, ints, precursor_mz, top_k=60):
    vec = np.zeros(N_TOTAL_DIMS, dtype=np.float32)
    if len(mzs) == 0: return np.zeros(1056, dtype=np.float32)
    if len(mzs) > top_k:
        top_idx = np.argsort(ints)[-top_k:]
        mzs, ints = mzs[top_idx], ints[top_idx]
    if precursor_mz > 0:
        losses = precursor_mz - mzs
        losses = losses[losses > 0]
        if len(losses) > 0:
            loss_b = np.round(losses * 100).astype(int)
            for b in set(loss_b) & prec_bins_set:
                vec[prec_dict[b]] = 1.0
    if len(mzs) >= 2:
        diffs = np.abs(mzs[:, None] - mzs[None, :])
        iu, ju = np.triu_indices(len(mzs), k=1)
        frag_b = np.round(diffs[iu, ju] * 100).astype(int)
        for b in set(frag_b) & frag_bins_set:
            vec[frag_dict[b]] = 1.0
    bins = np.clip((mzs / 1000.0 * 1000).astype(int), 0, 999)
    for b, v in zip(bins, ints):
        vec[N_CORE_BITS + b] = max(vec[N_CORE_BITS + b], v)
    return np.concatenate([vec[:306], vec[306+50:306+800]])

# ---------------------------------------------------------
# 5. Load Deep Neural Architecture (PMD_FPNet_1056d)
# ---------------------------------------------------------
device = torch.device('cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu'))
print(f"Neural Inference device: {device}", flush=True)

class ResidualBlock(nn.Module):
    def __init__(self, dim, dropout=0.15):
        super().__init__()
        self.block = nn.Sequential(
            nn.Linear(dim, dim), nn.LayerNorm(dim), nn.GELU(),
            nn.Dropout(dropout), nn.Linear(dim, dim), nn.LayerNorm(dim),
        )
        self.act = nn.GELU()
    def forward(self, x):
        return self.act(x + self.block(x))

class PMD_FPNet_1056d(nn.Module):
    def __init__(self, in_dim=1056, out_dim=2048, hidden_dim=1024):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Linear(in_dim, hidden_dim), nn.LayerNorm(hidden_dim),
            nn.GELU(), nn.Dropout(0.2),
        )
        self.res1 = ResidualBlock(hidden_dim, dropout=0.15)
        self.res2 = ResidualBlock(hidden_dim, dropout=0.15)
        self.head = nn.Linear(hidden_dim, out_dim)
    def forward(self, x):
        return self.head(self.res2(self.res1(self.stem(x))))

model = PMD_FPNet_1056d(in_dim=1056, out_dim=2048, hidden_dim=1024).to(device)
ckpt = torch.load(MODEL_PATH, map_location=device, weights_only=False)
state_dict = ckpt['model_state_dict'] if 'model_state_dict' in ckpt else ckpt
model.load_state_dict(state_dict)
model.eval()
print(f"PMD_FPNet_1056d loaded successfully (Val Cosine: 0.5685)", flush=True)

# ---------------------------------------------------------
# 6. Reactomics In-Silico Derivatization Reactions
# ---------------------------------------------------------
PMD_REACTIONS = [
    # 1. 基础单碳与氧化修饰
    ("methylation_on", 14.01565, "[O,N;H1:1]>>[*:1]C"),
    ("methylation_c", 14.01565, "[cH:1]>>[c:1]C"),
    ("hydroxylation", 15.99491, "[cH:1]>>[c:1]O"),
    ("acetylation", 42.01056, "[O,N;H1:1]>>[*:1]C(=O)C"),
    
    # 2. 双键加氢饱和与脱氢反应 (H2, ±2.01565 Da)
    ("hydrogenation_alkene", 2.01565, "[C:1]=[C:2]>>[C:1][C:2]"),
    ("carbonyl_reduction", 2.01565, "[C:1]=[O:2]>>[C:1][O:2]"),
    ("desaturation", -2.01565, "[C:1][C:2]>>[C:1]=[C:2]"),
    
    # 3. 水合加成与消除脱水反应 (H2O, ±18.01056 Da)
    ("hydration_alkene", 18.01056, "[C:1]=[C:2]>>[C:1](O)[C:2]"),
    ("epoxide_opening", 18.01056, "[C:1]1O[C:2]1>>[C:1](O)[C:2](O)"),
    ("dehydration", -18.01056, "[C:1][C:2][O;H1]>>[C:1]=[C:2]"),
    
    # 4. 天然产物多糖苷化核心通道
    ("glucosylation", 162.05282, "[c:1][O;H1:2]>>[c:1][O:2][C@@H]3O[C@H](CO)[C@@H](O)[C@H](O)[C@H]3O"),
    ("pentosylation", 132.04226, "[c:1][O;H1:2]>>[c:1][O:2][C@@H]3OC[C@@H](O)[C@H](O)[C@H]3O"),
    ("deoxyhexosylation", 146.05791, "[c:1][O;H1:2]>>[c:1][O:2][C@@H]3O[C@H](C)[C@@H](O)[C@H](O)[C@H]3O"),
    ("glucuronidation", 176.03209, "[c:1][O;H1:2]>>[c:1][O:2][C@@H]3O[C@H](C(=O)O)[C@@H](O)[C@H](O)[C@H]3O"),
    
    # 5. 代谢与次生修饰高频结合反应
    ("sulfation", 79.95681, "[c,C:1][O,N;H1:2]>>[*:1][*:2]S(=O)(=O)O"),
    ("malonylation", 86.00039, "[O,N;H1:1]>>[*:1]C(=O)CC(=O)O"),
    ("galloylation", 152.01104, "[c,C:1][O;H1:2]>>[*:1][*:2]C(=O)c3cc(O)c(O)c(O)c3"),
    ("glycine_conjugation", 57.02146, "[C:1](=O)[O;H1:2]>>[C:1](=O)NCC(=O)O"),
]
COMPILED_RXNS = [(name, delta, AllChem.ReactionFromSmarts(smarts)) for name, delta, smarts in PMD_REACTIONS]
print(f"Reactomics Open-Set Engine loaded with {len(COMPILED_RXNS)} compiled reactions.", flush=True)

# ---------------------------------------------------------
# 7. Index Grand Clean Natural Product Pool (729k) & Seeds
# ---------------------------------------------------------
print("\nIndexing Grand Clean Natural Product Pool (Train + COCONUT)...", flush=True)
t_pool = time.time()
unique_train = pq.read_table(TRAIN_PATH, columns=['inchikey14', 'normalized_smiles', 'molecular_formula']).to_pandas().drop_duplicates('inchikey14')
coco_pool = pd.read_parquet(COCONUT_PATH, columns=['inchikey14', 'smiles', 'formula']).drop_duplicates('inchikey14')
coco_pool = coco_pool.rename(columns={'smiles': 'normalized_smiles', 'formula': 'molecular_formula'})

pool_df = pd.concat([unique_train, coco_pool]).drop_duplicates('inchikey14').reset_index(drop=True)
del unique_train, coco_pool
gc.collect()

pool_df['exact_mass'] = [parse_formula_mw(f) for f in pool_df['molecular_formula']]
pool_df = pool_df[pool_df['exact_mass'] > 50.0].sort_values('exact_mass').reset_index(drop=True)

pool_masses = pool_df['exact_mass'].values
pool_iks = pool_df['inchikey14'].values
pool_smis = pool_df['normalized_smiles'].values
pool_forms = pool_df['molecular_formula'].values
del pool_df
gc.collect()

seed_mws = pool_masses
seed_smiles = pool_smis
print(f"Grand NP Candidate & Seed Pool ready ({len(pool_masses):,} molecules) in {time.time()-t_pool:.2f}s", flush=True)

# 7.1 Index LOTUS Natural Product Backfill Pool (149k Secondary Metabolites)
lotus_masses, lotus_iks, lotus_smis = np.array([]), np.array([]), np.array([])
lotus_iks_set = set()
if LOTUS_PATH and os.path.exists(LOTUS_PATH):
    t_lotus = time.time()
    lotus_df = pd.read_parquet(LOTUS_PATH, columns=['inchikey14', 'smiles', 'monoisotopic_mass'])
    lotus_df = lotus_df.drop_duplicates('inchikey14').sort_values('monoisotopic_mass').reset_index(drop=True)
    lotus_masses = lotus_df['monoisotopic_mass'].values
    lotus_iks = lotus_df['inchikey14'].values
    lotus_smis = lotus_df['smiles'].values
    lotus_iks_set = set(lotus_iks)
    del lotus_df
    gc.collect()
    print(f"LOTUS Natural Product Pool ready ({len(lotus_masses):,} molecules) in {time.time()-t_lotus:.2f}s", flush=True)

# ---------------------------------------------------------
# 8. Multi-CE Targeted Class 1 MS2 Reference Library (Zero-OOM, All CEs)
# ---------------------------------------------------------
print("\nIndexing Multi-CE Class 1 MS2 Reference Library...", flush=True)
t_ref = time.time()
test_df = pd.read_parquet(TEST_PATH)
test_groups = list(test_df.groupby('molecule_id'))
print(f"Loaded {len(test_df)} spectra across {len(test_groups)} test molecules.", flush=True)

meta_table = pq.read_table(TRAIN_PATH, columns=['inchikey14', 'adduct', 'precursor_mz'])
meta_df = meta_table.to_pandas()
del meta_table
gc.collect()

meta_df['neutral_mass'] = [calc_neutral_mass(m, a) for m, a in zip(meta_df['precursor_mz'], meta_df['adduct'])]
meta_df['row_idx'] = np.arange(len(meta_df), dtype=np.int32)
meta_df = meta_df.sort_values('neutral_mass').reset_index(drop=True)

sorted_m = meta_df['neutral_mass'].values
sorted_adduct = meta_df['adduct'].values
sorted_orig_idx = meta_df['row_idx'].values

test_neutrals = [calc_neutral_mass(row['precursor_mz'], row['adduct']) for _, row in test_df.iterrows()]
test_adducts = test_df['adduct'].values

needed_rows = set()
for tn, ta in zip(test_neutrals, test_adducts):
    tol = tn * 20e-6
    l = np.searchsorted(sorted_m, tn - tol)
    r = np.searchsorted(sorted_m, tn + tol)
    if r > l:
        for idx in range(l, r):
            if sorted_adduct[idx] == ta:
                needed_rows.add(sorted_orig_idx[idx])

del meta_df, sorted_m, sorted_adduct, sorted_orig_idx
gc.collect()

print(f"Targeted {len(needed_rows):,} reference spectra across all collision energies (~200MB RAM)...", flush=True)

# Read only needed row groups
pf = pq.ParquetFile(TRAIN_PATH)
cols_ref = ['inchikey14', 'normalized_smiles', 'molecular_formula', 'adduct', 'precursor_mz', 'ms2_mzs', 'ms2_normalized_intensities']
curr_offset = 0
selected_dfs = []

for rg_idx in range(pf.num_row_groups):
    num_rg_rows = pf.metadata.row_group(rg_idx).num_rows
    rg_end = curr_offset + num_rg_rows
    needed_in_rg = sorted([idx - curr_offset for idx in needed_rows if curr_offset <= idx < rg_end])
    if needed_in_rg:
        rg_table = pf.read_row_group(rg_idx, columns=cols_ref)
        rg_sub = rg_table.take(needed_in_rg).to_pandas()
        selected_dfs.append(rg_sub)
        del rg_table
    curr_offset = rg_end

del needed_rows
gc.collect()

ref_table = pd.concat(selected_dfs).reset_index(drop=True)
del selected_dfs
gc.collect()

ref_table['neutral_mass'] = [calc_neutral_mass(m, a) for m, a in zip(ref_table['precursor_mz'], ref_table['adduct'])]
ref_table['mass_bin'] = (ref_table['neutral_mass'] * 100).astype(int)

ref_index = defaultdict(list)
for idx, b in enumerate(ref_table['mass_bin']):
    ref_index[b].append(idx)
    
ref_m = ref_table['neutral_mass'].values
ref_ik = ref_table['inchikey14'].values
ref_smi = ref_table['normalized_smiles'].values
ref_add = ref_table['adduct'].values
ref_form = ref_table['molecular_formula'].values

def get_peaks_array(mzs, ints):
    m = np.asarray(mzs, dtype=np.float32)
    i = np.asarray(ints, dtype=np.float32)
    mask = i >= 0.02
    m, i = m[mask], i[mask]
    return m, i

def count_matches(m1, m2, tol_da=0.015):
    i, j, matches = 0, 0, 0
    n1, n2 = len(m1), len(m2)
    while i < n1 and j < n2:
        diff = m1[i] - m2[j]
        if abs(diff) <= tol_da:
            matches += 1
            i += 1
            j += 1
        elif diff < 0:
            i += 1
        else:
            j += 1
    return matches

ref_peaks = [get_peaks_array(mz, it) for mz, it in zip(ref_table['ms2_mzs'], ref_table['ms2_normalized_intensities'])]
print(f"Multi-CE Reference Library ready ({len(ref_peaks):,} spectra) in {time.time()-t_ref:.2f}s", flush=True)

# ---------------------------------------------------------
# 9. Numba-Compiled Multi-Collision-Energy In-Silico Fragmentation Engine
# ---------------------------------------------------------
AMU = {'C': 12.0, 'H': 1.00782503207, 'N': 14.0030740048, 'O': 15.9949146196, 'P': 30.97376163,
       'S': 31.97207100, 'F': 18.99840322, 'Cl': 34.96885268, 'Br': 78.9183371, 'I': 126.904473,
       'Na': 22.9897692809, 'K': 38.96370668, 'Si': 27.9769265325, 'B': 11.0093054, 'Se': 79.9165213}
H_MASS = AMU['H']
E_MASS = 0.00054857990
PROTON = H_MASS - E_MASS
FORMATE = AMU['C'] + 2 * H_MASS + 2 * AMU['O']

FRAG_CARRIERS = {
    '[M+H]+': (PROTON,), '[M-H2O+H]+': (PROTON,), '[M-2H2O+H]+': (PROTON,),
    '[M+NH4]+': (PROTON, AMU['N'] + 4 * H_MASS - E_MASS),
    '[M+Na]+': (PROTON, AMU['Na'] - E_MASS), '[M+K]+': (PROTON, AMU['K'] - E_MASS),
    '[M-H]-': (-PROTON,), '[M-H2O-H]-': (-PROTON,),
    '[M+CH2O2-H]-': (-PROTON, FORMATE - PROTON),
    '[M+Cl]-': (-PROTON, AMU['Cl'] + E_MASS),
}

DEFAULT_FRAG_CFG = dict(
    intensity='sqrt',
    w1=1.0, w2=0.8,
    h_shifts=tuple(range(-2, 4)),
    max_breaks=2, max_bonds_2=100,
    tol=0.005
)

def _find_frag(parent, a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a

def _emit_components_frag(n, w, ea, eb, removed, parent, acc, out_m, out_k, cnt, k):
    for a in range(n):
        parent[a] = a
        acc[a] = 0.0
    ncomp = n
    for e in range(ea.shape[0]):
        if removed[e]: continue
        ra = _find_frag(parent, ea[e])
        rb = _find_frag(parent, eb[e])
        if ra != rb:
            parent[ra] = rb
            ncomp -= 1
    if ncomp < 2: return cnt
    for a in range(n):
        r = _find_frag(parent, a)
        acc[r] += w[a]
    for a in range(n):
        if parent[a] == a:
            out_m[cnt] = acc[a]
            out_k[cnt] = k
            cnt += 1
    return cnt

def _enumerate_frag(n, w, ea, eb, max_breaks, base_components):
    nb = ea.shape[0]
    n2 = nb * (nb - 1) // 2 if max_breaks >= 2 else 0
    cap = base_components + (base_components + 1) * nb + (base_components + 2) * n2
    out_m = np.empty(cap, np.float64)
    out_k = np.empty(cap, np.int8)
    parent = np.empty(n, np.int64)
    acc = np.empty(n, np.float64)
    removed = np.zeros(nb, np.bool_)
    cnt = 0
    for i in range(nb):
        removed[i] = True
        cnt = _emit_components_frag(n, w, ea, eb, removed, parent, acc, out_m, out_k, cnt, 1)
        if max_breaks >= 2:
            for j in range(i + 1, nb):
                removed[j] = True
                cnt = _emit_components_frag(n, w, ea, eb, removed, parent, acc, out_m, out_k, cnt, 2)
                removed[j] = False
        removed[i] = False
    return out_m[:cnt], out_k[:cnt]

def _calc_mod_cos_py(mzs1, ints1, mzs2, ints2, dm, tol=0.01):
    n1, n2 = len(mzs1), len(mzs2)
    if n1 == 0 or n2 == 0: return 0.0, 0
    max_c = n1 * n2
    m1_idx = np.empty(max_c, dtype=np.int32)
    m2_idx = np.empty(max_c, dtype=np.int32)
    scores = np.empty(max_c, dtype=np.float64)
    cnt = 0
    for i in range(n1):
        m1, i1 = mzs1[i], ints1[i]
        for j in range(n2):
            m2, i2 = mzs2[j], ints2[j]
            diff = m2 - m1
            if abs(diff) <= tol or abs(diff - dm) <= tol:
                m1_idx[cnt] = i
                m2_idx[cnt] = j
                scores[cnt] = np.sqrt(i1 * i2)
                cnt += 1
    if cnt == 0: return 0.0, 0
    order = np.argsort(-scores[:cnt])
    used1 = np.zeros(n1, dtype=np.bool_)
    used2 = np.zeros(n2, dtype=np.bool_)
    matched_score = 0.0
    n_matched = 0
    for k in range(cnt):
        idx = order[k]
        u, v = m1_idx[idx], m2_idx[idx]
        if not used1[u] and not used2[v]:
            used1[u] = True
            used2[v] = True
            matched_score += scores[idx]
            n_matched += 1
    norm1 = np.sqrt(np.sum(ints1))
    norm2 = np.sqrt(np.sum(ints2))
    if norm1 * norm2 <= 1e-8: return 0.0, 0
    return matched_score / (norm1 * norm2), n_matched

try:
    from numba import njit
    _find_frag = njit(cache=True, nogil=True)(_find_frag)
    _emit_components_frag = njit(cache=True, nogil=True)(_emit_components_frag)
    _enumerate_frag = njit(cache=True, nogil=True)(_enumerate_frag)
    calc_modified_cosine = njit(fastmath=True, cache=True, nogil=True)(_calc_mod_cos_py)
    HAVE_NUMBA = True
except Exception:
    calc_modified_cosine = _calc_mod_cos_py
    HAVE_NUMBA = False

def mol_graph_frag(smi):
    try:
        m = Chem.MolFromSmiles(smi) if isinstance(smi, str) and smi else None
    except Exception:
        m = None
    if m is None or m.GetNumAtoms() == 0: return None
    pt = Chem.GetPeriodicTable()
    w = np.empty(m.GetNumAtoms(), np.float64)
    for a in m.GetAtoms():
        s = a.GetSymbol()
        am = AMU.get(s) or pt.GetMostCommonIsotopeMass(s)
        w[a.GetIdx()] = am + a.GetTotalNumHs() * H_MASS
    ea = np.array([b.GetBeginAtomIdx() for b in m.GetBonds()], np.int64)
    eb = np.array([b.GetEndAtomIdx() for b in m.GetBonds()], np.int64)
    return w, ea, eb, len(Chem.GetMolFrags(m))

def fragment_levels_frag(smi, max_breaks=2, max_bonds_2=100):
    g = mol_graph_frag(smi)
    if g is None: return None
    w, ea, eb, npieces = g
    nb = len(ea)
    mb = int(max_breaks)
    if mb >= 2 and nb > max_bonds_2: mb = 1
    levels = [np.array([w.sum()])]
    if npieces > 1:
        m = Chem.MolFromSmiles(smi)
        levels = [np.unique(np.concatenate([[w.sum()], [w[list(ix)].sum() for ix in Chem.GetMolFrags(m)]]))]
    if nb == 0:
        return levels + [np.zeros(0) for _ in range(int(max_breaks))]
    fm, fk = _enumerate_frag(len(w), w, ea, eb, mb, npieces)
    fm = np.concatenate([levels[0], fm])
    fk = np.concatenate([np.zeros(len(levels[0]), np.int8), fk])
    key = np.round(fm, 5)
    order = np.lexsort((fk, key))
    key, fm, fk = key[order], fm[order], fk[order]
    first = np.ones(len(key), bool)
    first[1:] = key[1:] != key[:-1]
    fm, fk = fm[first], fk[first]
    return [np.sort(fm[fk == k]) for k in range(int(max_breaks) + 1)]

def _prep_spectrum_frag(s, c):
    mz = np.asarray(s.get('mz', ()), np.float64).ravel()
    it = np.asarray(s.get('it', ()), np.float64).ravel()
    n = min(len(mz), len(it))
    mz, it = mz[:n], it[:n]
    ok = np.isfinite(mz) & np.isfinite(it) & (it > 0)
    mz, it = mz[ok], it[ok]
    if len(mz) == 0: return None
    iw = np.sqrt(it) if c.get('intensity') == 'sqrt' else it
    tot = iw.sum()
    if not tot > 0: return None
    adduct = s.get('adduct', '[M+H]+')
    mode = s.get('mode', 1)
    carriers = FRAG_CARRIERS.get(adduct) or ((PROTON,) if (mode or 1) > 0 else (-PROTON,))
    shifts = np.array([car + dh * H_MASS for car in carriers for dh in c['h_shifts']])
    q = (mz[None, :] - shifts[:, None]).ravel()
    return iw / tot, q, len(shifts), len(mz)

def _score_spectrum_frag(levels, weights, prep, tol):
    iw, q, ns, npk = prep
    best = np.zeros(npk)
    for arr, wt in zip(levels, weights):
        if len(arr) == 0 or wt <= 0: continue
        a = np.searchsorted(arr, q - tol, 'left')
        b = np.searchsorted(arr, q + tol, 'right')
        hit = (b > a).reshape(ns, npk).any(axis=0)
        best = np.where(hit & (wt > best), wt, best)
    return float(iw @ best)

def score_candidates_multi_ce(spectra, cand_smiles, cache=None):
    cfg = DEFAULT_FRAG_CFG
    cache = {} if cache is None else cache
    weights = [1.0, float(cfg['w1']), float(cfg['w2'])]
    preps = [p for p in (_prep_spectrum_frag(s, cfg) for s in (spectra or [])) if p is not None]
    tol = float(cfg['tol'])
    n_cands = len(cand_smiles)
    if n_cands == 0:
        return [], []
    if not preps:
        return [0.0] * n_cands, [0.0] * n_cands
        
    cand_levels = []
    for smi in cand_smiles:
        key = (smi, int(cfg['max_breaks']), int(cfg['max_bonds_2']))
        if key in cache:
            lv = cache[key]
        else:
            try: lv = fragment_levels_frag(smi, cfg['max_breaks'], cfg['max_bonds_2'])
            except Exception: lv = None
            cache[key] = lv
        cand_levels.append(lv)
        
    raw_scores_all = []
    excl_scores_all = []
    
    for prep in preps:
        iw, q, ns, npk = prep
        cov = np.zeros((n_cands, npk), dtype=np.float64)
        for ci, lv in enumerate(cand_levels):
            if lv is None: continue
            best = np.zeros(npk)
            for arr, wt in zip(lv, weights):
                if len(arr) == 0 or wt <= 0: continue
                a = np.searchsorted(arr, q - tol, 'left')
                b = np.searchsorted(arr, q + tol, 'right')
                hit = (b > a).reshape(ns, npk).any(axis=0)
                best = np.where(hit & (wt > best), wt, best)
            cov[ci] = best
            
        raw_s = cov @ iw
        raw_scores_all.append(raw_s)
        
        # Exclusive diagnostic peaks explained by exactly 1 candidate
        expl_cnt = (cov > 0).sum(axis=0)
        hard_mask = (expl_cnt == 1)
        if hard_mask.any():
            excl_s = cov[:, hard_mask] @ iw[hard_mask]
        else:
            excl_s = np.zeros(n_cands)
        excl_scores_all.append(excl_s)
        
    mean_raw = np.mean(raw_scores_all, axis=0).tolist()
    mean_excl = np.mean(excl_scores_all, axis=0).tolist()
    return mean_raw, mean_excl

fragment_levels_frag('CCOC(=O)c1ccccc1O')
print(f"Numba Multi-CE In-Silico Fragmentation Engine ready (HAVE_NUMBA: {HAVE_NUMBA}).", flush=True)

# ---------------------------------------------------------
# 10. Main Autonomous V11 Inference Loop
# ---------------------------------------------------------
print("\n" + "=" * 72, flush=True)
print("=== Starting Full V11 Autonomous Inference on 400 Test Molecules ===", flush=True)
print("=" * 72, flush=True)
t_infer_start = time.time()

gen = AllChem.GetMorganGenerator(radius=2, fpSize=2048)
def get_cand_fp(m):
    return gen.GetFingerprintAsNumPy(m).astype(np.float32)

frag_cache = {}
results = []
n_c1_hits = 0
n_rxn_total = 0
n_lotus_backfilled = 0
all_mols_scored = {}
test_merged_specs = []

for m_idx, (mol_id, group) in enumerate(test_groups, 1):
    first_row = group.iloc[0]
    pmz = float(first_row['precursor_mz'])
    adduct = str(first_row['adduct'])
    neutral_mass = calc_neutral_mass(pmz, adduct)
    norm_add = NORM_ADDUCT.get(adduct, '[M+H]+')
    add_delta = ADDUCT_MAP.get(adduct, (1.007276, 1, 1))[0]
    
    # 10.1 Query Spectra Peak Aggregation & Multi-CE Specs
    all_mzs, all_ints = [], []
    q_specs = []
    spec_dicts = []
    for _, s in group.iterrows():
        qm, qi = get_peaks_array(s['ms2_mzs'], s['ms2_normalized_intensities'])
        if len(qm) > 0:
            q_specs.append((qm, qi, s['adduct']))
            all_mzs.extend(qm)
            all_ints.extend(qi)
            b_int = qi.max() if len(qi) else 1.0
            spec_dicts.append({
                'mz': qm,
                'it': qi / (b_int + 1e-6),
                'adduct': s.get('adduct', adduct),
                'prec': float(s.get('precursor_mz', pmz)),
                'mode': 1 if str(s.get('ionization_mode', 'positive')).lower() == 'positive' or '+' in str(s.get('adduct', adduct)) else -1
            })
    all_mzs = np.array(all_mzs, dtype=np.float64)
    all_ints = np.array(all_ints, dtype=np.float64)
    if len(all_mzs) > 0:
        order = np.argsort(all_mzs)
        m_s, i_s = all_mzs[order], all_ints[order]
        if len(m_s) > 60:
            top_idx = np.argsort(i_s)[-60:]
            top_idx.sort()
            m_s, i_s = m_s[top_idx], i_s[top_idx]
        test_merged_specs.append((mol_id, m_s, i_s, pmz))
    else:
        test_merged_specs.append((mol_id, np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.float64), pmz))
    
    # 10.2 Multi-CE Class 1 Spectral Entropy & Cosine Matching
    mbin_center = int(neutral_mass * 100)
    cand_indices = []
    for b in range(mbin_center - 2, mbin_center + 3):
        cand_indices.extend(ref_index.get(b, []))
        
    c1_matches = {}
    for c_idx in cand_indices:
        if abs(ref_m[c_idx] - neutral_mass) / neutral_mass * 1e6 <= 20.0:
            cand_ik = ref_ik[c_idx]
            rm, ri = ref_peaks[c_idx]
            radd = ref_add[c_idx]
            if len(rm) == 0: continue
            
            best_sim = 0.0
            best_nm = 0
            for qm, qi, qadd in q_specs:
                if radd != qadd: continue
                n_m = count_matches(qm, rm, tol_da=0.015)
                if n_m < 3: continue
                # Native C++ Spectral Entropy & Cosine
                ent = hz.spectral_entropy(qm, qi, rm, ri, tol_da=0.015)
                cos = hz.fast_cosine(qm, qi, rm, ri, tol_da=0.015)
                sim = max(ent, cos)
                if sim > best_sim:
                    best_sim = sim
                    best_nm = n_m
            if best_sim >= 0.70 and best_nm >= 3:
                eff_sim = best_sim * (1.0 + 0.01 * min(best_nm, 20))
                c1_matches[cand_ik] = max(c1_matches.get(cand_ik, 0.0), eff_sim)
                
    if len(c1_matches) > 0:
        n_c1_hits += 1
        
    # 10.3 Sourcing Candidates (Closed-Set Database vs Open-Set In-Silico)
    closed_dict = {}     # ik -> (smi, form)
    reactomics_dict = {} # ik -> (smi, form)
    
    # A. Closed-Set: Precursor Mass Window ±12 ppm around calibrated center (-1.7 ppm)
    cal_mass = neutral_mass * (1.0 - 1.7e-6)
    tol = cal_mass * 12e-6
    i_l = np.searchsorted(pool_masses, cal_mass - tol)
    i_r = np.searchsorted(pool_masses, cal_mass + tol)
    if i_r == i_l:
        tol = cal_mass * 30e-6
        i_l = np.searchsorted(pool_masses, cal_mass - tol)
        i_r = np.searchsorted(pool_masses, cal_mass + tol)
    if i_r == i_l:
        idx_c = np.searchsorted(pool_masses, cal_mass)
        i_l = max(0, idx_c - 15)
        i_r = min(len(pool_masses), idx_c + 15)
        
    for p_idx in range(i_l, i_r):
        c_ik = pool_iks[p_idx]
        if c_ik not in closed_dict:
            closed_dict[c_ik] = (pool_smis[p_idx], pool_forms[p_idx])
            
    # Anchor Class 1 matches
    for c1_ik in c1_matches:
        if c1_ik not in closed_dict:
            c1_cand_idx = np.where(ref_ik == c1_ik)[0]
            if len(c1_cand_idx) > 0:
                closed_dict[c1_ik] = (ref_smi[c1_cand_idx[0]], ref_form[c1_cand_idx[0]])
                
    # B. Open-Set Reactomics In-Silico Gap-Filling (ONLY if closed-set candidates < 25)
    if len(closed_dict) < 25:
        for rxn_name, delta_pmd, rxn in COMPILED_RXNS:
            seed_target = neutral_mass - delta_pmd
            tol_pmd = seed_target * 18e-6
            l = np.searchsorted(seed_mws, seed_target - tol_pmd)
            r = np.searchsorted(seed_mws, seed_target + tol_pmd)
            if r > l:
                for s_idx in range(l, min(r, l + 8)):
                    seed_s = seed_smiles[s_idx]
                    seed_m = Chem.MolFromSmiles(seed_s)
                    if not seed_m: continue
                    try:
                        for prod_tuple in rxn.RunReactants((seed_m,)):
                            p_mol = prod_tuple[0]
                            Chem.SanitizeMol(p_mol)
                            p_form = rdMolDescriptors.CalcMolFormula(p_mol)
                            p_smi = Chem.MolToSmiles(p_mol)
                            p_ik = Chem.MolToInchiKey(p_mol)[:14]
                            if p_ik not in closed_dict and p_ik not in reactomics_dict:
                                p_mw = Descriptors.ExactMolWt(p_mol)
                                p_ppm = (p_mw - neutral_mass) / neutral_mass * 1e6
                                if abs(p_ppm - (-1.7)) <= 6.0:
                                    p_raw, _ = score_candidates_multi_ce(spec_dicts, [p_smi], cache=frag_cache)
                                    p_mf = p_raw[0] if p_raw else 0.0
                                    if p_mf >= 0.15:
                                        reactomics_dict[p_ik] = (p_smi, p_form)
                                        n_rxn_total += 1
                                        if len(closed_dict) + len(reactomics_dict) >= 30:
                                            break
                    except Exception:
                        continue
            if len(closed_dict) + len(reactomics_dict) >= 30:
                break

    # 10.4 HORIZON MS2 Formula Explanation
    eval_forms = set([v[1] for v in closed_dict.values()] + [v[1] for v in reactomics_dict.values()])
    formula_scores = {}
    for form in eval_forms:
        try:
            exp_mask = hz.explain(all_mzs, form, norm_add, ppm=25.0)
            exp_intensity = np.sum(all_ints[exp_mask])
            tot_intensity = np.sum(all_ints) + 1e-6
            formula_scores[form] = exp_intensity / tot_intensity
        except Exception:
            formula_scores[form] = 0.0
            
    best_form = max(formula_scores.keys(), key=lambda f: formula_scores[f]) if formula_scores else None

    # 10.5 Neural Fingerprint Prediction via PMD_FPNet_1056d (Raw Peaks >= 0.02)
    # Using 1056d Golden Core [50, 800] Da: Val Cosine 0.5685, Local MRR@25 0.5019
    vec = compute_1056d_barcode(all_mzs, all_ints, pmz)
    with torch.no_grad():
        x_t = torch.tensor(vec, dtype=torch.float32, device=device).unsqueeze(0)
        p_logits = model(x_t)
        pred_fp = torch.sigmoid(p_logits).squeeze(0).cpu().numpy()
        norm_pred = np.linalg.norm(pred_fp) + 1e-6

    # 10.6 Multi-CE Fragmentation Rescoring & Candidate Ranking (Calibrated Physics Core)
    cand_list = list(closed_dict.items())
    cand_smis = [item[1][0] for item in cand_list]
    multi_ce_scores, excl_scores = score_candidates_multi_ce(spec_dicts, cand_smis, cache=frag_cache) if (spec_dicts and cand_smis) else ([0.0] * len(cand_list), [0.0] * len(cand_list))

    all_scored = []
    for idx, (ik, (smi, form)) in enumerate(cand_list):
        m = Chem.MolFromSmiles(smi)
        if not m: continue
        arr = get_cand_fp(m)
        norm_c = np.linalg.norm(arr) + 1e-6
        fp_sim = float(np.dot(pred_fp, arr) / (norm_pred * norm_c))
        
        mf_score = float(multi_ce_scores[idx]) if (multi_ce_scores and multi_ce_scores[idx] is not None) else 0.0
        excl_score = float(excl_scores[idx]) if (excl_scores and excl_scores[idx] is not None) else 0.0
        
        # High-resolution timsTOF continuous Gaussian error prior
        cand_mass = Descriptors.ExactMolWt(m)
        ppm_err = (cand_mass - neutral_mass) / neutral_mass * 1e6
        gauss_pen = -0.5 * ((ppm_err - (-1.7)) / 2.0) ** 2
        
        # Natural product complexity & ring rigidity prior
        n_rings = int(rdMolDescriptors.CalcNumRings(m))
        ring_bonus = 0.10 * n_rings
        n_rot = int(rdMolDescriptors.CalcNumRotatableBonds(m))
        rot_bonus = -0.08 * n_rot
        
        # LOTUS organism-verified natural product consensus bonus (Validated optimal w=0.50)
        lotus_bonus = 0.50 if ik in lotus_iks_set else 0.0
        
        # Class 1 Empirical Bonus (25.0 * eff_sim, strictly guarded by best_nm >= 3)
        c1_bonus = (25.0 * c1_matches[ik]) if ik in c1_matches else 0.0
        f_bonus = formula_scores.get(form, 0.0) * 1.5
        
        # Validated optimal multi-objective score (MRR 0.5981 on disjoint NP validation panel)
        total_score = (c1_bonus + 
                       7.0 * fp_sim + 
                       f_bonus + 
                       4.5 * mf_score + 
                       3.0 * excl_score + 
                       0.25 * gauss_pen + 
                       ring_bonus + 
                       rot_bonus +
                       lotus_bonus)
        all_scored.append((ik, smi, total_score, 'closed'))
        
    # 10.7 Reactomics In-Silico Analogs Scoring
    rxn_list = list(reactomics_dict.items())
    rxn_smis = [item[1][0] for item in rxn_list]
    rxn_ce_scores, rxn_excl_scores = score_candidates_multi_ce(spec_dicts, rxn_smis, cache=frag_cache) if (spec_dicts and rxn_smis) else ([0.0] * len(rxn_list), [0.0] * len(rxn_list))
    for idx, (ik, (smi, form)) in enumerate(rxn_list):
        m = Chem.MolFromSmiles(smi)
        if not m: continue
        arr = get_cand_fp(m)
        norm_c = np.linalg.norm(arr) + 1e-6
        fp_sim = float(np.dot(pred_fp, arr) / (norm_pred * norm_c))
        
        mf_score = float(rxn_ce_scores[idx]) if (rxn_ce_scores and rxn_ce_scores[idx] is not None) else 0.0
        excl_score = float(rxn_excl_scores[idx]) if (rxn_excl_scores and rxn_excl_scores[idx] is not None) else 0.0
        cand_mass = Descriptors.ExactMolWt(m)
        ppm_err = (cand_mass - neutral_mass) / neutral_mass * 1e6
        gauss_pen = -0.5 * ((ppm_err - (-1.7)) / 2.0) ** 2
        
        n_rings = int(rdMolDescriptors.CalcNumRings(m))
        ring_bonus = 0.10 * n_rings
        n_rot = int(rdMolDescriptors.CalcNumRotatableBonds(m))
        rot_bonus = -0.08 * n_rot
        f_bonus = formula_scores.get(form, 0.0) * 1.5
        
        # Gentle biological synthesis bonus (+0.15)
        rxn_score = (7.0 * fp_sim + 
                     f_bonus + 
                     4.5 * mf_score + 
                     3.0 * excl_score + 
                     0.25 * gauss_pen + 
                     ring_bonus + 
                     rot_bonus + 
                     0.15)
        all_scored.append((ik, smi, rxn_score, 'reactomics'))
        
    all_mols_scored[mol_id] = {'cands': all_scored, 'neutral_mass': neutral_mass}
    
    if m_idx % 50 == 0 or m_idx == len(test_groups):
        print(f"[{m_idx:3d}/{len(test_groups)}] Scored | Class 1 Hits: {n_c1_hits} | Rxn Novel Mol: {n_rxn_total} | Elapsed: {time.time()-t_infer_start:.1f}s", flush=True)

# ---------------------------------------------------------
# 10.8 Strategy A: Test-Time Congener Scaffold Consensus Network
# ---------------------------------------------------------
print("\n" + "=" * 72, flush=True)
print("=== Strategy A: Passing Congener Scaffold Consensus across MS2 Network ===", flush=True)
print("=" * 72, flush=True)
t_congener = time.time()
n_mols = len(test_merged_specs)
congener_edges = []
for i in range(n_mols):
    u_id, mzs1, ints1, p1 = test_merged_specs[i]
    for j in range(i + 1, n_mols):
        v_id, mzs2, ints2, p2 = test_merged_specs[j]
        dm = p2 - p1
        cos, n_m = calc_modified_cosine(mzs1, ints1, mzs2, ints2, dm, tol=0.01)
        if cos >= 0.65 and n_m >= 4:
            congener_edges.append((u_id, v_id, cos, dm, n_m))

print(f"Found {len(congener_edges)} congener pairs (ModCos >= 0.65) in {time.time()-t_congener:.2f}s!", flush=True)

# Extract Murcko scaffolds for all candidates (Safe against RDKit 2026 bad bond stereo)
from rdkit.Chem.Scaffolds import MurckoScaffold
def safe_murcko_scaffold(smi):
    if not isinstance(smi, str) or not smi: return ''
    try:
        m = Chem.MolFromSmiles(smi)
        if not m: return ''
        Chem.RemoveStereochemistry(m)
        return MurckoScaffold.MurckoScaffoldSmiles(mol=m)
    except Exception:
        return ''

mol_scaffolds = {}
for mid, data in all_mols_scored.items():
    mol_scaffolds[mid] = [safe_murcko_scaffold(smi) for _, smi, _, _ in data['cands']]

# Message passing / mutual reinforcement
reinforce_count = 0
for u, v, cos, dm, n_m in congener_edges:
    if u not in all_mols_scored or v not in all_mols_scored: continue
    sc_u = mol_scaffolds[u]
    sc_v = mol_scaffolds[v]
    cands_u = all_mols_scored[u]['cands']
    cands_v = all_mols_scored[v]['cands']
    
    max_v = {}
    for i, sc in enumerate(sc_v):
        if sc and (sc not in max_v or cands_v[i][2] > max_v[sc]):
            max_v[sc] = cands_v[i][2]
            
    max_u = {}
    for i, sc in enumerate(sc_u):
        if sc and (sc not in max_u or cands_u[i][2] > max_u[sc]):
            max_u[sc] = cands_u[i][2]
            
    # Reinforce u
    for i, sc in enumerate(sc_u):
        if sc and sc in max_v:
            bonus = 0.50 * cos * max(0.0, max_v[sc] / 5.0)
            ik, smi, sc_old, src = cands_u[i]
            cands_u[i] = (ik, smi, sc_old + bonus, src)
            reinforce_count += 1
            
    # Reinforce v
    for i, sc in enumerate(sc_v):
        if sc and sc in max_u:
            bonus = 0.50 * cos * max(0.0, max_u[sc] / 5.0)
            ik, smi, sc_old, src = cands_v[i]
            cands_v[i] = (ik, smi, sc_old + bonus, src)
            reinforce_count += 1

print(f"Applied {reinforce_count} congener scaffold mutual reinforcements!", flush=True)

# 10.9 Final InChIKey-14 Deduplication & LOTUS Tail Backfill
for mid, data in all_mols_scored.items():
    cands = data['cands']
    neutral_mass = data['neutral_mass']
    cands.sort(key=lambda x: -x[2])

    final_candidates = []
    seen_iks = set()
    for ik, smi, sc, src in cands:
        if ik not in seen_iks:
            seen_iks.add(ik)
            final_candidates.append(smi)
            if len(final_candidates) >= 25:
                break
                
    if len(final_candidates) < 25 and len(lotus_masses) > 0:
        l_tol = neutral_mass * 20e-6
        l_idx_l = np.searchsorted(lotus_masses, neutral_mass - l_tol)
        l_idx_r = np.searchsorted(lotus_masses, neutral_mass + l_tol)
        if l_idx_r == l_idx_l:
            l_tol = neutral_mass * 50e-6
            l_idx_l = np.searchsorted(lotus_masses, neutral_mass - l_tol)
            l_idx_r = np.searchsorted(lotus_masses, neutral_mass + l_tol)
        
        lotus_cands = []
        for l_i in range(l_idx_l, l_idx_r):
            lik = lotus_iks[l_i]
            if lik not in seen_iks:
                lotus_cands.append((lik, lotus_smis[l_i], abs(lotus_masses[l_i] - neutral_mass)))
        lotus_cands.sort(key=lambda x: x[2])
        for lik, lsmi, _ in lotus_cands:
            seen_iks.add(lik)
            final_candidates.append(lsmi)
            n_lotus_backfilled += 1
            if len(final_candidates) >= 25:
                break

    if len(final_candidates) < 25:
        idx_c = np.searchsorted(pool_masses, neutral_mass)
        for fb_idx in range(max(0, idx_c - 50), min(len(pool_masses), idx_c + 50)):
            fb_ik = pool_iks[fb_idx]
            if fb_ik not in seen_iks:
                seen_iks.add(fb_ik)
                final_candidates.append(pool_smis[fb_idx])
                if len(final_candidates) >= 25:
                    break
                    
    results.append({
        'molecule_id': mid,
        'smiles': ';'.join(final_candidates[:25])
    })

# ---------------------------------------------------------
# 11. Final Submission Verification & Export
# ---------------------------------------------------------
sub_df = pd.DataFrame(results)
out_csv = '/kaggle/working/submission.csv' if os.path.exists('/kaggle') else 'scratch/casmi26/kernel_v10_autonomous/submission.csv'

print("\n" + "=" * 72, flush=True)
print("=== SUBMISSION VERIFICATION AUDIT ===", flush=True)
print(f"Total Rows:     {len(sub_df)} (Expected: 400)", flush=True)
print(f"Columns:        {sub_df.columns.tolist()} (Expected: ['molecule_id', 'smiles'])", flush=True)

smi_lens = [len(str(s).split(';')) for s in sub_df['smiles']]
print(f"SMILES Counts:  Min={min(smi_lens)}, Median={np.median(smi_lens)}, Max={max(smi_lens)} (All must be 25)", flush=True)
print(f"Class 1 Hits:   {n_c1_hits} / {len(test_groups)} ({n_c1_hits/len(test_groups)*100:.1f}%)", flush=True)
print(f"Novel Analogs:  {n_rxn_total} created via Reactomics In-Silico Derivatization", flush=True)
print(f"LOTUS Backfill: {n_lotus_backfilled} tail slots backfilled from LOTUS", flush=True)
print(f"Total Time:     {time.time()-t_start:.2f}s", flush=True)
print("=" * 72, flush=True)

sub_df.to_csv(out_csv, index=False)
print(f"\n[SUCCESS] Final V12 submission saved strictly to: {out_csv}", flush=True)
