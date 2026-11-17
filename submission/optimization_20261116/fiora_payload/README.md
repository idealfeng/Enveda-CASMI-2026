# Private CASMI26 FIORA tims500 inference asset

This bundle is prepared for the owner's private Kaggle competition notebook. It contains only the exported step500 inference state, native FIORA source, pure-Python runtime dependencies, and two label-free official-training development queries for an offline startup smoke check. It contains no optimizer state, training scripts, competition test labels, or downloaded NIST model.

The parent FIORA-OS v1.0.0 release is the MSnLib v7-only model, native source commit e19ef82c9a6cb9dbac92bce23e914008f1aeb44e. Native FIORA source is MIT licensed; see source_checkout/LICENSE. Dependency license files are preserved inside dependencies/*.dist-info/. The MSnLib pretrained model's provenance must not be confused with the standard FIORA model trained using NIST.

The explicit timsTOF19 model was adapted by 500 actual optimizer updates on 400 official competition-training structures. A fixed 100-structure development group was excluded from these updates. Official competition data and derived query fixtures remain subject to the competition data license and rules; they are not relicensed as MIT by this bundle. Keep this Kaggle asset private. MSnLib pretraining exposure to development structures is unknown.

state.pt contains exactly 67 tensors (13,448,861 parameters), exported byte-value-equal to the trained parent checkpoint's model_state_dict; export provenance and all file hashes are in asset_manifest.json and the local export receipt. No cp312 shared-library dependencies are bundled. The target must supply compatible torch, RDKit, NumPy, SciPy and the normal scientific Python stack. Local isolated forward parity does not certify Kaggle hidden-run success or leaderboard improvement.
