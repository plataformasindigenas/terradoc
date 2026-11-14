#!/usr/bin/python3
"""sitepull: serve terradoc sites from the `refs/sites/*` refs that CI publishes.

Runs on the web server as the unprivileged user `sites`, every couple of
minutes (systemd timer), and as `sitectl` for the owner. Standard library only.

For every repository in the config it:

1. lists the remote with `git ls-remote` (anonymous HTTPS: the repos are public);
2. maps branches to targets: the default branch is `_prod`, every other branch
   the preview `sanitize(branch)` (the same rule as the CI workflow); two
   branches with the same name are both ignored;
3. for a target whose `refs/sites/<name>` changed, fetches that one commit into
   a bare cache and checks it: `.release.json` must name the current tip of the
   branch (stale or hand-pushed refs are not served), the tree must hold only
   regular files with safe paths, within size limits;
4. writes the release into `<root>/<slug>/<target>/releases/<id>/` (files that
   did not change are hardlinked from the previous release), switches the
   `current` symlink atomically, and smoke-tests a few URLs through Caddy. If
   that fails it switches back, and that ref is never retried.

State lives in `<root>/state/<slug>.json`: what is deployed, refs that failed,
and `hold` (set by `sitectl rollback`; the target is left alone until
`sitectl release`). A single lock covers every command.

The server never runs repository code and holds no credential.
"""

from __future__ import annotations

import argparse
import configparser
import fcntl
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CONFIG = Path(os.environ.get("SITEPULL_CONFIG", "/etc/sitepull/sites.ini"))
PROD = "_prod"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
RESERVED = {"cache", "state", "www"}

KEEP = {"prod": 10, "preview": 2}            # releases kept per target
MAX_FILES = 20_000
MAX_BYTES = {"prod": 2 << 30, "preview": 1 << 30}
MAX_PREVIEWS = 5                            # per repository; the oldest goes
DISK_LIMIT = 0.80                           # no new preview above this usage
PROD_RESERVE = 512 << 20                    # production needs this much free
GRACE_BRANCH_ONLY = 24 * 3600               # branch gone, ref still there
GRACE_BOTH = 10 * 60                        # branch and ref both gone
STALE = 15 * 60                             # heartbeat older than this: alarm
GC_EVERY = 7 * 24 * 3600
SMOKE_FILES = 5
LOCK_WAIT = 120


class Refused(Exception):
    """This ref must not be served, ever (it is recorded as failed)."""


class NotYet(Exception):
    """Not servable now, but may be later (not recorded as failed)."""


@dataclass
class Site:
    slug: str
    url: str
    default_branch: str


@dataclass
class Conf:
    root: Path
    smoke_base: str
    sites: list[Site]

    def site(self, slug: str) -> Site:
        for s in self.sites:
            if s.slug == slug:
                return s
        die(f"unknown site '{slug}' (known: {', '.join(s.slug for s in self.sites)})")


# ── small helpers ────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(msg, flush=True)


def die(msg: str, code: int = 2):
    print(f"sitepull: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp(after: str | None = None) -> str:
    """UTC time to the millisecond; sorts after `after` (release ids sort by age)."""
    while True:
        s = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%f")[:-3] + "Z"
        if after is None or s > after:
            return s
        time.sleep(0.002)


def sanitize(branch: str) -> str:
    """Branch → preview name, exactly as the CI workflow does it: lowercase
    (ASCII only), runs of anything outside [a-z0-9-] become '-', no leading
    '-', at most 40 characters, no trailing '-'."""
    s = "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in branch)
    s = re.sub(r"[^a-z0-9-]+", "-", s).lstrip("-")
    return s[:40].rstrip("-")


def write_json(path: Path, data) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def symlink_swap(link: Path, target: str) -> None:
    """Point `link` at `target` atomically (the equivalent of `ln -s` + `mv -T`)."""
    tmp = link.with_name(f".{link.name}.new")
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(target, tmp)
    os.replace(tmp, link)


def boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return "unknown"


def git(*args: str, cwd: Path | None = None, timeout: int = 120, check: bool = True):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1", LC_ALL="C")
    proc = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True,
                          timeout=timeout)
    if check and proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError(f"git {args[0]} failed: {err[-1] if err else proc.returncode}")
    return proc


