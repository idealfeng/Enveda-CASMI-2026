# Manifest batch code-submission helper

`scripts/kaggle_batch.py` is plan-only unless one explicit action is selected. This tool never uploads a local diagnostic CSV; formal submission always refers to the selected cloud Notebook V1 and its `submission.csv`.

## Manifest contract

```json
{
  "schema_version": 1,
  "batch_id": "20261107",
  "competition": "enveda-CASMI26-molecule-id-mass-spectra",
  "max_submissions": 4,
  "state_root": "reports/aggressive_batch_20261107",
  "branches": [
    {
      "name": "example",
      "target": "stormseye/casmi26-example-20261107",
      "version": 1,
      "stage_dir": "submission/aggressive_20261107/example",
      "notebook_sha256": "64 lowercase hex characters",
      "metadata_sha256": "64 lowercase hex characters",
      "description": "CASMI26 example recipe 20261107 V1",
      "validation_mode": "fast_static",
      "static_review_path": "submission/aggressive_20261107/example/static_review.json",
      "required_runtime_audits": [
        {
          "name": "batch_variant_audit.json",
          "required_true_checks": ["static_source", "recipe_config"],
          "expected_fields": {"mode": "fast_static", "branch": "example"}
        }
      ]
    }
  ]
}
```

There may be 1–5 uniquely named branches and a cap of 1–5 submissions. Each new target is a private, offline, GPU Notebook at V1. Stage metadata explicitly lists competition, datasets and any public kernel dependencies. The helper rejects unknown dependencies on server readback; metadata `model_sources` is currently unsupported. Numeric dataset/kernel versions requested in metadata are retained, but the API source binding only proves the observed source slugs. Runtime observers must verify exact model/asset content where required.

For `fast_static`, `static_review_path` must contain:

```json
{"status":"passed","target":"stormseye/casmi26-example-20261107","version":1,
 "notebook_sha256":"same frozen source SHA","checks":{"reviewed_recipe":true}}
```

Each required cloud JSON must have `status: "passed"`, a nonempty `checks` mapping whose values are all exactly `true`, every named required check, and exact expected top-level fields. A source-bound observer should record the branch, mode and recipe digest. Fast-static commits prove source/input/schema preparation only; they do not prove that visible model inference ran. Hidden rerun model/config/coverage checks must be enforced by the frozen Notebook itself.

## Commands

Use Windows Python with all cache/temp paths on D. Replace `MANIFEST` and `BRANCH` below.

```powershell
.venv\Scripts\python.exe scripts/kaggle_batch.py --manifest MANIFEST
.venv\Scripts\python.exe scripts/kaggle_batch.py --manifest MANIFEST --branch BRANCH --launch
.venv\Scripts\python.exe scripts/kaggle_batch.py --manifest MANIFEST --branch BRANCH --status
.venv\Scripts\python.exe scripts/kaggle_batch.py --manifest MANIFEST --branch BRANCH --reconcile-target stormseye/actual-title-derived-slug
.venv\Scripts\python.exe scripts/kaggle_batch.py --manifest MANIFEST --branch BRANCH --audit-outputs
.venv\Scripts\python.exe scripts/kaggle_batch.py --manifest MANIFEST --branch BRANCH --submit
.venv\Scripts\python.exe scripts/kaggle_batch.py --manifest MANIFEST --branch all --poll
```

`--status` and `--poll` accept `--branch all`. Mutating actions and output downloads require exactly one branch. This helper does not start background processes or automatically schedule another action.

## Evidence and failure handling

Each branch has `cloud.json`, `binding.json`, `outputs/`, `output_audit.json`, `submission.json` and `score.json` under its state directory. Before either external write, the corresponding receipt is created exclusively, flushed and fsynced. An existing receipt blocks any repeat write even after a timeout or ambiguous server response. The batch submit lock serializes quota checks and requests, and unknown submission outcomes count towards the batch cap.

Source comparison permits only `cell.source` list/string representation changes. Every other Notebook JSON field must match. Before submission the helper rereads server V1, checks COMPLETE with no failure, rehashes local artifacts, inventories all existing submissions, rejects duplicate descriptions or available exact source-version duplicates, and checks current `num_allowed_now`. Old unrelated submissions are allowed.

Downloads are read-only, paginated and bounded: CSV ≤4MiB, each JSON ≤2MiB, total ≤16MiB. Signed URLs are used in memory only. Output directories are immutable; a failed download preserves its partial evidence and requires explicit operator inspection before another download attempt. Official RDKit2026.03.3 validates the CSV, all 400 sample IDs and ordering, and 1–25 valid candidate identities. Duplicate identities are recorded because official scoring consumes their ranks; the helper never edits the CSV.

`--status` may reconcile a timed-out cloud request only after exact target/source/private/offline/dependency readback. `--poll` may reconcile an unknown submission only by a unique description/file match in the complete inventory, then polls its fixed positive ref. Neither path retries any write. Exception messages, credentials, headers and signed URLs are not persisted.

Kaggle may derive a new Notebook slug from its title despite the requested metadata ID. For a proved single create request, `--reconcile-target ACTUAL_REF` reads the explicit actual V1 and requires the same private/offline/GPU/source and dependency checks. Only after those pass does it add `actual_target` to the existing cloud receipt and mark the run requested. The logical manifest target, stage metadata and original claim fields remain unchanged. Every later status/output/submission call uses this verified actual target. An established actual target cannot be rebound, a wrong source is rejected, and an existing cloud claim still blocks another push. This path performs reads plus local receipt updates only.

## Verification

16 offline tests passed, covering durable one-write claims, unknown outcomes, source mutation, private/offline/dependency guards, named observer checks, current quota, batch cap, duplicate submissions, allowed historic refs, fixed-ref polling, bounded output artifacts, file tampering, explicitly allowed public kernel dependencies, and read-only recovery of a title-derived cloud slug. No actual network write or model execution was performed by the tool author.

## Read-only four-branch watcher

`scripts/watch_kaggle_batch_20261107.py` defaults to a local plan without networking. Explicit `--watch --max-hours 12` polls already accepted/reconciled positive refs every45 seconds, for at most12 hours. It never launches, downloads, submits or reconciles an unknown nonpositive ref. Missing submissions are `not_submitted`; ambiguous claims without a fixed accepted ref are `awaiting_submission_identity`.

The exclusive `watcher.lock` and `latest_status.json` live under the manifest state root. The summary records actual PID, logical/actual targets, fixed refs, finite scores, original0.479, batch best and overall best. Completed branches are cached; all four COMPLETE/ERROR stops the watcher. The manifest SHA is fixed at startup; changing that manifest stops monitoring rather than switching recipes. Root should start it after finishing the four recipe manifests. Two offline fixtures verified these boundaries. It was prepared only; the author did not start a background process.
