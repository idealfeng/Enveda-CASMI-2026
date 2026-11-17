# CODE CELL 48 · Deep EDA
# Four scenarios for future candidate-ranker evaluation.
protocol=pd.DataFrame([
 ['S0 · New spectrum','spectrum_id','Search against known reference spectra','Other spectra of the same structure may remain in the reference library'],
 ['S1 · New structure','inchikey14','Generalization to unseen structures','Close analogs or the same molecular scaffold may remain'],
 ['S2 · New library','ingest_lib','Transfer across data sources','Instrument mix and chemical composition may differ'],
 ['S3 · New scaffold','Bemis–Murcko scaffold','Structural novelty','Check for missing scaffolds and balance the groups'],
],columns=['Scenario','Grouped by','What this tests','What to watch for'])
display(protocol)
