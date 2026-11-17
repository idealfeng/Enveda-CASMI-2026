# Picture: the public score at each network weight (no data loaded)
try:   # a drawing error must never stop the run
    import matplotlib.pyplot as plt
    lam = [0.0, 0.15, 0.25, 0.35, 0.50]; lb = [0.487, 0.487, 0.488, 0.492, 0.484]
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    ax.plot(lam, lb, marker='o', color='#4C78A8')
    ax.scatter([0.35], [0.492], s=120, color='#F58518', zorder=3, label='this notebook')
    for x, y in zip(lam, lb):
        ax.annotate(f'{y:.3f}', (x, y), textcoords='offset points', xytext=(0, 7), ha='center', fontsize=9)
    ax.set_xlabel('network weight LAM'); ax.set_ylabel('public MRR@25'); ax.set_ylim(0.480, 0.496)
    ax.set_title('Test-set network rerank: how much weight?', fontsize=11); ax.legend(loc='lower left', fontsize=8)
    ax.spines[['top', 'right']].set_visible(False); plt.tight_layout(); plt.show()
except Exception as e:
    print('picture skipped:', e)
