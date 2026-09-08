# T-300 — Documentation adoption verification

**Date:** 2026-09-08
**Performed by:** Codex (Documentation Maintainer for this implementation)
**Base:** `f465688`
**Head:** The implementation commit containing this artifact.
**Scope:** Documentation organization and navigation; no application behavior change.
**Review status:** Independent review pending. These are implementation checks.

## Changes and preservation boundary

Adopt DOC-007 while retaining numbered AGENTS sections, the accepted role mapping,
review policy, and all dated decision/review entries. Keep the single review file.
Move detailed procedures to DEVELOPMENT and templates to PROMPTS; archive closed
task detail and the old status snapshot without rewording the captured records.
Current navigation and metadata are editable; original findings remain historical.

T-299 remains In Review. Its privacy and captured-transcript corrections are
outside this adoption. The existing README CI wording and current review-policy
path are corrected here; finding resolution still belongs to the Reviewer.

## Checks and limits

- `ruff check .`: passed.
- Targeted task placement, capability guards and option-audit checks: **64 passed
  in 2.29 s** on the first documentation draft. The full suite also covers these.
- `source .venv/bin/activate` then `python -m pytest -q -n auto`: **3925 passed,
  21 skipped, 17 warnings in 169.95 s**, Linux, with local sockets available.
  The first sandboxed run returned **56 failed, 3869 passed, 21 skipped** in
  111.56 s; its output included blocked local socket creation and two failures
  from not activating the pinned toolchain. The successful run excluded no
  additional tests and used unchanged application/test sources.
- Preservation/link instrument below: passed. **2,395,298 bytes** of dated review
  records and **346,612 bytes** of previous decisions are unchanged. All **297**
  task IDs/headings remain, **268** archived closed records are verbatim, all
  **13** numbered AGENTS sections retain their subjects, **59** decisions are
  indexed, and **394** new local link destinations resolve. T-299 and the
  test-consumed T-260 entry are unchanged.
- `git diff --check` and the commit-message checker: passed.
- No Windows runtime, real-display session, release gate, repository-settings
  inspection, publication or push was performed.

## Reproduce the preservation check

Run from the repository root against this revision. The script compares the
current checkout with the recorded base; after further documentation edits,
check out this implementation commit to reproduce the same boundary. It checks
literal record preservation, task routes, numbered sections, newly introduced
Markdown links and the absence of application/configuration changes. It does not
prove that all inherited prose is accurate or replace independent review.

Save the Python block below to a temporary file and run `.venv/bin/python` on it.
It reads repository data and Git history; it does not modify either.

```python
"""Run from the repository root; compares current docs with the adoption base."""
from pathlib import Path
from collections import Counter
from functools import cache
from urllib.parse import unquote, urlsplit
import hashlib
import re
import subprocess

BASE = 'f465688'
ROOT = Path.cwd()

def before(path):
    return subprocess.check_output(['git', 'show', f'{BASE}:{path}'], stderr=subprocess.DEVNULL).decode()

def current(path):
    return (ROOT/path).read_text()

def suffix(text, marker):
    return text[text.index(marker):]

def section(text, start, end):
    return text[text.index(start):text.index(end,text.index(start))]

review_path = 'docs/project/REVIEWS.md'
review_bytes = suffix(before(review_path), '## Reviews\n').encode()
assert suffix(current(review_path), '## Reviews\n').encode() == review_bytes
print('All dated reviews preserved:', len(review_bytes), 'bytes;', hashlib.sha256(review_bytes).hexdigest())
decision_path = 'docs/project/DECISIONS.md'
decision_bytes = suffix(before(decision_path), '## DOC-001 —').encode()
assert suffix(current(decision_path), '## DOC-001 —').encode().startswith(decision_bytes)
print('All prior decisions preserved:', len(decision_bytes), 'bytes;', hashlib.sha256(decision_bytes).hexdigest())
index=section(current(decision_path),'## Effective-decision index','## Dated decision records')
rows={m[1]:m[0] for m in re.finditer(r'^\| \[([A-Z]+-\d+)\].*$',index,re.M)}
ids=re.findall(r'^## ([A-Z]+-\d+) —',current(decision_path),re.M)
assert set(rows)==set(ids)
assert '| Withdrawn |' in rows['DAT-004']
assert '| Withdrawn; purge ruling accepted |' in rows['DAT-006']
assert '#amended-2026-07-30--the-boundary-is-provenance' in rows['DAT-003']
assert '#amended-2026-08-10--cookie-files-land' in rows['DAT-003']
assert '#arc-007-amended-2026-07-30' in rows['ARC-007']
assert '#arc-007-amended-2026-07-30' not in rows['ARC-006']
print(len(ids),'decisions indexed; withdrawals and cross-section ARC-007 amendment routed explicitly')
assert current('docs/project/archive/STATUS-2026-09-08.md').endswith(before('docs/project/STATUS.md') + '---\n')
print('Full prior status snapshot preserved verbatim')

def task_blocks(text):
    marks = list(re.finditer(r'^## .+$|^### T-\d+ — .+$', text, re.M))
    blocks = {}
    for i,m in enumerate(marks):
        if not m[0].startswith('### '):
            continue
        end = marks[i+1].start() if i+1 < len(marks) else len(text)
        task = re.match(r'### (T-\d+)',m[0])[1]
        assert task not in blocks, task
        blocks[task] = text[m.start():end]
    return blocks

tasks_path='docs/project/TASKS.md'
prior_tasks=task_blocks(before(tasks_path))
live_tasks=task_blocks(current(tasks_path))
archive=current('docs/project/archive/TASKS-completed-2026-09-08.md')
assert prior_tasks.keys()==live_tasks.keys()
archived=0
for task,block in prior_tasks.items():
    assert live_tasks[task].splitlines()[0] == block.splitlines()[0], task
    if task=='T-300':
        assert block in archive
        continue
    if live_tasks[task].rstrip() == block.rstrip():
        continue
    assert archive.count(block) == 1, task
    assert 'Archived scope and completion evidence' in live_tasks[task], task
    old_status=re.search(r'^\*\*Status:\*\*.*$',block,re.M)[0]
    assert old_status in live_tasks[task], task
    archived += 1
assert archived==268
assert live_tasks['T-299']==prior_tasks['T-299']
assert live_tasks['T-260']==prior_tasks['T-260']
print(len(prior_tasks),'task IDs/headings retained;',archived,'closed records preserved verbatim; T-299/T-260 unchanged')

agents_before=before('AGENTS.md')
agents_after=current('AGENTS.md')
headings=lambda t:re.findall(r'^## (\d+\. .+)$',t,re.M)
assert headings(agents_before)==headings(agents_after)
old_roles=section(agents_before,'## 3. Roles','## 4. File ownership').rstrip()
assert old_roles in agents_after
policy=section(agents_before,'## 10. Review convergence','## 11. End-of-task report')
policy=policy.replace('## 10. Review convergence','## 14. Review policy').replace("§5's safety exception","AGENTS.md §5's safety exception")
assert policy.rstrip() in current('docs/project/TESTING.md')
print('All 13 numbered AGENTS sections retained; accepted tool/role mapping and review policy preserved')

# Fence-aware Markdown inspection. Existing historical links are not rewritten;
# check only newly introduced link destinations. Heading slugs follow the simple
# GFM headings used here; explicit IDs are included and duplicates reported.
def visible(text):
    fence=None
    for line in text.splitlines():
        m=re.match(r'^\s*(`{3,}|~{3,})',line)
        if fence:
            if m and m[1][0]==fence[0] and len(m[1])>=len(fence):
                fence=None
            continue
        if m:
            fence=m[1]
            continue
        yield line

