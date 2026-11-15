# ======================================================================
# 🧠 CYCLE 3 WSP CONV1D DUAL-ENCODER SOFT RANK FUSION
# ======================================================================
import os
import sys
import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator

print('--- INITIALIZING CYCLE 3 WSP DUAL-ENCODER SOFT RANK FUSION ---')

class SpectrumConv1DEncoder(nn.Module):
    def __init__(self, in_bins=2000, hidden_dim=512, embed_dim=256):
        super().__init__()
        self.conv1 = nn.Conv1d(1, 16, kernel_size=7, stride=2, padding=3)
        self.bn1 = nn.BatchNorm1d(16)
        self.conv2 = nn.Conv1d(16, 32, kernel_size=5, stride=2, padding=2)
        self.bn2 = nn.BatchNorm1d(32)
        self.pool = nn.AdaptiveAvgPool1d(64)
        conv_out_dim = 32 * 64
        self.fc1 = nn.Linear(conv_out_dim, hidden_dim)
        self.ln1 = nn.LayerNorm(hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, embed_dim)

    def forward(self, x):
        x = x.unsqueeze(1)
        x = F.gelu(self.bn1(self.conv1(x)))
        x = F.gelu(self.bn2(self.conv2(x)))
        x = self.pool(x)
        x = x.view(x.size(0), -1)
        x = F.gelu(self.ln1(self.fc1(x)))
        x = self.fc2(x)
        return F.normalize(x, p=2, dim=-1)

class MoleculeEncoder(nn.Module):
    def __init__(self, in_dim=2048, hidden_dim=512, embed_dim=256):
        super().__init__()
        self.fc1 = nn.Linear(in_dim, 1024)
        self.bn1 = nn.BatchNorm1d(1024)
        self.fc2 = nn.Linear(1024, hidden_dim)
        self.ln1 = nn.LayerNorm(hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, embed_dim)

    def forward(self, x):
        x = F.gelu(self.bn1(self.fc1(x)))
        x = F.gelu(self.ln1(self.fc2(x)))
        x = self.fc3(x)
        return F.normalize(x, p=2, dim=-1)

class CASMIDualEncoder(nn.Module):
    def __init__(self, in_bins=2000, fp_dim=2048, embed_dim=256):
        super().__init__()
        self.spectrum_encoder = SpectrumConv1DEncoder(in_bins=in_bins, embed_dim=embed_dim)
        self.molecule_encoder = MoleculeEncoder(in_dim=fp_dim, embed_dim=embed_dim)
        self.logit_scale = nn.Parameter(torch.ones([]) * float(np.log(1 / 0.07)))

    def forward(self, spectra, fingerprints):
        z_spec = self.spectrum_encoder(spectra)
        z_mol = self.molecule_encoder(fingerprints)
        return z_spec, z_mol

def find_wsp_checkpoint():
    candidates = [
        '/kaggle/input/casmi26-cycle-3-wsp-gpu-trainer/casmi26_cycle3_wsp_model/casmi26_cycle3_model.pt',
        '/kaggle/input/notebooks/kingdamon/casmi26-cycle-3-wsp-gpu-trainer/casmi26_cycle3_wsp_model/casmi26_cycle3_model.pt',
        '/kaggle/input/casmi26-cycle-3-gpu-trainer/casmi26_cycle3_wsp_model/casmi26_cycle3_model.pt',
        '/kaggle/input/casmi26-wsp-spectrum-embedder/casmi26_cycle3_model.pt'
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    for root, dirs, files in os.walk('/kaggle/input'):
        if 'casmi26_cycle3_model.pt' in files:
            return os.path.join(root, 'casmi26_cycle3_model.pt')
    return None

ckpt_path = find_wsp_checkpoint()
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'Cycle 3 WSP Checkpoint: {ckpt_path} | Device: {device}')

if ckpt_path and os.path.exists(ckpt_path):
    print('Loading Cycle 3 WSP Conv1D Dual-Encoder model weights...')
    model = CASMIDualEncoder(in_bins=2000, fp_dim=2048, embed_dim=256).to(device)
    model.load_state_dict(torch.load(ckpt_path, map_location=device))
    model.eval()
    print('✅ Cycle 3 WSP Conv1D Dual-Encoder loaded successfully!')

    df_curr = pd.read_csv('submission.csv')
    print(f'Current submission has {len(df_curr)} molecule rows.')

    fp_gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)

    def bin_spec(mzs, intens, num_bins=2000, max_mz=1000.0):
        vec = np.zeros(num_bins, dtype=np.float32)
        bin_sz = max_mz / num_bins
        if mzs is not None and intens is not None:
            for mz, it in zip(mzs, intens):
                if 0 < mz < max_mz:
                    idx = int(mz / bin_sz)
                    if idx < num_bins:
                        vec[idx] = max(vec[idx], float(it))
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    test_parquet_path = None
    for p in ['/kaggle/input/competitions/enveda-CASMI26-molecule-id-mass-spectra/test.parquet',
              '/kaggle/input/enveda-CASMI26-molecule-id-mass-spectra/test.parquet']:
        if os.path.exists(p):
            test_parquet_path = p
            break

    if test_parquet_path:
        test_spec_df = pd.read_parquet(test_parquet_path).set_index('molecule_id')
        print(f'Loaded test spectra for {len(test_spec_df)} molecules.')

        rescored_rows = []
        BETA = 0.22  # Tuned Soft Rank Fusion Weight
        TOP_K = 25

        for row_idx, row in df_curr.iterrows():
            mol_id = row['molecule_id']
            candidates_str = str(row['candidate_smiles']).split()
            if not candidates_str or len(candidates_str) <= 1 or mol_id not in test_spec_df.index:
                rescored_rows.append(' '.join(candidates_str[:TOP_K]))
                continue

            spec_row = test_spec_df.loc[mol_id]
            mzs = spec_row.get('ms2_mzs', None)
            intens = spec_row.get('ms2_normalized_intensities', None)
            spec_binned = bin_spec(mzs, intens)
            spec_tensor = torch.tensor(spec_binned, dtype=torch.float32).unsqueeze(0).to(device)

            with torch.no_grad():
                z_spec = model.spectrum_encoder(spec_tensor).cpu().numpy()[0]  # (256,)

            candidate_scores = []
            for base_rank, smi in enumerate(candidates_str[:TOP_K]):
                try:
                    mol = Chem.MolFromSmiles(smi)
                    if mol:
                        fp = fp_gen.GetFingerprintAsNumPy(mol).astype(np.float32)
                        fp_tensor = torch.tensor(fp).unsqueeze(0).to(device)
                        with torch.no_grad():
                            z_mol = model.molecule_encoder(fp_tensor).cpu().numpy()[0]
                        sim = float(np.dot(z_spec, z_mol))
                    else:
                        sim = 0.0
                except Exception:
                    sim = 0.0

                # Soft Rank Fusion Law
                s_fused = (1.0 / np.sqrt(base_rank + 1.0)) + (BETA * sim)
                candidate_scores.append((s_fused, smi))

            candidate_scores.sort(key=lambda x: x[0], reverse=True)
            reordered_smiles = [smi for _, smi in candidate_scores] + candidates_str[TOP_K:]
            rescored_rows.append(' '.join(reordered_smiles[:TOP_K]))

        df_curr['candidate_smiles'] = rescored_rows
        df_curr.to_csv('submission.csv', index=False)
        print('✅ Successfully wrote Cycle 3 WSP Soft Rank Fusion submission.csv!')
        print(df_curr.head(5))
else:
    print('⚠️ Cycle 3 WSP Checkpoint not found; fallback baseline preserved.')
