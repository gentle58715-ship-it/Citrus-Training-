# Citrus v4 — 60,000 target, 20% synthesized knowledge

**Current deliverable: a 100-record authored pilot, not a completed 60,000-record dataset.**
The pilot has 20 original explanatory/synthesis records and 80 practical records.
All 100 have a recorded Codex author/editor review; this is not independent human
review or evidence of a successful model-training run.
It spans all fourteen categories. Thirty practical records contain actual results
from 84 calls to the isolated Citrus draft engine. Five pure-Luau examples have
executable assertions. Roblox Studio has not been run.

The current authoritative target is `config.json`: 12,000 synthesized knowledge
examples and 48,000 practical examples, 60,000 total including evaluation splits.
Older v2/v3 data is separate. The v3 Kaggle output had demonstrated API errors and
has not been silently imported, approved or expanded.

## Content and evidence

- `candidates/authored_0001.jsonl`: 70 individually authored records; no template multiplication.
- `candidates/tool_replay_0001.jsonl`: 30 distinct executed draft-tool scenarios.
- `tool_schemas.json`: provider schemas captured from the existing Citrus interface.
- `sources.json`: source registry and short original factual anchors, not raw documentation.
- `reports/`: reproducible audit, tool execution and pure-Luau results.
- `reviews.json`, when present: substantive per-record decisions tied to content hashes.
- `pilot_exports/`, when present: explicitly partial exports; never the 60k release.

Each canonical record includes `id`, `family_id`, `kind`, `category`, `subtype`,
`mode`, `messages`, `tools`, `sources`, provenance, review status and scoped evidence.
Tool arguments are objects in the canonical Hugging Face-style representation.
Tool results are JSON strings in `role: tool` messages with matching call IDs.
Use the chosen training model's own chat template; the target training model is
not fixed by this dataset package.

`runtime_verified=true` is always qualified by its evidence. Pure Luau WASM
assertions are not Roblox tests, and neither are isolated TypeScript tool runs.
The captured `check_project` implementation explicitly does not validate Luau
syntax or execute a Studio game. Negative fixtures deliberately demonstrate
that boundary. Never remove that context when using them for training.

## Validation and export

From the repository root, using Python 3.10+:

```bash
python scripts/citrus_v4.py audit --report datasets/v4/reports/audit.json
python -m unittest discover -s tests -v
python scripts/citrus_v4.py export --out datasets/v4/release
```

The final export command **fails until the reviewed corpus meets all 60,000
category/kind targets**. This is intentional. An explicitly partial pilot export
uses `--allow-partial` and records `complete: false` in its manifest.
Approval requires a matching content hash, reviewer identity, factual/diversity/
source-rights checks and substantive notes. The generator never approves itself.

Splits hash a shared task family, approximately 80% train / 10% validation /
10% test. Closely related pilot cases are merged through `family_aliases` so a
renamed or related fixture does not cross splits. `membership.json` records the
actual assignments. Exact split sizes are not guaranteed. Automated numeric
variant screening is not a substitute for semantic review.

## Generate additional candidates

`notebooks/Citrus-Generate-60k-v4.ipynb` is the prepared GPU entry point. It uses
the repository generator with source anchors, SQLite checkpoints, per-category
quotas, duplicate rejection and concrete bad-API checks. A run creates **draft
candidates**, not automatically verified examples. The first run is bounded to
200 new drafts so its actual output can be examined before scaling. Changing a
limit is not evidence that the target was reached.

```bash
python scripts/citrus_v4.py generate \
  --out /kaggle/working/citrus-v4-progress \
  --model Qwen/Qwen2.5-7B-Instruct --limit 200 --minutes 60
```

This model is a candidate-generation default inherited from the earlier setup,
not the chosen Citrus training model. Its earlier output contained factual
errors; grounding and validation still require output review. The generator's
text-only path does not fabricate tool results. Additional tool-call training
must use actual isolated executor traces. Final model quality is unmeasured.

No generation job or background automation was started from this workspace:
the generation preflight found no configured Torch/CUDA runtime. Free GPU quota,
network/model access and execution permission must be available on the selected
runner. No paid inference service has been called.

## Reproduce execution checks

`scripts/replay_citrus_v4.mjs` accepts an absolute path to an ESM bundle exporting
`DraftTools` and `toolDefinitions` from the inspected application revision
`0be3ed7c32d181512a50b90579efe2f217f01cdd`, with Zod 3.25.76. It runs only isolated
in-memory project fixtures. The application's private source is not redistributed.

`scripts/verify_citrus_luau.mjs` accepts the installed `luau-web` 1.5.0 entry path.
It runs each authored pure-Luau example in a separate process with a timeout.
It is not a static type checker or a Roblox emulator.

## Rights and remaining work

The questions, explanations and small test code are newly authored. Referenced
documentation is not pasted into the dataset. Source URLs are attribution and
verification aids, not blanket license grants. No external asset binaries or
personal data are included. This change does not assign a new repository-wide
distribution license.

Remaining: configured generation runtime; much broader reviewed task coverage;
59,900 additional acceptable examples;
continued semantic deduplication; appropriate Roblox verification for future
engine-dependent code; final category quotas; model compatibility and training
evaluation. None of those are claimed complete by this pilot.
