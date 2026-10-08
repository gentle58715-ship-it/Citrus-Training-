# Citrus dataset requirements accepted on 2026-10-08

- Citrus is a Roblox development agent for coding, building, UI, animation,
  project context, tool use, diagnosis and evidence-based verification.
- The requested release contains 60,000 substantive examples across fourteen
  categories, including 12,000 (20%) rewritten explanations/syntheses and 48,000
  (80%) practical examples. Raw document dumps do not satisfy the knowledge quota.
- Names/numeric changes alone do not create substantive task diversity.
- Plan mode never calls tools, including read tools, and never edits files.
- Agent mode acts within the current user's request and actual available schemas.
- Do not invent existing object names, unknown APIs, tool outputs or Studio tests.
- UI examples use Scale for responsive layout and appropriate layout/size constraints.
- Knowledge, code behavior, draft-tool results and Roblox runtime evidence are
  different forms of verification and must be labeled separately.
- Upload destination authorized by the user:
  `gentle58715-ship-it/Citrus-Training-`.
- A pilot/checkpoint is labeled as such. The final release requires the requested
  reviewed totals and quality checks; no target number is reported as actual output.
- The base model for Citrus training has not been selected. Canonical conversations
  remain model-neutral until a compatible tokenizer/chat template is chosen.
