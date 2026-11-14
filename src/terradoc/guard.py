"""`terradoc guard`: compare a freshly built site with the release it replaces.

Validation (`terradoc check`) cannot see that a correct-looking table lost half
its rows, or that a reorganisation dropped a folder of images. The guard
compares two built sites (each with a `.release.json`) and blocks:

- a module shrinking by more than ``SHRINK_ROWS`` rows or ``SHRINK_SHARE`` of its
  records against the previous release (a module vanishing counts as 100 %);
- the same against an optional fixed *baseline* release with the looser
  ``BASELINE_SHARE``, so a site cannot erode a little at a time;
- more than ``max(LOST_FILES, LOST_SHARE * n)`` files present in the previous
  release disappearing.

All of these become warnings instead when the change is confirmed
(``--confirm-shrink``): deleting content on purpose is allowed, by accident not.
"""

from __future__ import annotations

import json
from pathlib import Path

from terradoc.checks import Issue

SHRINK_ROWS = 20
SHRINK_SHARE = 0.10
BASELINE_SHARE = 0.25
LOST_FILES = 10
LOST_SHARE = 0.05

CONFIRM_HINT = ("if this is intended, add a line `confirma-reducao` to the commit message "
                "(or tick 'confirm shrink' when running the workflow by hand)")


def _release(site: Path) -> dict:
    path = site / ".release.json"
    if not path.is_file():
        raise FileNotFoundError(f"{site} has no .release.json (not a terradoc >= 0.11 site)")
    return json.loads(path.read_text(encoding="utf-8"))


def _files(site: Path) -> set[str]:
    return {p.relative_to(site).as_posix() for p in site.rglob("*")
            if p.is_file() and p.name != ".release.json"}


def _shrink(old: dict[str, int], new: dict[str, int], *, share: float, rows: int | None,
            against: str, level: str) -> list[Issue]:
    issues = []
    for module, before in sorted(old.items()):
        after = new.get(module, 0)
        drop = before - after
        if drop <= 0 or before == 0:
            continue
        too_many = (rows is not None and drop > rows) or drop / before > share
        if too_many:
            issues.append(Issue(
                level, "guard",
                f"module '{module}' went from {before} to {after} records "
                f"(-{drop}, -{drop / before:.0%}) compared with {against}; {CONFIRM_HINT}"))
    return issues


def compare_releases(current: Path, previous: Path | None, baseline: Path | None = None,
                     *, confirm_shrink: bool = False) -> list[Issue]:
    level = "warning" if confirm_shrink else "error"
    issues: list[Issue] = []
    new = _release(current).get("modules", {})

    if previous is not None:
        old_release = _release(previous)
        if not old_release.get("modules"):
            issues.append(Issue("warning", "guard",
                                "previous release has no module counts; shrink check skipped"))
        else:
            issues += _shrink(old_release["modules"], new, share=SHRINK_SHARE, rows=SHRINK_ROWS,
                              against="the previous release", level=level)
        old_files, new_files = _files(previous), _files(current)
        lost = sorted(old_files - new_files)
        limit = max(LOST_FILES, int(LOST_SHARE * len(old_files)))
        if len(lost) > limit:
            shown = ", ".join(lost[:10]) + (" ..." if len(lost) > 10 else "")
            issues.append(Issue(level, "guard",
                                f"{len(lost)} files of the previous release are missing "
                                f"(limit {limit}): {shown}; {CONFIRM_HINT}"))

    if baseline is not None:
        base = _release(baseline).get("modules", {})
        issues += _shrink(base, new, share=BASELINE_SHARE, rows=None,
                          against="the baseline release", level=level)
    return issues
