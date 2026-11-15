'''## 7. ICEBERG + GLACIER spectrum simulators

Both models predict each candidate's spectrum and compare it with the measured one. Candidates with the same molecular formula are then re-ranked by

$$z(\\text{score}) + 1.0\\,z(\\text{ICEBERG}) + 1.0\\,z(\\text{GLACIER})$$

Most wrong answers share the right answer's formula, so this is where isomers get separated.

- Second-engine candidates join the simulator input, so they are scored too.
- **GLACIER uses [M+H]+ spectra only.** Restricting it this way added +0.006 on the leaderboard.
'''
