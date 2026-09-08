"""Verify the retained 2026-09-08 review migration against its original Git blob.

Run from any directory. Future rounds may be appended outside the migration
markers; the original captured entries and manifest remain historical evidence.
"""

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


def verify(project: Path, manifest_path: Path, repository: Path) -> tuple[int, int, int]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    revision = manifest["source_revision"]
    assert re.fullmatch(r"[0-9a-f]{40}", revision), "invalid source revision"
    assert manifest["source_path"] == "docs/project/REVIEWS.md"
    source = subprocess.run(
        ["git", "show", f"{revision}:{manifest['source_path']}"],
        cwd=repository,
        check=True,
        capture_output=True,
    ).stdout
    assert hashlib.sha256(source).hexdigest() == manifest["source_sha256"]
    body_start = source.index(b"## Reviews\n") + len(b"## Reviews\n")
    assert body_start == manifest["body_start"]
    assert len(source) - body_start == manifest["body_bytes"]
    assert hashlib.sha256(source[body_start:]).hexdigest() == manifest["body_sha256"]

    entries = manifest["records"]
    assert len(entries) == manifest["record_count"]
    assert [entry["id"] for entry in entries] == list(range(1, len(entries) + 1))
    assert len({entry["path"] for entry in entries}) == manifest["file_count"]
    files = {}
    found_starts: Counter[int] = Counter()
    found_ends: Counter[int] = Counter()
    for path in sorted((project / "reviews").glob("*.md")):
        raw = path.read_bytes()
        files[path.relative_to(project).as_posix()] = raw
        found_starts.update(
            int(value)
            for value in re.findall(rb"^<!-- review-migration:(\d+):start -->$", raw, re.M)
        )
        found_ends.update(
            int(value) for value in re.findall(rb"^<!-- review-migration:(\d+):end -->$", raw, re.M)
        )
    expected = Counter(entry["id"] for entry in entries)
    assert found_starts == expected, "missing or duplicated record start"
    assert found_ends == expected, "missing or duplicated record end"

    previous_end = body_start
    reconstructed = []
    positions: dict[str, list[int]] = {}
    for entry in entries:
        number, name = entry["id"], entry["path"]
        assert name.startswith("reviews/") and Path(name).suffix == ".md"
        assert (project / name).resolve().is_relative_to(project.resolve())
        raw = files[name]
        opening = f"<!-- review-migration:{number:04d}:start -->\n".encode()
        closing = f"\n<!-- review-migration:{number:04d}:end -->".encode()
        assert raw.count(opening) == raw.count(closing) == 1
        position = raw.index(opening)
        start = position + len(opening)
        end = raw.index(closing, start)
        payload = raw[start:end]
        assert entry["source_start"] == previous_end, "source gap or overlap"
        assert payload == source[entry["source_start"] : entry["source_end"]], number
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"], number
        assert payload.count(("## " + entry["heading"] + "\n").encode()) == 1
        assert sum(content.count(payload) for content in files.values()) == 1, (
            "duplicated historical payload"
        )
        previous_end = entry["source_end"]
        reconstructed.append(payload)
        positions.setdefault(name, []).append(position)
    assert previous_end == len(source), "unmapped source suffix"
    assert all(values == sorted(values) for values in positions.values()), "round order changed"
    assert b"".join(reconstructed) == source[body_start:]
    return len(entries), manifest["file_count"], len(source) - body_start


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--repository", type=Path)
    args = parser.parse_args()
    project = args.project or Path(__file__).resolve().parents[1]
    repository = args.repository or project.parents[1]
    manifest = args.manifest or project / "evidence/2026-09-08-review-migration.json"
    count, files, size = verify(project, manifest, repository)
    print(
        f"PASS: {count} original entries in {files} files; all {size:,} historical bytes preserved"
    )


if __name__ == "__main__":
    main()
