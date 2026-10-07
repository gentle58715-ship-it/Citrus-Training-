#!/usr/bin/env python3
"""Audit Citrus v3 candidates and export reviewed records only. Standard library."""
import argparse, collections, hashlib, json, pathlib, re, sys, unicodedata

def normalized(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip().casefold()

def audit(paths, manifest):
    rows, errors, ids, prompts, answers = [], [], set(), set(), set()
    categories = {c["name"] for c in manifest["categories"]}
    for path in paths:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip(): continue
            loc = f"{path}:{line_no}"
            try:
                row = json.loads(line)
                assert isinstance(row, dict), "record must be an object"
                assert row["kind"] in ("knowledge", "practice"), "unknown kind"
                assert row["category"] in categories, "unknown category"
                assert isinstance(row["id"], str) and row["id"], "missing id"
                assert isinstance(row["family_id"], str) and row["family_id"], "missing family_id"
                assert row["review_status"] in ("draft", "approved", "rejected"), "invalid review status"
                assert isinstance(row["runtime_verified"], bool), "invalid runtime verification"
                assert isinstance(row["sources"], list), "sources must be a list"
                assert all(isinstance(s, str) and s.startswith("https://") for s in row["sources"]), "invalid source URL"
                messages = row["messages"]
                assert len(messages) == 2, "expected user/assistant pair"
                assert [m["role"] for m in messages] == ["user", "assistant"], "invalid roles"
                assert all(isinstance(m["content"], str) and m["content"].strip() for m in messages), "empty content"
                prompt, answer = [normalized(m["content"]) for m in messages]
                assert row["id"] not in ids, "duplicate id"
                assert prompt not in prompts, "duplicate prompt"
                assert answer not in answers, "duplicate answer"
                ids.add(row["id"]); prompts.add(prompt); answers.add(answer)
                rows.append(row)
            except (KeyError, TypeError, ValueError, AssertionError) as exc:
                errors.append(f"{loc}: {exc}")
    counts = collections.Counter(r["kind"] for r in rows)
    approved = [r for r in rows if r["review_status"] == "approved"]
    report = {
        "actual_total": len(rows), "actual_counts": dict(counts),
        "approved_total": len(approved),
        "draft_total": sum(r["review_status"] == "draft" for r in rows),
        "target_total": manifest["target_total"],
        "remaining_to_approve": manifest["target_total"] - len(approved),
        "errors": errors,
        "checks": ["schema", "exact normalized duplicates", "review status"],
        "limitations": ["No semantic deduplication", "No Roblox execution", "No factual verification"],
    }
    return rows, report

def export(rows, directory):
    # Every task family stays in one split even if it has multiple variants.
    directory.mkdir(parents=True, exist_ok=True)
    buckets = {"train": [], "eval": []}
    for row in rows:
        if row["review_status"] != "approved": continue
        split = "eval" if int(hashlib.sha256(row["family_id"].encode()).hexdigest(), 16) % 20 == 0 else "train"
        buckets[split].append(row)
    for split, records in buckets.items():
        (directory / f"{split}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
            encoding="utf-8")
    return {k: len(v) for k, v in buckets.items()}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("datasets/v3"))
    parser.add_argument("--export", type=pathlib.Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((args.root / "manifest.json").read_text(encoding="utf-8"))
    rows, report = audit(sorted((args.root / "candidates").glob("*.jsonl")), manifest)
    if args.export and not report["errors"]:
        report["exported"] = export(rows, args.export)
    if args.require_complete:
        approved = [r for r in rows if r["review_status"] == "approved"]
        count = collections.Counter(r["kind"] for r in approved)
        category_count = collections.Counter((r["category"], r["kind"]) for r in approved)
        if len(approved) != manifest["target_total"] or any(
            count[k] != n for k, n in manifest["target_counts"].items()
        ):
            report["errors"].append("Approved records do not meet 150000 / 45000 / 105000 targets")
        for cat in manifest["categories"]:
            for kind in ("knowledge", "practice"):
                if category_count[(cat["name"], kind)] != cat[f"target_{kind}"]:
                    report["errors"].append(f"Target mismatch: {cat['name']}/{kind}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0

if __name__ == "__main__":
    sys.exit(main())
