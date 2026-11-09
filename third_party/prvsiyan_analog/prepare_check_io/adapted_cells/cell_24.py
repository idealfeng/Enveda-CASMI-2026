'''## 9. Two-engine fusion + final simulator re-rank

The two lists are combined by weighted reciprocal-rank fusion. A candidate's score is $\\frac{1}{3 + r_{\\text{main}}} + \\frac{0.6}{3 + r_{\\text{engine 2}}}$, and the top 40 are kept. ICEBERG and GLACIER then re-rank same-formula groups of the fused list one last time, and the top 25 become the submission.
'''
