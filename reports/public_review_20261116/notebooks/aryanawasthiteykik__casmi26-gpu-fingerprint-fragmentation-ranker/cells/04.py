import numpy as np, pandas as pd
import matplotlib.pyplot as plt

res = pd.read_csv(V3 / 'compare_models.csv')
mrr = res.groupby(['split', 'model']).rr.mean().unstack()
splits = ['S1 np-examples', 'S2 enveda-180 holdout']
names = {'S1 np-examples': 'S1: library natural products', 'S2 enveda-180 holdout': 'S2: no public spectra'}

INK, INK2, MUTED, GRID, SURFACE = '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#fcfcfb'
COLORS = {'fpnet_v2h': '#2a78d6', 'fpnet_v3h': '#eb6834'}
LABELS = {'fpnet_v2h': 'v2 (CPU, 2 x 2,048)', 'fpnet_v3h': 'v3 (GPU, 3 x 4,096)'}
fig, ax = plt.subplots(figsize=(8.5, 4.2), facecolor=SURFACE)
ax.set_facecolor(SURFACE)
x, w = np.arange(len(splits)), 0.34
for k, (model, off) in enumerate([('fpnet_v2h', -w / 2), ('fpnet_v3h', w / 2)]):
    vals = [mrr.loc[s, model] for s in splits]
    ax.bar(x + off, vals, w - 0.02, color=COLORS[model], label=LABELS[model], zorder=3)
    for xi, v in zip(x + off, vals):
        ax.text(xi, v + 0.01, f'{v:.3f}', ha='center', va='bottom', fontsize=10, color=INK2)
ax.set_xticks(x, [names[s] for s in splits], color=INK2)
ax.set_ylabel('MRR@25, fingerprint likelihood alone', color=INK2)
ax.set_ylim(0, max(0.6, mrr.values.max() * 1.15))
ax.set_title('Answers reachable only through PubChem (~5k-10k candidates each)', loc='left', color=INK, fontsize=12)
ax.grid(axis='y', color=GRID, linewidth=0.8, zorder=0)
for s in ('top', 'right'):
    ax.spines[s].set_visible(False)
for s in ('left', 'bottom'):
    ax.spines[s].set_color(MUTED)
ax.tick_params(colors=INK2)
ax.legend(frameon=False, labelcolor=INK2)
plt.tight_layout(); plt.show()

table = res.groupby(['split', 'model']).agg(molecules=('rr', 'size'), MRR=('rr', 'mean'), top1=('top1', 'mean'),
                                            top25=('top25', 'mean')).round(3)
table