# Fixed public spectral-network exploration, 2026-11-13

**Release-ready as an explicitly speculative submission requested by the user.** This is not a validated improvement: the prior fixed-policy old48 panel result was approximately -0.00278 MRR@25. The coefficient and gating were not tuned in response.

Use only [revision2/branch_spec.json](../../submission/optimization_20261113/spectral_network_explore/revision2/branch_spec.json), target `stormseye/casmi26-spectral-network-1113`, branch `spectral_network_explore`. The preliminary parent-directory stage is superseded and unsubmitted; it is preserved because its post-overlay protection audit incorrectly compared the original AB hash with the already revised CSV. Revision 2 binds the immutable network control instead. The scoring policy is unchanged.

## Frozen implementation

The exact .488 parent's 33 cells remain unchanged, including dual neural, MASS, guarded trained heads and original AB matching. One appended cell runs public N1c after the audited AB output. It builds a target-to-target modified-cosine graph (same H+ or H- adduct, threshold .6, at least 6 matched peaks), then reranks the same candidate structures using neighbour candidate-fingerprint consensus at weight .25. No candidates, labels, models or data sources are added. Original library confidence >=.9 and accepted real AB matches protect the whole original list.

- Notebook SHA: `389b5341a38cf3825f09450e2a99e604655e3fb25beb474131364c6dd0b1ad00`.
- Recipe SHA: `f6bc296a0988f9b860e851d08e8540e060ac3cb7ffb8470b3b0c4a07c0a42e6b`.
- Runtime module SHA: `16f62e95a18608e66f95be0b5c279666cfd07f92d07c88c0a0d6a0153cf0018a`.
- Archived public source SHA: `8150955a1f0a617639253bd59cca9c186c6e881ebc7f15447682c0e3df7de768` ([source](https://www.kaggle.com/code/analyticaobscura/casmi-2026)).

The added module binds actual competition test IDs and path to the active CSV; official identities, candidate multisets, protected lists, original AB runtime, module/source/recipe pins and final CSV hash are checked. The audit independently reconstructs order from observed base/support score vectors and independently recomputes the protected set. Fast static skips all network work and retains the audited original CSV. Hidden mode actually invokes the frozen public function, including when the resulting graph is empty.

## Component evidence

[evidence_network_explore_smoke/verification.json](evidence_network_explore_smoke/verification.json) executes the actual appended frozen cell with both fast and hidden flags. It reuses the successful generation-production run's two real final lists and projects its spectra to the 12 official test columns; the projection contains no truth metadata. Both rows are protected; the actual graph has 0 edges and the CSV remains unchanged. A deliberately wrong output hash is rejected with CSV removal. Positive outputs and explicitly named tampered evidence are both retained. This is a component check, not a new full .488 or hidden-test rerun.

[evidence_network_delta/verification.json](evidence_network_delta/verification.json) separately exercises the nonempty graph and ordering path on the already existing old48 real spectra and saved predictions. It observes 8 edges, changes 13 query lists, and changes 0 top1 predictions. Score reconstruction, official identity validity and exact candidate multisets pass. A constructed AB-hit fixture protects a row that otherwise changes. That fixture is explicitly an interface test; it is not an actual .488 AB result. No labels or new metrics are read, and no parameters are selected from the outcome.

Remaining limits: no new complete pipeline inference was run for this branch, no new model was trained, no exact .488 efficacy comparison exists, and the known old48 efficacy result is negative. Kaggle hidden scoring will decide whether this fixed new-information mechanism is useful on the active champion.

## Dispatcher preflight

The root's actual dispatcher check caught missing `target` and `version` fields in the initial static-review record. Those review metadata fields were corrected; its original record is preserved as `evidence_network_static_review_before_metadata_fix.json`. The frozen notebook, recipe, metadata and module hashes above did not change. The builder now emits both fields. The actual `kaggle_batch.load_manifest` and `local_preflight` functions subsequently pass against the revision2 spec; see [evidence_network_preflight.json](evidence_network_preflight.json). No cloud write was performed here.
