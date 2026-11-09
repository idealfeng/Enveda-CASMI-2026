# New public scorer assets: availability and source audit

Checked 2026-11-06. Metadata and file lists were read anonymously from official Kaggle endpoints with TLS verification. Only two explicitly authorized bgunshui checkpoints were downloaded; no checkpoint was executed by this audit.

| Dataset | Public anonymous access | Current version / published update | Native files / bytes | Card licence |
| --- | --- | --- | --- | --- |
| [bgunshui/scorer-v2-model](https://www.kaggle.com/datasets/bgunshui/casmi26-scorer-v2-model) | HTTP200, isPrivate=false | V1 / 2026-11-02 | 4 / 11,875,242 | Unknown |
| [bgunshui/scorer-v4-model](https://www.kaggle.com/datasets/bgunshui/casmi26-scorer-v4-model) | HTTP200, isPrivate=false | V1 / 2026-11-02 | 4 / 16,915,853 | Unknown |
| [prvsiyan/self-trained-scorer-seeds](https://www.kaggle.com/datasets/prvsiyan/casmi26-self-trained-scorer-seeds) | HTTP200, isPrivate=false | V2 / 2026-11-04 | 12 / 23,762,196 | CC BY-NC-SA4.0 |

The metadata request treating `alexchilton/casmi26-scorer-train-v80` as a dataset returned anonymous403. This does not prove a private dataset exists; the reference may denote a training Notebook. No payload was fetched from it.

## Two bgunshui models

Both native packages contain only README.md, config_used.json, final_model.pt and training_result.json. The README's historical phrase "private scorer" does not describe current access: both are now anonymously public.

The packages require Saner v1's model.py/features.py/inference.py. The local complete inference bundles retain native config_used.json and add an exact config.json filename alias. The three code dependencies were copied from already downloaded `sanpier/casmi-spectrum-model-v1` V1; per-file receipts preserve this actual source rather than attributing the code to bgunshui.

| Property | v2 | v4 |
| --- | --- | --- |
| width / heads / layers / embedding | 192 / 6 / 3 / 192 | 256 / 8 / 3 / 256 |
| training maximum epochs | 80 | 120 |
| best epoch / completed holdout epochs / refit epochs | 52 / 56 / 52 | 109 / 120 / 109 |
| final checkpoint bytes | 11,872,818 | 16,913,586 |
| final checkpoint SHA256 | c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46 | 10565a0d8c2c1cc903882ff7ba2a9b7b994ae169228bf0c9b6c4ae055ff4ec51 |

The v4 config was corrected on November2 from width192 to256 according to its README. The shipped width256 / heads8 / embedding256 must be preserved; the earlier wrong config or public defaults can invalidate loading. Both configs specify the official competition train.parquet, external_paths=[], and refit_full=true. Both training_result.json files explicitly state full data refit including former validation identities. Their reported diagnostic MRR values are not clean heldout performance of final_model.pt.

The v2 README reports a public-plus-v2 z-score ensemble at0.480, and standalone replacement at0.460. The v4 README recommends public0.5 + v2 0.25 + v4 0.25. These are author statements, not this audit's verified competition submissions and not proof that a current consumer Notebook version scores0.481 or0.482.

Native licences remain Unknown. Saner code provenance does not confer a licence on the new trained weights. No blanket prize-eligibility conclusion is made.

## Self-trained seeds

The public V2 package has two seed folders, each with checkpoint, config, model.py, features.py and training_result.json, plus README and full SHA/bytes manifest. Small metadata/code files were downloaded, but its two checkpoints were not.

The card describes independent random-initialized training seeds20261103 and20261104 using the bgunshui public recipe. Full refit used57 and62 epochs and includes former holdout identities. Architecture is192/6/3/192. The stated measurements are0.479 for seed-pair submission57987166 and0.480 for an earlier credited two-scorer reproduction57922509; the author explicitly does not claim the seeds improve the score. Publication is explained as a replacement for the old bgunshui training Notebook input that could no longer be attached as ofNovember4.

## Downloaded local bundles

- `assets/kaggle/bgunshui/casmi26-scorer-v2-model/v1`
- `assets/kaggle/bgunshui/casmi26-scorer-v4-model/v1`

Each has8 payload files, per-file receipts and BUNDLE_MANIFEST.json. Checkpoints total28,786,404bytes; all package payloads total28,806,023bytes, below the authorized35MiB cap. Fresh full hashes matched16/16 payload receipts. Both new checkpoint hashes differ from the original public Saner checkpoint. This verifies download integrity, not strict model loading or scoring coverage.

See `minimal_model_download_report.json`, `integrity_summary.json`, dataset view/file-list snapshots and `small_file_receipts.json`. No signed URLs, credentials, Kaggle writes or model execution were recorded/performed by this audit.
