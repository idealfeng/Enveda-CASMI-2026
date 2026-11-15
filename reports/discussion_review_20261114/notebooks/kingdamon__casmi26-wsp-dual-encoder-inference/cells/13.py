'''## 4. PubChem-only channel with a popularity prior

This channel searches about 105 million PubChem structures that are not in the main candidate pool. Its score combines the spectrum fit with how well documented a structure is.

$$\\text{score} = z(f\\cdot z) + 0.25\\,\\big(\\log(1+\\#\\text{PubChem substances}) + \\log(1+\\#\\text{PubMed papers})\\big)$$

The 200 most documented structures in the mass window are always added to the shortlist. A gate later decides how many PubChem candidates enter the final list. This prior added +0.004 on the leaderboard.
'''
