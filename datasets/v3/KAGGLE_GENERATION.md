# Generate the first 50,000 candidates on Kaggle

Open `notebooks/Citrus-Generate-50k.ipynb` in Kaggle. Select a CUDA GPU and enable Internet before the first run. The notebook downloads the generator from an immutable repository revision and loads Qwen2.5-7B-Instruct in 4-bit mode. No paid model API or credential is used. Downloading dependencies and the model requires network access.

Target: 15,000 rewritten educational knowledge pairs and 35,000 practical pairs. The generated run is separate from the 120 authored v3 candidates; it does not silently include or overwrite them. No generation has been started from this repository commit.

The generator uses original prompts and concise educational rationale rather than pasted documentation. It preserves a SQLite checkpoint after each accepted record and exports JSONL periodically. If generation is interrupted, export again with `--export-only`. Save the progress archive as notebook output, attach it to the next session, and set RESUME_DB in the notebook. Do not depend on a temporary notebook session surviving.

It stops at the target, the session time budget, or repeated invalid/duplicate output. Invalid JSON, empty/short answers, unbalanced code fences, exact repeated questions and exact repeated answers are rejected. These checks do not prove factual accuracy or semantic diversity. The supplied generation topics and factual constraints are limited; a model can hallucinate or repeatedly paraphrase a topic. Review all candidates and perform semantic deduplication before training. Increase source grounding and topic diversity based on reviewed batches instead of trusting the final count.

Generation produces drafts only. `review_status` remains `draft`, `runtime_verified` remains false, and `approved_total` remains zero. Neither the generator nor its test assigns factual approval. Roblox-dependent code requires actual Roblox tests; pure Luau examples need appropriate execution tests. Do not claim an adapter was trained by this notebook.

Verified here: JSON parsing, normalized exact duplicate rejection, quota allocation, SQLite resume, draft export, and completion reporting using a mocked batch. Not verified here: CUDA model loading, Kaggle package compatibility, actual generation quality, runtime performance, Roblox execution, or a completed 50,000-record run. There is no active background job.

References:
- https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
- https://huggingface.co/docs/transformers/quantization/bitsandbytes

CLI alternative after installing dependencies:

```bash
python3 scripts/generate_citrus_kaggle.py --out /kaggle/working/citrus-50k
python3 scripts/generate_citrus_kaggle.py --out /kaggle/working/citrus-50k --export-only
python3 scripts/audit_citrus_v3.py --root /kaggle/working/citrus-50k
```

Output: `progress.sqlite`, `manifest.json`, `candidates/kaggle_generated.jsonl`. The notebook also saves `Citrus-50k-progress.zip`. Automatic GitHub uploading is intentionally absent; no GitHub write token is embedded in the notebook.
