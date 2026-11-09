"""Bounded isomer correction with the original uniform spectrum mean frozen.

The inference interface deliberately matches CandidateMultiSpectrumHead. There
is no candidate-list normalization or learned spectrum attention in this head.
"""
from __future__ import annotations
import torch
from torch import nn


class CandidateMultiSpectrumHead(nn.Module):
    def __init__(self, embedding=192, hidden=64, residual_bound=0.5):
        super().__init__()
        self.embedding, self.hidden = embedding, hidden
        self.residual_bound = residual_bound
        self.network = nn.Sequential(nn.Linear(2 * embedding + 19, hidden),
                                     nn.GELU(), nn.Linear(hidden, 1))
        nn.init.zeros_(self.network[-1].weight)
        nn.init.zeros_(self.network[-1].bias)

    def forward(self, z, m, cos, fp_score, metadata, adduct, peak_fraction, spectrum_mask):
        b, s, _ = z.shape
        c = m.shape[1]
        zz = z[:, :, None, :].expand(-1, -1, c, -1)
        mm = m[:, None].expand(-1, s, -1, -1)
        extra = torch.cat([metadata,
                           torch.nn.functional.one_hot(adduct.long(), 11).to(z.dtype),
                           peak_fraction[..., None]], -1)
        extra = extra[:, :, None].expand(-1, -1, c, -1)
        base = cos / 0.1 + 2.0 * fp_score
        x = torch.cat([zz * mm, (zz - mm).abs(), extra,
                       cos[..., None], fp_score[..., None], base[..., None]], -1)
        correction = self.residual_bound * self.network(x).squeeze(-1).tanh()
        weights = spectrum_mask.to(z.dtype)
        weights = weights / weights.sum(1, keepdim=True).clamp_min(1)
        return (weights[..., None] * (base + correction)).sum(1)


def head_config():
    return dict(embedding=192, hidden=64, residual_bound=0.5)
