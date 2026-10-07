# Citrus v3: 150,000 target

Status: IN PROGRESS. Actual authored candidates: 20 (6 knowledge, 14 practice). Approved training records: 0. No model training has started.

The target is 45,000 knowledge instruction/response examples and 105,000 practical task/response examples. Knowledge must be rewritten educational answers, never raw pasted documentation. The 15 categories in manifest.json allocate 3,000 knowledge and 7,000 practical tasks each. These allocations are an implementation plan, not completed counts.

## Records and review

Each record has id, family_id, kind, category, messages, sources, provenance, review_status, runtime_verified. Seed examples are authored drafts. Procedural design tasks are legitimate practical examples; code tasks need executable code where the prompt requests code. Tool examples must use the real tool schema before training concrete calls. Never fabricate successful tool output or Roblox testing. Source citations do not imply code execution or fact checking of every claim.

Approve only after checking factual correctness, relevance, meaningful task diversity, complete answer/code, source/license provenance, and semantic duplicates. Run code in an appropriate Luau/Roblox environment when applicable and record results separately. Do not mark runtime_verified for design-only examples. Match the actual rig and API version; R15 joint implementations may vary. Preserve user scope.

## Audit and export

From repository root:

```bash
python3 scripts/audit_citrus_v3.py
python3 scripts/audit_citrus_v3.py --export datasets/v3/exports
python3 scripts/audit_citrus_v3.py --require-complete
```

The audit checks structure and normalized exact duplicates, NOT factual correctness or semantic duplicates. Export includes approved records only. Split assignment hashes family_id to keep variants together (approximately 95% train / 5% eval). Related examples must receive the same family_id before export. The complete check rejects incomplete totals and category allocations. The current draft batch exports zero records by design.

## Remaining work

149,980 additional candidates, substantive review of all records, semantic deduplication, runtime validation where relevant, source/license review, approved dataset export, model compatibility selection, and actual model training. Existing v2 records have NOT been added automatically. This repository contains no active background generation job. Large-scale generation needs an available authorized generation runtime; no paid API was called for this batch.
