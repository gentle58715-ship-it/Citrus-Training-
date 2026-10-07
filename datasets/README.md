# Citrus AI datasets

This folder contains Citrus-specific supervised fine-tuning data.

## Files

- `citrus_special_v1.jsonl` — custom conversational examples for Roblox/Luau, R6/R15 animation, GUI/UI, 3D/Mesh, debugging, and assistant behavior.

## Format

Each line is one JSON object:

```json
{"category":"animation","messages":[{"role":"system","content":"..."},{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

One example must stay on one physical line because this is JSONL.

## Recommended training mix

Do not train only on a raw code-completion corpus. Mix public Luau data with Citrus conversational data so the model keeps instruction/chat behavior.

Suggested starting mix:
- 70% public Roblox/Luau
- 15% Citrus conversational/behavior
- 10% animation + UI + 3D
- 5% tool-calling once the real Citrus tool schemas are finalized

For prompt-completion SFT, convert each row so `messages[:-1]` is the prompt and the final assistant message is the completion, then train with completion-only loss.

## Notes

- Keep tool-calling examples separate until tool names and JSON schemas are stable.
- Add new data in versioned files rather than repeatedly overwriting old training sets.
- Validate every JSONL line before training.
