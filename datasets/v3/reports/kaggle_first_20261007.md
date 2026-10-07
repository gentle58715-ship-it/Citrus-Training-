# First Kaggle generation quality gate

Verified 2026-10-07 19:48 UTC. Kernel: https://www.kaggle.com/code/rrachphl/citrus-dataset-generation-50k

Kernel status complete does not mean the 50,000-row target is complete. Downloaded JSONL and authoritative SQLite agree: 429 unique candidate IDs, 129 knowledge and 300 practice. SQLite integrity_check: ok. Approved: 0. Existing authored 120 candidates remain separate; no combined deduplicated total is asserted.

Expansion PAUSED. Do not train on this output without repair and review. Concrete sampled failures:

- citrus-kaggle-012c40d232453ac93f419e96 calls Player:SetData and Player:SetState without any custom implementation; these are not Roblox Player methods. ClaimReward is undefined and there are no actual test assertions.
- citrus-kaggle-b4127b5b63189a74f19f4912 calls game:GetService('RemoteFunction'), treating an Instance class as a service, and Player:GetData without a custom implementation.
- citrus-kaggle-01e59fe356663695c79f12ec assumes an undefined R6LegPart type and resets Part0/Part1 world CFrames to identity as an axis correction. This is not a valid Motor6D animation correction.

These examples demonstrate that schema validation and exact deduplication do not establish factual or executable quality. All output stays draft and runtime_verified=false. No further GPU run was launched. Automatic expansion disabled pending correction of generation and validation.

Authoritative checkpoint and JSONL preserved in completed Kaggle output and backup: https://backend.composio.dev/api/v3/sl/mBFZklU7S7

The 300,000 target remains unfulfilled. Generated output is quarantined, not included in reviewed training exports.
