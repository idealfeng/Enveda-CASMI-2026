# Out-of-fold report: share of molecules whose answer is first by the joint ranker against the FPNet score, the
# channel score z(FPNet) + 0.25 x documentation and documentation alone; then the margins at which the joint ranker's
# first choice is right often enough to move a rank 1 (90%) or to take rank 2 (50%), fitted on the test-like molecules.
ci = {f: F.index(f) for f in F}
rows = []
for i, M in enumerate(MOLS):
    s, y, X = OOF[i], M['y'], M['X']
    o = np.argsort(-s, kind='stable')
    pos = np.where(y[o] == 1)[0]
    rows.append(dict(key=M['key'], testlike=M['testlike'], in_window=M['in_window'], in_sel=bool(y.any()), n_window=M['n_window'],
                     margin=float(s[o[0]] - s[o[1]]) if len(o) > 1 else 9.0, joint=bool(y[o[0]]),
                     joint_rank=int(pos[0]) + 1 if len(pos) else 0,
                     fz=bool(y[np.argmax(X[:, ci['fzz']])]), chan=bool(y[np.argmax(X[:, ci['chan']])]),
                     docs=bool(y[np.argmax(X[:, ci['pop']])])))
R = pd.DataFrame(rows)
R.to_parquet(WORK / 'isomer_ranker_oof.parquet', index=False)


def summary(d):
    rr = d.joint_rank.values
    return dict(n=len(d), in_window=round(d.in_window.mean(), 4), in_sel=round(d.in_sel.mean(), 4),
                top1_joint=round(d.joint.mean(), 4), top1_chan=round(d.chan.mean(), 4), top1_fz=round(d.fz.mean(), 4),
                top1_docs=round(d.docs.mean(), 4), mrr25_joint=round(float(np.where((rr > 0) & (rr <= 25), 1.0 / np.maximum(rr, 1), 0).mean()), 4))


def threshold(d, prec, min_n):
    o = np.argsort(-d.margin.values, kind='stable')
    c = np.cumsum(d.joint.values[o])
    k = np.arange(1, len(o) + 1)
    ok = np.where((c / k >= prec) & (k >= min_n))[0]
    if not len(ok):
        return None
    j = int(ok.max())
    return dict(margin=float(d.margin.values[o][j]), n=int(k[j]), share=round(float(k[j]) / len(d), 4), precision=round(float(c[j] / k[j]), 4))


cal = R[R.testlike] if int(R.testlike.sum()) >= 300 else R
TH = dict(swap=threshold(cal, 0.90, 30), insert=threshold(cal, 0.50, 50))
REPORT = dict(all=summary(R), testlike=summary(R[R.testlike]), other=summary(R[~R.testlike]),
              calibration_set='testlike' if cal is not R else 'all', thresholds=TH, stats=stats, seconds=round(time.time() - T0))
print(json.dumps(REPORT, indent=1))