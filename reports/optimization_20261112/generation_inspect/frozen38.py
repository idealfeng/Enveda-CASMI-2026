'''## 6. Main candidate lists + pool popularity re-rank

For each molecule, v4n scores candidates with FPNet fingerprints, its feature families and a 4-booster LightGBM ranker, and keeps the top 60. The list is then re-ranked by

$$z(\\text{ranker score}) + 0.15\\,\\big(\\log(1+\\#\\text{substances}) + \\log(1+\\#\\text{papers})\\big)$$

Only pool structures are re-ranked. Generated (novel) candidates keep their positions and form their own simulator groups. This step added +0.010 on the leaderboard.
'''