# ── config, state, lock ──────────────────────────────────────────────────

def load_config(path: Path = CONFIG) -> Conf:
    cp = configparser.ConfigParser(interpolation=None)
    try:
        with open(path, encoding="utf-8") as f:
            cp.read_file(f)
    except FileNotFoundError:
        die(f"no config at {path}")
    d = cp.defaults()
    sites = []
    for slug in cp.sections():
        if not SLUG_RE.match(slug) or slug in RESERVED:
            die(f"config: invalid site name '{slug}'")
        sec = cp[slug]
        sites.append(Site(slug, sec["url"], sec.get("default_branch", "master")))
    return Conf(Path(d.get("root", "/srv/sites")), d.get("smoke_base", ""), sites)


class Lock:
    def __init__(self, root: Path, wait: bool):
        self.path, self.wait = root / ".lock", wait

    def __enter__(self):
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o644)
        deadline = time.monotonic() + (LOCK_WAIT if self.wait else 0)
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    os.close(self.fd)
                    raise
                time.sleep(1)

    def __exit__(self, *exc):
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)


def state_path(conf: Conf, slug: str) -> Path:
    return conf.root / "state" / f"{slug}.json"


def load_state(conf: Conf, slug: str) -> dict:
    st = read_json(state_path(conf, slug), {})
    st.setdefault("targets", {})
    return st


def save_state(conf: Conf, slug: str, st: dict) -> None:
    write_json(state_path(conf, slug), st)


def target_dir(conf: Conf, slug: str, name: str) -> Path:
    return conf.root / slug / name


def releases_of(tdir: Path) -> list[str]:
    rel = tdir / "releases"
    if not rel.is_dir():
        return []
    return sorted(d.name for d in rel.iterdir() if d.is_dir() and not d.name.startswith("."))


def current_release(tdir: Path) -> str | None:
    link = tdir / "current"
    return os.readlink(link).split("/")[-1] if link.is_symlink() else None


def kind_of(name: str) -> str:
    return "prod" if name == PROD else "preview"


def ensure_layout(conf: Conf) -> None:
    for d in ("cache", "state", "www"):
        (conf.root / d).mkdir(parents=True, exist_ok=True)
    for s in conf.sites:
        (conf.root / "www" / s.slug).mkdir(exist_ok=True)
        (conf.root / s.slug).mkdir(exist_ok=True)


def clean_staging(conf: Conf) -> None:
    """Remove half-written releases left by a crash or a reboot."""
    for s in conf.sites:
        for rel in (conf.root / s.slug).glob("*/releases"):
            for d in rel.glob(".staging-*"):
                log(f"{s.slug}: removing leftover {d.relative_to(conf.root)}")
                shutil.rmtree(d, ignore_errors=True)


# ── remote and cache ─────────────────────────────────────────────────────

def ls_remote(url: str) -> tuple[dict[str, str], dict[str, str]]:
    out = git("ls-remote", url, timeout=60).stdout.decode("utf-8", "surrogateescape")
    heads, sites = {}, {}
    for line in out.splitlines():
        sha, _, ref = line.partition("\t")
        if ref.startswith("refs/heads/"):
            heads[ref[len("refs/heads/"):]] = sha
        elif ref.startswith("refs/sites/"):
            sites[ref[len("refs/sites/"):]] = sha
    return heads, sites


def cache_repo(conf: Conf, site: Site) -> Path:
    path = conf.root / "cache" / f"{site.slug}.git"
    if not path.is_dir():
        git("init", "--quiet", "--bare", str(path))
    return path


def fetch_commit(conf: Conf, site: Site, ref_name: str, sha: str) -> Path:
    cache = cache_repo(conf, site)
    if git("cat-file", "-e", f"{sha}^{{commit}}", cwd=cache, check=False).returncode != 0:
        git("fetch", "--quiet", "--no-tags", "--depth", "1", site.url,
            f"+refs/sites/{ref_name}:refs/sites/{ref_name}", cwd=cache, timeout=900)
        if git("cat-file", "-e", f"{sha}^{{commit}}", cwd=cache, check=False).returncode != 0:
            raise NotYet(f"refs/sites/{ref_name} moved while fetching")
    git("update-ref", f"refs/keep/{sha}", sha, cwd=cache)
    return cache


