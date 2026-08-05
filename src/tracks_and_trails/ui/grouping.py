"""Flattening a list into headers and the rows under them, for both tabs (`T-145`, `UX-005` §3).

## Why this is shared, and what is deliberately not

`T-140` built playlist grouping for the queue: a `_Group`, a flattening pass, an expansion set and
the line-number map three of them need. `T-145` gives History the same anatomy — `UX-005` §3 exists
to keep the two tabs reading as one shape — and copying a hundred lines across is how the two tabs
start to drift in exactly the way that decision forbids.

**What is shared is the flattening and the expansion. The data is not, and could not be.** The
queue groups `Job`s by status and draws a bar of their states; History groups records that are all
finished by definition. So this module knows how to turn *a list plus a membership function* into
headers and rows, and knows nothing about either row type — `Group` is generic, and every question
about what a header *says* stays with the model that owns it (`QueueModel._group_data` and
`HistoryModel._group_data` answer different roles from the same shape).

## The rules the two tabs must not disagree about

These are `T140-R4`'s, and they are here rather than in either model because a second copy is a
second chance to get one of them wrong:

1. **A header takes the position of its first member**, so a list the user ordered keeps reading
   the way they left it.
2. **Members follow their header together**, whatever their own positions are. Letting each member
   sit at its own position let an unrelated row land between a header and its children, which draws
   a row as belonging to a playlist it has nothing to do with.
3. **A group of one is dissolved.** A heading over a single row is a heading over nothing.
4. **A closed group's members are absent from the visible list entirely** — not hidden rows, no
   rows. The delegate never sees them.
"""

from collections.abc import Callable, Container, Sequence
from typing import Any

__all__ = ["Group", "Visible", "flatten"]


class Group[T]:
    """A header and the items gathered under it.

    **Synthesised per rebuild, never stored** (`T-137`, `T-145`). A group has no state of its own:
    its chip is a count of its members and, in the queue, its bar is their states — so there is
    nothing to keep in sync and nothing to go stale. That is also why neither tab has a `playlists`
    table, and why History carries membership on the record rather than in one.

    `members` and `indices` are parallel: `indices[n]` is where `members[n]` sits in the list this
    group was built from, which is what lets the flattened view name a row without the model
    searching for it again.
    """

    __slots__ = ("group_id", "indices", "members", "title")

    def __init__(self, group_id: str, title: str) -> None:
        self.group_id = group_id
        self.title = title
        self.members: list[T] = []
        self.indices: list[int] = []


#: One line of a flattened list: a header, or the index of an item in the list it was built from.
#:
#: **The tree is flattened rather than either view becoming a `QTreeView`** (`T-140`). A tree view
#: would replace the list, the delegate and the geometry `T118-R7`, `T118-R8`, `T118-R12` and
#: `T118-R15` were each spent on. A flat list of these keeps every one of them, and the delegate's
#: `DEPTH_ROLE` is the only thing that has to know nesting exists.
type Visible[T] = Group[T] | int


def flatten[T](
    items: Sequence[T],
    *,
    membership: Callable[[T], tuple[str, str] | None],
    identity: Callable[[T], str],
    expanded: Container[str],
    order: Callable[[T], Any] | None = None,
) -> tuple[list[Visible[T]], dict[str, int]]:
    """Turn `items` into headers and rows, plus a map from id to the line it is drawn on.

    `membership` answers `(group_id, title)` for an item that belongs to a group and `None` for one
    that does not — which is where each tab's own idea of a group lives. `identity` names an item
    for the returned map. `expanded` holds the ids of the groups that are open.

    `order` sorts the members **within** a group when the list's own order is not the order they
    should be read in. History needs it: records arrive newest-completed-first, while a playlist's
    entries belong in the playlist's own order, so track 03 stays above track 04 however the
    downloads interleaved. The queue passes nothing, because its list is already in queue order and
    that is what the user arranged.

    The returned map is keyed by group id *and* item id together. They cannot collide in practice —
    both are uuid4 — and a caller that looks up an id it was given by this module gets the line it
    was drawn on whichever kind it is.
    """
    groups: dict[str, Group[T]] = {}
    for position, item in enumerate(items):
        named = membership(item)
        if named is None:
            continue
        group_id, title = named
        group = groups.get(group_id)
        if group is None:
            group = Group[T](group_id, title)
            groups[group_id] = group
        group.members.append(item)
        group.indices.append(position)

    # Rule 3: a group of one is a heading over nothing, so it is not a group.
    grouped = {group_id: group for group_id, group in groups.items() if len(group.members) > 1}

    if order is not None:
        for group in grouped.values():
            together = sorted(
                zip(group.members, group.indices, strict=True), key=lambda p: order(p[0])
            )
            group.members = [member for member, _ in together]
            group.indices = [index for _, index in together]

    visible: list[Visible[T]] = []
    emitted: set[str] = set()
    for position, item in enumerate(items):
        named = membership(item)
        group = grouped.get(named[0]) if named is not None else None
        if group is None:
            visible.append(position)
            continue
        if group.group_id in emitted:
            # Rule 2: already drawn, with its siblings, where its header sits.
            continue
        emitted.add(group.group_id)
        # Rule 1: the header takes the position of its first member.
        visible.append(group)
        if group.group_id in expanded:
            visible.extend(group.indices)

    lines: dict[str, int] = {}
    for line, entry in enumerate(visible):
        lines[entry.group_id if isinstance(entry, Group) else identity(items[entry])] = line
    return visible, lines