def anchors(text):
    found=[]; seen=Counter()
    for line in visible(text):
        found.extend(re.findall(r'^<a id="([^"]+)"></a>$',line))
        m=re.match(r'^#{1,6} (.+)$',line)
        if m:
            title=m[1].strip()
            anchor=re.sub(r'[^\w\- ]','',title.lower()).replace(' ','-')
            number=seen[anchor]; seen[anchor]+=1
            found.append(anchor+(f'-{number}' if number else ''))
    return found

@cache
def target_anchors(path):
    return anchors(path.read_text())

def links(text):
    found=[]
    for line in visible(text):
        line=re.sub(r'(`+).*?\1','',line)
        for m in re.finditer(r'\[[^\]\n]+\]\((<[^>]+>|[^\s)]+)\)',line):
            found.append(m[1].strip('<>'))
    return Counter(found)

files=subprocess.check_output(['git','diff','--name-only',BASE],text=True).splitlines()
files += subprocess.check_output(['git','ls-files','--others','--exclude-standard'],text=True).splitlines()
checked=0
for path in dict.fromkeys(files):
    if not path.endswith('.md'):
        continue
    text=current(path)
    try:
        old_text=before(path)
    except subprocess.CalledProcessError:
        # New archives preserve the old contents with their original path context;
        # check only their deliberately added navigation, not historical references.
        old_text=''
        if path.endswith('/STATUS-2026-09-08.md'):
            old_text=before('docs/project/STATUS.md')
        elif path.endswith('/TASKS-completed-2026-09-08.md'):
            old_text=before('docs/project/TASKS.md')
    new_links=links(text)-links(old_text)
    for dest in new_links:
        url=urlsplit(unquote(dest))
        if url.scheme or url.netloc:
            continue
        target=(ROOT/path).parent/url.path if url.path else ROOT/path
        assert target.is_file(), (path,dest,'missing file')
        if url.fragment:
            assert url.fragment in target_anchors(target), (path,dest,'missing anchor')
        checked+=1
    # Do not reinterpret old duplicate headings in dated history as a new error.
    after_ids=Counter(anchors(text)); before_ids=Counter(anchors(old_text))
    for name,count in after_ids.items():
        assert count<=max(1,before_ids[name]), (path,name,'new duplicate anchor')
print(checked,'new local link destinations checked')

unchanged=['src','tests','tools','packaging','.github','pyproject.toml']
subprocess.run(['git','diff','--exit-code',BASE,'--',*unchanged],check=True)
print('Source, tests, tools, packaging, CI and dependency configuration unchanged')
```
