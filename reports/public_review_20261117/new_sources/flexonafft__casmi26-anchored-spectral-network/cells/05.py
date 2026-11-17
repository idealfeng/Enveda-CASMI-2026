# FPNet fold 0 logits for every training molecule (GPU), exactly as the overlay computes them on the test spectra.
Z = IR.fpnet_z(P, SPECTRA)
print(f'FPNet logits for {len(Z):,} molecules, {time.time() - T0:.0f} s')