def bad_path(p: str) -> str | None:
    if not p or p.startswith("/") or "\\" in p:
        return "absolute or odd path"
    if any(ord(c) < 32 or ord(c) == 127 for c in p):
        return "control character in path"
    parts = p.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return "'.' or '..' in path"
    if any(len(part.encode("utf-8", "surrogateescape")) > 255 for part in parts):
        return "path component too long"
    return None


def list_tree(cache: Path, sha: str, kind: str) -> dict[str, tuple[str, str, int]]:
    """{path: (mode, blob, size)}; Refused if anything but plain files appears."""
    out = git("ls-tree", "-r", "-l", "-z", "--full-tree", sha, cwd=cache).stdout
    entries, total = {}, 0
    for rec in out.split(b"\0"):
        if not rec:
            continue
        meta, _, raw_path = rec.partition(b"\t")
        mode, typ, obj, size = meta.decode().split()
        path = raw_path.decode("utf-8", "surrogateescape")
        if typ != "blob" or mode not in ("100644", "100755"):
            raise Refused(f"'{path}' is not a regular file ({typ} {mode}: symlink or submodule?)")
        why = bad_path(path)
        if why:
            raise Refused(f"{why}: {path!r}")
        entries[path] = (mode, obj, int(size))
        total += int(size)
    if ".release.json" not in entries:
        raise Refused("no .release.json at the top of the tree")
    if len(entries) > MAX_FILES:
        raise Refused(f"{len(entries)} files (limit {MAX_FILES})")
    if total > MAX_BYTES[kind]:
        raise Refused(f"{total} bytes (limit {MAX_BYTES[kind]})")
    return entries


def materialise(cache: Path, entries: dict, dest: Path, prev: Path | None,
                prev_manifest: dict) -> None:
    """Write every file of the release into `dest` (which must not exist).
    Files whose (mode, blob) equal the previous release's are hardlinked."""
    dest.mkdir(mode=0o755)
    todo = []
    for path, (mode, blob, _size) in sorted(entries.items()):
        out = dest / path
        out.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        if prev is not None and prev_manifest.get(path) == [mode, blob]:
            try:
                os.link(prev / path, out, follow_symlinks=False)
                continue
            except OSError:
                pass  # purged or missing: write it from git
        todo.append((path, mode, blob))
    if not todo:
        return
    proc = subprocess.Popen(["git", "cat-file", "--batch"], cwd=cache, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, env=dict(os.environ, LC_ALL="C"))
    try:
        for path, mode, blob in todo:
            proc.stdin.write(blob.encode() + b"\n")
            proc.stdin.flush()
            header = proc.stdout.readline().split()
            if len(header) != 3 or header[1] != b"blob":
                raise RuntimeError(f"cat-file: unexpected answer for {blob}: {header!r}")
            remaining = int(header[2])
            fd = os.open(dest / path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o755 if mode == "100755" else 0o644)
            with os.fdopen(fd, "wb") as f:
                while remaining:
                    chunk = proc.stdout.read(min(remaining, 1 << 20))
                    if not chunk:
                        raise RuntimeError("cat-file: short read")
                    f.write(chunk)
                    remaining -= len(chunk)
            os.chmod(dest / path, 0o755 if mode == "100755" else 0o644)
            proc.stdout.read(1)  # the newline after the content
    finally:
        proc.stdin.close()
        proc.wait(timeout=60)


# ── smoke test ───────────────────────────────────────────────────────────

