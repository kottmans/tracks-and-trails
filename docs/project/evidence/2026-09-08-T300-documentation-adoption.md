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


## Status evidence relocation — 2026-09-08

**Base:** `d88e62e`; **head:** the follow-up commit containing this supplement.
**Authority:** The maintainer requested relocation of unique evidence and removal
of the status archive. Independent review remains pending.

### Retention and audit scope

The removed `docs/project/archive/STATUS-2026-09-08.md` contained 7,425 lines.
Its SHA-256 at `d88e62e` is
`e5e746d78559f78402a40db84c5d46c84b45e27ab2d8520a00d427299d4c814c`.
The [19 dated task supplements](../archive/TASKS-completed-2026-09-08.md#historical-evidence-supplements--2026-09-08)
retain 38 verbatim excerpts, linked from 38 relevant task entries. The original
2,193,195-byte task archive is an unchanged prefix; the supplements append 489 lines.

The comparison covered 1,292 source paragraphs and 299 other UTF-8 files from the
321-file tracked tree; 21 binary/non-UTF-8 files were excluded from text comparison.
Literal and numeric searches identified candidates; comparison with the relevant
task, review and decision records determined what needed retaining. The excerpts
keep adjacent context where necessary, rather than treating every unmatched word
or number as new evidence.

Retained material includes CI run identities and failures, the first Linux scan,
Windows process observations, timing estimates, failed mutations, test counts,
incomplete runs and the historical environment. Two new notes qualify errors in
the source: 30m39s is 76.625% of 40 minutes, and T-234's apparent test failure was
later identified as a worker segfault. Original quoted text remains unchanged.

Repeated implementation/review narratives already have their task and review
records. Current requirements and decisions retain their own authority. Superseded
queue snapshots, routine push-state updates, regenerable inventories, transient
handoff names and old personal/external routing do not need another live copy.
The complete original snapshot remains recoverable with the command in the
supplements. Historical CI was not re-queried or reclassified as current evidence.

DOC-007 has an appended retention amendment and an index link. STATUS, task
navigation and the setup guide point to retained evidence. No source, test,
dependency, workflow, external standard or review finding was changed.

### Checks and limits

- `ruff check .`: passed.
- `python -m pytest -q tests/unit/test_task_placement.py tests/unit/test_capability_guards.py tests/unit/test_option_audit.py`:
  **64 passed in 2.39 s**.
- Activated `.venv`, then `python -m pytest -q -n auto`, Linux with local sockets
  available: **3925 passed, 21 skipped, 17 warnings in 168.90 s**; exit 0.
- The instrument below verifies all 38 excerpts against the immutable source,
  all 297 task IDs/headings, unchanged pre-existing task bodies apart from T-300
  and navigation, preserved original archives/reviews/decisions/verification text,
  the removed snapshot and the added local link destinations.
- `git diff --check` and the commit-message checker: passed.
- No Windows runtime, real-display session, external CI verification or push.
  Existing task blockers and independent-review requirements are unchanged.

### Reproduce this retention check

The original instrument above describes `d88e62e` and still requires its full
snapshot. Run that instrument at that commit. Save the following block to a
temporary file and run it from the repository root at this follow-up commit to
check the new preservation boundary. It checks text and navigation; it does not
independently establish the truth of the historical measurements.

```python
from pathlib import Path
from urllib.parse import unquote
import hashlib
import re
import subprocess

BASE = 'd88e62e'
ARCHIVE = 'docs/project/archive/TASKS-completed-2026-09-08.md'
STATUS = 'docs/project/archive/STATUS-2026-09-08.md'
EVIDENCE = 'docs/project/evidence/2026-09-08-T300-documentation-adoption.md'

def before(path):
    return subprocess.check_output(['git', 'show', f'{BASE}:{path}'])

def current(path):
    return Path(path).read_bytes()

source = before(STATUS)
assert hashlib.sha256(source).hexdigest() == 'e5e746d78559f78402a40db84c5d46c84b45e27ab2d8520a00d427299d4c814c'
assert current(ARCHIVE).startswith(before(ARCHIVE))
assert current(EVIDENCE).startswith(before(EVIDENCE))
assert current('docs/project/REVIEWS.md') == before('docs/project/REVIEWS.md')
marker = b'## DOC-001 \xe2\x80\x94'
assert current('docs/project/DECISIONS.md').split(marker, 1)[1].startswith(
    before('docs/project/DECISIONS.md').split(marker, 1)[1])
print('Original task archive, review record, dated decisions and adoption evidence preserved.')

supplements = current(ARCHIVE)[len(before(ARCHIVE)):].decode()
excerpts = list(re.finditer(r'^\*\*Source lines (\d+)–(\d+):\*\*\n\n((?:>[^\n]*\n)+)', supplements, re.M))
assert len(excerpts) == 38
for match in excerpts:
    recovered = [line[2:] if line.startswith('> ') else '' for line in match[3].splitlines()]
    assert recovered == source.decode().splitlines()[int(match[1])-1:int(match[2])], match[0]
print(f'{len(excerpts)} excerpts match their exact source lines.')

tasks_before = before('docs/project/TASKS.md').decode()
tasks_after = current('docs/project/TASKS.md').decode()
ids = r'^### (T-\d+) —.*$'
assert re.findall(ids, tasks_before, re.M) == re.findall(ids, tasks_after, re.M)
without_navigation = re.sub(r'\n\nHistorical evidence relocated 2026-09-08:\n[^\n]+', '', tasks_after)
task300 = r'(?ms)^### T-300 —.*?(?=^### T-299 —)'
assert re.sub(task300, '', without_navigation) == re.sub(task300, '', tasks_before)
print(f'{len(re.findall(ids, tasks_after, re.M))} task IDs/headings preserved; other task bodies unchanged.')

allowed = {ARCHIVE, STATUS, EVIDENCE, 'docs/project/TASKS.md', 'docs/project/STATUS.md', 'docs/project/DECISIONS.md', 'docs/DEVELOPMENT.md'}
changed = subprocess.check_output(['git', 'diff', '--name-only', BASE]).decode().splitlines()
assert set(changed) <= allowed, changed
count = 0
for name in changed:
    path = Path(name)
    if not path.exists():
        continue
    # Only links added by this change; retained historical prose is not rewritten.
    diff = subprocess.check_output(['git', 'diff', '--unified=0', BASE, '--', name]).decode()
    added = '\n'.join(line[1:] for line in diff.splitlines() if line.startswith('+') and not line.startswith('+++'))
    for target in re.findall(r'(?<!!)\[[^\]\n]+\]\(([^)\s]+)\)', added):
        if '://' in target or target.startswith('mailto:'):
            continue
        destination, _, anchor = unquote(target).partition('#')
        dest = path.parent / destination if destination else path
        assert dest.exists(), (name, target)
        if anchor:
            text = dest.read_text()
            headings = re.findall(r'^#{1,6}\s+(.+)$', text, re.M)
            anchors = set(re.findall(r'<a\s+id="([^"]+)"', text))
            anchors.update(re.sub(r'[^\w\- ]', '', h.lower()).replace(' ', '-') for h in headings)
            assert anchor in anchors, (name, target)
        count += 1
print(f'{count} added local links resolve; changes confined to the seven authorized documentation paths.')
assert not Path(STATUS).exists()
print('Status archive removed; immutable source remains available in Git.')
```
