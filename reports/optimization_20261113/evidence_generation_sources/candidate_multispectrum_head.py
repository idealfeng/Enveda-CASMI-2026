"""Candidate-conditioned residual/attention head; frozen v2 features are its input."""
from __future__ import annotations
import torch
from torch import nn


class CandidateMultiSpectrumHead(nn.Module):
    def __init__(self, embedding=192, hidden=64, residual_bound=4.0):
        super().__init__()
        self.embedding, self.hidden = embedding, hidden
        self.residual_bound = residual_bound
        self.network = nn.Sequential(nn.Linear(2 * embedding + 19, hidden), nn.GELU(),
                                     nn.Linear(hidden, 2))
        nn.init.zeros_(self.network[-1].weight)
        nn.init.zeros_(self.network[-1].bias)

    def forward(self, z, m, cos, fp_score, metadata, adduct, peak_fraction, spectrum_mask):
        """B,S,D; B,C,D; B,S,C; B,S,4; B,S; B,S; B,S -> B,C."""
        b, s, d = z.shape
        c = m.shape[1]
        zz, mm = z[:, :, None, :].expand(-1, -1, c, -1), m[:, None].expand(-1, s, -1, -1)
        extra = torch.cat([metadata, torch.nn.functional.one_hot(adduct.long(), 11).to(z.dtype),
                           peak_fraction[..., None]], -1)
        extra = extra[:, :, None].expand(-1, -1, c, -1)
        base = cos / 0.1 + 2.0 * fp_score
        x = torch.cat([zz * mm, (zz - mm).abs(), extra,
                       cos[..., None], fp_score[..., None], base[..., None]], -1)
        out = self.network(x)
        attention = out[..., 1].masked_fill(~spectrum_mask[:, :, None], -1e4).softmax(1)
        return (attention * (base + self.residual_bound * out[..., 0].tanh())).sum(1)


def head_config():
    return dict(embedding=192, hidden=64, residual_bound=4.0)