def smoke_sample(entries: dict) -> list[str]:
    paths = sorted(p for p in entries if p != ".release.json")
    pages = [p for p in paths if p.endswith(".html") and p != "index.html"]
    others = [p for p in paths if not p.endswith(".html")]
    sample = ["index.html"] if "index.html" in entries else []
    want = SMOKE_FILES - len(sample) - (1 if others else 0)
    if pages and want > 0:
        step = max(1, len(pages) // want)
        sample += pages[::step][:want]
    if others:
        sample.append(others[len(others) // 2])
    return sample


def smoke_test(conf: Conf, slug: str, name: str, release: Path, entries: dict) -> None:
    if not conf.smoke_base:
        log(f"{slug}/{name}: no smoke_base configured; smoke test skipped")
        return
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for path in smoke_sample(entries):
        url_path = "" if path == "index.html" else urllib.parse.quote(path)
        url = f"{conf.smoke_base.rstrip('/')}/{slug}/{name}/{url_path}"
        try:
            with opener.open(url, timeout=15) as r:
                body = r.read()
        except urllib.error.HTTPError as e:     # Caddy answered, wrongly: the release is bad
            raise Refused(f"smoke test: {url}: {e}") from None
        except OSError as e:                    # Caddy down or restarting: try again later
            raise NotYet(f"smoke test: {url}: {e}") from None
        if hashlib.sha256(body).digest() != hashlib.sha256((release / path).read_bytes()).digest():
            raise Refused(f"smoke test: {url} does not serve the release's {path}")


# ── deploying one target ─────────────────────────────────────────────────

def deploy(conf: Conf, site: Site, st: dict, name: str, branch: str, tip: str,
           ref_name: str, ref_sha: str) -> bool:
    """Deploy refs/sites/<ref_name> as target `name` if it is new and valid.
    Returns True if something was deployed."""
    kind = kind_of(name)
    t = st["targets"].setdefault(name, {"kind": kind, "failed": {}})
    t["branch"] = branch
    t["absent_since"] = None
    tag = f"{site.slug}/{name}"
    if t.get("hold") or t.get("site_ref") == ref_sha or ref_sha in t["failed"]:
        return False

    cache = fetch_commit(conf, site, ref_name, ref_sha)
    try:
        info = json.loads(git("show", f"{ref_sha}:.release.json", cwd=cache).stdout)
    except (RuntimeError, ValueError) as e:
        raise Refused(f"unreadable .release.json: {e}") from None
    if info.get("source_ref") != branch:
        raise Refused(f".release.json names branch {info.get('source_ref')!r}, not {branch!r}")
    if info.get("source_commit") != tip:
        if t.get("waiting") != [ref_sha, tip]:
            log(f"{tag}: refs/sites/{ref_name} was built from {str(info.get('source_commit'))[:7]}, "
                f"but {branch} is at {tip[:7]}; waiting for CI")
            t["waiting"] = [ref_sha, tip]
        return False
    t.pop("waiting", None)

    entries = list_tree(cache, ref_sha, kind)
    size = sum(e[2] for e in entries.values())
    usage = shutil.disk_usage(conf.root)
    tdir = target_dir(conf, site.slug, name)
    new_target = current_release(tdir) is None
    if kind == "preview":
        if new_target and usage.used / usage.total > DISK_LIMIT:
            raise NotYet(f"disk {usage.used / usage.total:.0%} full; no new previews")
        if new_target:
            make_room_for_preview(conf, site, st, name)
    elif usage.free - size < PROD_RESERVE:
        raise NotYet(f"not enough free disk for {size} bytes")

    rel = tdir / "releases"
    rel.mkdir(parents=True, exist_ok=True)
    existing = releases_of(tdir)
    rid = f"{stamp(existing[-1] if existing else None)}-{tip[:7]}"
    staging = rel / f".staging-{rid}"
    prev_rid = current_release(tdir)
    prev = rel / prev_rid if prev_rid else None
    prev_manifest = read_json(rel / f"{prev_rid}.manifest.json", {}).get("files", {}) if prev_rid else {}
    materialise(cache, entries, staging, prev, prev_manifest)
    os.rename(staging, rel / rid)
    write_json(rel / f"{rid}.manifest.json", {
        "site_ref": ref_sha, "source_commit": tip, "branch": branch, "created": utcnow(),
        "files": {p: [m, b] for p, (m, b, _s) in entries.items()}})

    symlink_swap(tdir / "current", f"releases/{rid}")
    symlink_swap(conf.root / "www" / site.slug / name, f"../../{site.slug}/{name}/current")
    try:
        smoke_test(conf, site.slug, name, rel / rid, entries)
    except (Refused, NotYet):
        if prev_rid:
            symlink_swap(tdir / "current", f"releases/{prev_rid}")
        else:
            unserve(conf, site.slug, name)
        shutil.rmtree(rel / rid, ignore_errors=True)
        (rel / f"{rid}.manifest.json").unlink(missing_ok=True)
        log(f"{tag}: smoke test failed; " + (f"back on {prev_rid}" if prev_rid else "not served"))
        raise
    t.update(site_ref=ref_sha, commit=tip, release=rid, deployed_at=utcnow(), deployed_ts=time.time())
    log(f"{tag}: deployed {rid} ({len(entries)} files, {size} bytes) from {branch}@{tip[:7]}")
    prune(tdir, KEEP[kind])
    return True


def unserve(conf: Conf, slug: str, name: str) -> None:
    link = conf.root / "www" / slug / name
    if link.is_symlink():
        link.unlink()
    cur = target_dir(conf, slug, name) / "current"
    if cur.is_symlink():
        cur.unlink()


def remove_target(conf: Conf, site: Site, st: dict, name: str, why: str) -> None:
    unserve(conf, site.slug, name)
    shutil.rmtree(target_dir(conf, site.slug, name), ignore_errors=True)
    st["targets"].pop(name, None)
    log(f"{site.slug}/{name}: removed ({why})")


def make_room_for_preview(conf: Conf, site: Site, st: dict, new: str) -> None:
    live = [(t.get("deployed_ts", 0), n) for n, t in st["targets"].items()
            if n not in (PROD, new) and t.get("release") and not t.get("hold")]
    held = sum(1 for n, t in st["targets"].items() if n not in (PROD, new) and t.get("hold"))
    live.sort()
    while live and len(live) + held >= MAX_PREVIEWS:
        _, oldest = live.pop(0)
        remove_target(conf, site, st, oldest, f"more than {MAX_PREVIEWS} previews; oldest goes")


def prune(tdir: Path, keep: int) -> None:
    cur = current_release(tdir)
    rels = releases_of(tdir)
    for rid in rels[:-keep] if keep else rels:
        if rid == cur:
            continue
        shutil.rmtree(tdir / "releases" / rid, ignore_errors=True)
        (tdir / "releases" / f"{rid}.manifest.json").unlink(missing_ok=True)


# ── one polling round ────────────────────────────────────────────────────

def pull_site(conf: Conf, site: Site) -> None:
    heads, refs = ls_remote(site.url)
    st = load_state(conf, site.slug)
    now = time.time()

    by_name: dict[str, list[str]] = {}
    for branch in heads:
        if branch == site.default_branch:
            name = PROD
        else:
            name = sanitize(branch)
            if not name or name == site.default_branch or not NAME_RE.match(name):
                continue
        by_name.setdefault(name, []).append(branch)

    for name, branches in sorted(by_name.items()):
        tag = f"{site.slug}/{name}"
        if len(branches) > 1:
            if st.get("collisions", {}).get(name) != sorted(branches):
                log(f"{tag}: branches {', '.join(sorted(branches))} share this name; none served")
            st.setdefault("collisions", {})[name] = sorted(branches)
            continue
        st.get("collisions", {}).pop(name, None)
        branch = branches[0]
        ref_name = site.default_branch if name == PROD else name
        if ref_name not in refs:
            continue
        try:
            deploy(conf, site, st, name, branch, heads[branch], ref_name, refs[ref_name])
        except Refused as e:
            st["targets"][name]["failed"][refs[ref_name]] = f"{utcnow()} {e}"
            log(f"{tag}: refusing refs/sites/{ref_name} {refs[ref_name][:7]}: {e}")
        except NotYet as e:
            log(f"{tag}: not now: {e}")
        finally:
            save_state(conf, site.slug, st)

    for name, t in list(st["targets"].items()):
        if name == PROD or name in by_name:
            continue
        ref_alive = name in refs
        t["absent_since"] = t.get("absent_since") or now
        grace = GRACE_BRANCH_ONLY if ref_alive else GRACE_BOTH
        if not t.get("hold") and now - t["absent_since"] >= grace:
            remove_target(conf, site, st, name, "its branch was deleted")
    write_index(conf, site, st)

    cache = conf.root / "cache" / f"{site.slug}.git"
    if cache.is_dir() and now - st.get("last_gc", 0) > GC_EVERY:
        for line in git("for-each-ref", "--format=%(refname)", "refs/keep/", cwd=cache).stdout.decode().split():
            git("update-ref", "-d", line, cwd=cache)
        git("gc", "--quiet", "--prune=now", cwd=cache, timeout=1800)
        st["last_gc"] = now
    save_state(conf, site.slug, st)


def write_index(conf: Conf, site: Site, st: dict) -> None:
    rows = []
    for name, t in sorted(st["targets"].items(), key=lambda kv: (kv[0] != PROD, kv[0])):
        if not t.get("release"):
            continue
        label = "produção / production" if name == PROD else html.escape(name)
        rows.append(
            f"<tr><td><a href=\"./{html.escape(name)}/\">{label}</a></td>"
            f"<td><code>{html.escape(t.get('branch', ''))}</code></td>"
            f"<td><code>{html.escape(t.get('commit', '')[:7])}</code></td>"
            f"<td>{html.escape(t.get('deployed_at', ''))}{' (hold)' if t.get('hold') else ''}</td></tr>")
    page = f"""<!doctype html>
<html lang="pt"><head><meta charset="utf-8"><meta name="robots" content="noindex">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prévias: {html.escape(site.slug)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem}}
td,th{{padding:.3rem .8rem;text-align:left}}</style></head><body>
<h1>Prévias / Previews: {html.escape(site.slug)}</h1>
<p>Cada ramo do repositório aparece aqui depois de verificado. Each branch of the repository
appears here once it has been checked.</p>
<table><tr><th>prévia / preview</th><th>ramo / branch</th><th>commit</th><th>publicado / deployed (UTC)</th></tr>
{chr(10).join(rows)}
</table></body></html>
"""
    out = conf.root / "www" / site.slug / "index.html"
    tmp = out.with_name(".index.html.tmp")
    tmp.write_text(page, encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, out)


def cmd_pull(conf: Conf, _args) -> int:
    try:
        lock = Lock(conf.root, wait=False).__enter__()
    except BlockingIOError:
        log("another sitepull is running; skipping this round")
        return 0
    errors = []
    try:
        ensure_layout(conf)
        clean_staging(conf)
        for site in conf.sites:
            try:
                pull_site(conf, site)
            except Exception as e:  # noqa: BLE001 — one site must not stop the others
                errors.append(f"{site.slug}: {e}")
                print(f"{site.slug}: ERROR {e}", file=sys.stderr, flush=True)
        write_json(conf.root / "heartbeat.json",
                   {"time": utcnow(), "ts": time.time(), "boot_id": boot_id(), "errors": errors})
    finally:
        lock.__exit__()
    return 1 if errors else 0


# ── owner commands (sitectl) ─────────────────────────────────────────────

def cmd_status(conf: Conf, _args) -> int:
    hb = read_json(conf.root / "heartbeat.json", None)
    bad = False
    if hb is None:
        print("heartbeat: never ran")
        bad = True
    else:
        age = time.time() - hb["ts"]
        stale = age > STALE
        bad |= stale or bool(hb["errors"])
        print(f"heartbeat: {hb['time']} ({age / 60:.0f} min ago){'  ** STALE **' if stale else ''}"
              f"{'' if hb['boot_id'] == boot_id() else '  (before the last reboot)'}")
        for e in hb["errors"]:
            print(f"  error: {e}")
    for site in conf.sites:
        st = load_state(conf, site.slug)
        print(f"\n{site.slug}")
        for name, t in sorted(st["targets"].items(), key=lambda kv: (kv[0] != PROD, kv[0])):
            flags = []
            if t.get("hold"):
                flags.append("HOLD (sitectl release to resume)")
            if t.get("failed"):
                flags.append(f"{len(t['failed'])} refused")
            if t.get("waiting"):
                flags.append("waiting for CI")
            if t.get("absent_since"):
                flags.append("branch deleted")
            print(f"  {name:<20} {t.get('branch', '?'):<24} {t.get('commit', '')[:7]:<8} "
                  f"{t.get('release', '-'):<26} {'; '.join(flags)}")
        for name, branches in st.get("collisions", {}).items():
            print(f"  {name:<20} COLLISION: {', '.join(branches)}")
    return 1 if bad else 0


def cmd_list(conf: Conf, args) -> int:
    site = conf.site(args.slug)
    tdir = target_dir(conf, site.slug, args.target)
    cur = current_release(tdir)
    for rid in releases_of(tdir):
        m = read_json(tdir / "releases" / f"{rid}.manifest.json", {})
        print(f"{'*' if rid == cur else ' '} {rid}  {m.get('branch', '?')}@{m.get('source_commit', '')[:7]}")
    st = load_state(conf, site.slug)
    for sha, why in st["targets"].get(args.target, {}).get("failed", {}).items():
        print(f"  refused {sha[:7]}: {why}")
    return 0


def cmd_rollback(conf: Conf, args) -> int:
    site = conf.site(args.slug)
    with Lock(conf.root, wait=True):
        st = load_state(conf, site.slug)
        t = st["targets"].get(args.target)
        tdir = target_dir(conf, site.slug, args.target)
        rels, cur = releases_of(tdir), current_release(tdir)
        if t is None or not rels:
            die(f"{site.slug}/{args.target}: nothing deployed")
        if args.release:
            rid = args.release
            if rid not in rels:
                die(f"no release {rid}; see `sitectl list {site.slug} {args.target}`")
        else:
            older = [r for r in rels if cur is None or r < cur]
            if not older:
                die("no older release to go back to")
            rid = older[-1]
        m = read_json(tdir / "releases" / f"{rid}.manifest.json", {})
        symlink_swap(tdir / "current", f"releases/{rid}")
        t.update(hold=True, release=rid, site_ref=m.get("site_ref"), commit=m.get("source_commit", ""),
                 deployed_at=utcnow())
        save_state(conf, site.slug, st)
        write_index(conf, site, st)
    print(f"{site.slug}/{args.target} now serves {rid} and is ON HOLD: new pushes are not "
          f"deployed until `sitectl release {site.slug} {args.target}`")
    return 0


def cmd_release(conf: Conf, args) -> int:
    site = conf.site(args.slug)
    with Lock(conf.root, wait=True):
        st = load_state(conf, site.slug)
        t = st["targets"].get(args.target)
        if not t or not t.get("hold"):
            die(f"{site.slug}/{args.target} is not on hold")
        t["hold"] = False
        t["failed"] = {}
        save_state(conf, site.slug, st)
    print(f"{site.slug}/{args.target}: hold released; the next poll deploys the branch's latest build")
    return 0


def cmd_retry(conf: Conf, args) -> int:
    site = conf.site(args.slug)
    with Lock(conf.root, wait=True):
        st = load_state(conf, site.slug)
        t = st["targets"].get(args.target)
        if not t or not t.get("failed"):
            die(f"{site.slug}/{args.target} has no refused releases")
        n = len(t["failed"])
        t["failed"] = {}
        save_state(conf, site.slug, st)
    print(f"{site.slug}/{args.target}: forgot {n} refusal(s); the next poll tries again")
    return 0


def cmd_purge(conf: Conf, args) -> int:
    site = conf.site(args.slug)
    why = bad_path(args.path)
    if why:
        die(f"{why}: {args.path!r}")
    removed = 0
    with Lock(conf.root, wait=True):
        for tdir in (conf.root / site.slug).iterdir():
            for rid in releases_of(tdir):
                victim = tdir / "releases" / rid / args.path
                if victim.is_file() and not victim.is_symlink():
                    victim.unlink()
                    removed += 1
                elif victim.is_dir() and not victim.is_symlink():
                    shutil.rmtree(victim)
                    removed += 1
    print(f"removed {args.path} from {removed} release(s) of {site.slug}. It returns with the next "
          f"build unless it is also removed from the repository (and, if it was ever pushed, "
          f"purged by GitHub Support).")
    return 0


def cmd_import(conf: Conf, args) -> int:
    """Break-glass: serve a tarball read from stdin, and hold the target."""
    site = conf.site(args.slug)
    with Lock(conf.root, wait=True):
        ensure_layout(conf)
        st = load_state(conf, site.slug)
        tdir = target_dir(conf, site.slug, args.target)
        rel = tdir / "releases"
        rel.mkdir(parents=True, exist_ok=True)
        existing = releases_of(tdir)
        rid = f"{stamp(existing[-1] if existing else None)}-import"
        staging = rel / f".staging-{rid}"
        staging.mkdir(mode=0o755)
        files = total = 0
        with tarfile.open(fileobj=sys.stdin.buffer, mode="r|*") as tar:
            for member in tar:
                name = member.name.removeprefix("./")
                if member.isdir() or name in ("", "."):
                    continue
                if not member.isfile():
                    die(f"tarball holds a non-regular file: {member.name}")
                why = bad_path(name)
                if why:
                    die(f"{why}: {member.name!r}")
                files += 1
                total += member.size
                if files > MAX_FILES or total > MAX_BYTES[kind_of(args.target)]:
                    die("tarball too large")
                out = staging / name
                out.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                with tar.extractfile(member) as src, open(out, "xb") as dst:
                    shutil.copyfileobj(src, dst)
                os.chmod(out, 0o644)
        os.rename(staging, rel / rid)
        write_json(rel / f"{rid}.manifest.json", {"site_ref": None, "source_commit": "",
                                                   "branch": "(import)", "created": utcnow(), "files": {}})
        symlink_swap(tdir / "current", f"releases/{rid}")
        symlink_swap(conf.root / "www" / site.slug / args.target,
                     f"../../{site.slug}/{args.target}/current")
        t = st["targets"].setdefault(args.target, {"kind": kind_of(args.target), "failed": {}})
        t.update(hold=True, release=rid, site_ref=None, commit="", branch="(import)",
                 deployed_at=utcnow(), deployed_ts=time.time())
        save_state(conf, site.slug, st)
        write_index(conf, site, st)
    print(f"{site.slug}/{args.target} serves import {rid} ({files} files) and is ON HOLD")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sitectl", description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, default=CONFIG)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pull", help="one polling round (what the timer runs)")
    sub.add_parser("status", help="what is served, holds, refusals, heartbeat")
    for cmd, hlp in (("list", "releases kept for a target"),
                     ("rollback", "serve an older release and hold the target"),
                     ("release", "end a hold: deploy new pushes again"),
                     ("retry", "forget refused releases, so they are tried again"),
                     ("import", "break-glass: serve a tarball from stdin, and hold")):
        p = sub.add_parser(cmd, help=hlp)
        p.add_argument("slug")
        p.add_argument("target", nargs="?", default=PROD, help=f"preview name, or {PROD} (default)")
        if cmd == "rollback":
            p.add_argument("release", nargs="?", help="release id (default: the one before)")
    p = sub.add_parser("purge", help="delete a file from every kept release of a site")
    p.add_argument("slug")
    p.add_argument("path", help="path inside the site, e.g. videos/x.mp4")
    args = ap.parse_args(argv)

    if os.geteuid() == 0:
        die("do not run as root; `sitectl` runs this as the `sites` user")
    if getattr(args, "target", PROD) != PROD and not NAME_RE.match(args.target):
        die(f"invalid target name {args.target!r}")
    conf = load_config(args.config)
    os.umask(0o022)
    return {"pull": cmd_pull, "status": cmd_status, "list": cmd_list, "rollback": cmd_rollback,
            "release": cmd_release, "retry": cmd_retry, "purge": cmd_purge, "import": cmd_import}[args.cmd](conf, args)


if __name__ == "__main__":
    sys.exit(main())
