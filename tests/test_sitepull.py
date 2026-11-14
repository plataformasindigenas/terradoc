"""server/sitepull.py against a local bare 'GitHub' repository and a local HTTP
server standing in for Caddy (serving <root>/www, symlinks and all)."""

import functools
import importlib.util
import json
import os
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "sitepull", Path(__file__).resolve().parents[1] / "server" / "sitepull.py")
sp = importlib.util.module_from_spec(SPEC)
sys.modules["sitepull"] = sp
SPEC.loader.exec_module(sp)


def run(*args, cwd=None, input=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@x", GIT_CONFIG_NOSYSTEM="1", HOME=str(cwd or "."))
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, env=env,
                          input=input).stdout.decode().strip()


class Remote:
    """A bare repo with branches, plus helpers to publish refs/sites/* like CI."""

    def __init__(self, base: Path):
        self.bare = base / "remote.git"
        run("git", "init", "-q", "--bare", "-b", "master", str(self.bare))
        self.work = base / "work"
        run("git", "init", "-q", "-b", "master", str(self.work))
        self.n = 0

    @property
    def url(self):
        return f"file://{self.bare}"

    def commit(self, branch: str) -> str:
        """A new source commit on `branch` (pushed); returns its sha."""
        self.n += 1
        w = self.work
        if self.n > 1:
            if run("git", "branch", "--list", branch, cwd=w):
                run("git", "checkout", "-q", branch, cwd=w)
            else:
                run("git", "checkout", "-q", "-b", branch, "master", cwd=w)
        (w / "src.txt").write_text(str(self.n))
        run("git", "add", "-A", cwd=w)
        run("git", "commit", "-q", "-m", f"c{self.n}", cwd=w)
        run("git", "push", "-q", "-f", self.url, f"{branch}:refs/heads/{branch}", cwd=w)
        return run("git", "rev-parse", "HEAD", cwd=w)

    def publish(self, name: str, branch: str, commit: str, files: dict | None = None,
                symlink: str | None = None, release: dict | None = None) -> str:
        d = self.work.parent / f"site-{self.n}-{name}"
        d.mkdir()
        files = files or {"index.html": f"<h1>{branch} {commit[:7]}</h1>",
                          "dicionario/a.html": "a", "dicionario/b.html": "b",
                          "images/logo.png": "PNG"}
        for p, body in files.items():
            (d / p).parent.mkdir(parents=True, exist_ok=True)
            (d / p).write_text(body)
        if symlink:
            os.symlink(symlink, d / "link")
        info = {"source_ref": branch, "source_commit": commit, "modules": {}}
        info.update(release or {})
        (d / ".release.json").write_text(json.dumps(info))
        run("git", "init", "-q", "-b", "site", cwd=d)
        run("git", "add", "-A", cwd=d)
        run("git", "commit", "-q", "-m", "site", cwd=d)
        run("git", "push", "-q", "-f", self.url, f"HEAD:refs/sites/{name}", cwd=d)
        return run("git", "rev-parse", "HEAD", cwd=d)

    def delete(self, ref: str):
        run("git", "push", "-q", self.url, f":{ref}", cwd=self.work)


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture()
def env(tmp_path):
    remote = Remote(tmp_path)
    root = tmp_path / "srv"
    (root / "www").mkdir(parents=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0),
                                functools.partial(Quiet, directory=str(root / "www")))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    ini = tmp_path / "sites.ini"
    ini.write_text(f"[DEFAULT]\nroot = {root}\nsmoke_base = http://127.0.0.1:{httpd.server_port}\n\n"
                   f"[demo]\nurl = {remote.url}\ndefault_branch = master\n")
    yield remote, root, ini
    httpd.shutdown()


def pull(ini):
    return sp.main(["--config", str(ini), "pull"])


def served(root, name, path="index.html"):
    return (root / "www" / "demo" / name / path).read_text()


def state(root):
    return json.loads((root / "state" / "demo.json").read_text())["targets"]


# ── names ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("branch,name", [
    ("FFGerardi-patch-1", "ffgerardi-patch-1"),
    ("Foo_Bar", "foo-bar"),
    ("feature/Novo verbete", "feature-novo-verbete"),
    ("--x--", "x"),
    ("ação", "a-o"),
    ("KK", "k"),          # Kelvin sign is not ASCII: no sneaky lowercasing
    ("a" * 50, "a" * 40),
    ("___", ""),
])
def test_sanitize_matches_the_workflow(branch, name):
    assert sp.sanitize(branch) == name


def test_sanitize_agrees_with_the_shell_version():
    shell = ("printf '%s' \"$1\" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9-]+/-/g; s/^-+//'"
             " | cut -c1-40 | sed -E 's/-+$//'")
    for b in ["FFGerardi-patch-1", "Foo_Bar", "feature/Novo verbete", "--x--", "a" * 50 + "-b", "x.y.z"]:
        out = subprocess.run(["bash", "-c", shell, "_", b], capture_output=True, text=True).stdout
        assert out.strip() == sp.sanitize(b), b


# ── the normal path ──────────────────────────────────────────────────────

def test_production_and_preview_are_deployed_and_smoke_tested(env):
    remote, root, ini = env
    c1 = remote.commit("master")
    remote.publish("master", "master", c1)
    c2 = remote.commit("FFGerardi-patch-1")
    remote.publish("ffgerardi-patch-1", "FFGerardi-patch-1", c2)
    assert pull(ini) == 0
    assert c1[:7] in served(root, "_prod")
    assert c2[:7] in served(root, "ffgerardi-patch-1")
    assert (root / "demo" / "_prod" / "current").is_symlink()
    index = (root / "www" / "demo" / "index.html").read_text()
    assert "ffgerardi-patch-1" in index and "FFGerardi-patch-1" in index
    hb = json.loads((root / "heartbeat.json").read_text())
    assert hb["errors"] == []


def test_unchanged_files_are_hardlinked_and_nothing_redeploys_without_change(env):
    remote, root, ini = env
    c1 = remote.commit("master")
    remote.publish("master", "master", c1)
    assert pull(ini) == 0
    first = state(root)["_prod"]["release"]
    assert pull(ini) == 0
    assert state(root)["_prod"]["release"] == first
    c2 = remote.commit("master")
    remote.publish("master", "master", c2)
    assert pull(ini) == 0
    second = state(root)["_prod"]["release"]
    assert second != first
    rel = root / "demo" / "_prod" / "releases"
    a, b = rel / first / "dicionario" / "a.html", rel / second / "dicionario" / "a.html"
    assert a.stat().st_ino == b.stat().st_ino
    assert (rel / first / "index.html").stat().st_ino != (rel / second / "index.html").stat().st_ino


# ── what must not be served ──────────────────────────────────────────────

def test_a_ref_not_built_from_the_branch_tip_is_not_served(env):
    remote, root, ini = env
    c1 = remote.commit("master")
    remote.commit("master")                       # tip moved on; CI has not caught up
    remote.publish("master", "master", c1)
    assert pull(ini) == 0
    assert not (root / "www" / "demo" / "_prod").exists()
    assert state(root)["_prod"].get("waiting")
    assert not state(root)["_prod"]["failed"]     # not refused: CI may still publish


def test_a_ref_naming_another_branch_is_refused(env):
    remote, root, ini = env
    c1 = remote.commit("master")
    remote.publish("master", "other", c1)
    assert pull(ini) == 0
    assert state(root)["_prod"]["failed"]
    assert not (root / "www" / "demo" / "_prod").exists()


def test_a_tree_with_a_symlink_is_refused(env):
    remote, root, ini = env
    c1 = remote.commit("master")
    remote.publish("master", "master", c1, symlink="/etc/passwd")
    assert pull(ini) == 0
    [why] = state(root)["_prod"]["failed"].values()
    assert "not a regular file" in why
    assert not (root / "demo" / "_prod" / "current").exists()


def test_a_refused_ref_is_not_retried_and_the_good_release_stays(env, capsys):
    remote, root, ini = env
    c1 = remote.commit("master")
    remote.publish("master", "master", c1)
    assert pull(ini) == 0
    c2 = remote.commit("master")
    remote.publish("master", "master", c2, symlink="x")
    assert pull(ini) == 0
    assert c1[:7] in served(root, "_prod")
    capsys.readouterr()
    assert pull(ini) == 0
    assert "refusing" not in capsys.readouterr().out


def test_colliding_branches_are_both_ignored(env):
    remote, root, ini = env
    remote.commit("master")
    a = remote.commit("Foo-Bar")
    remote.commit("foo-bar")
    remote.publish("foo-bar", "Foo-Bar", a)
    assert pull(ini) == 0
    assert not (root / "www" / "demo" / "foo-bar").exists()
    st = json.loads((root / "state" / "demo.json").read_text())
    assert st["collisions"]["foo-bar"] == ["Foo-Bar", "foo-bar"]


@pytest.mark.parametrize("breakage,refused", [
    (lambda base: base + "/nothing-here", True),                  # Caddy answers 404: bad release
    (lambda base: base.replace("127.0.0.1", "127.0.0.2"), False),  # Caddy down: try again later
])
def test_a_failed_smoke_test_rolls_back(env, monkeypatch, breakage, refused):
    remote, root, ini = env
    c1 = remote.commit("master")
    remote.publish("master", "master", c1)
    assert pull(ini) == 0
    good = os.readlink(root / "demo" / "_prod" / "current")
    c2 = remote.commit("master")
    remote.publish("master", "master", c2)
    real = sp.smoke_test

    def broken(conf, slug, name, release, entries):
        conf.smoke_base = breakage(conf.smoke_base)
        real(conf, slug, name, release, entries)
    monkeypatch.setattr(sp, "smoke_test", broken)
    assert pull(ini) == 0
    assert os.readlink(root / "demo" / "_prod" / "current") == good
    assert c1[:7] in served(root, "_prod")
    assert len(sp.releases_of(root / "demo" / "_prod")) == 1
    failed = state(root)["_prod"]["failed"]
    assert bool(failed) == refused
    monkeypatch.setattr(sp, "smoke_test", real)
    if refused:
        assert pull(ini) == 0
        assert c1[:7] in served(root, "_prod")              # not retried...
        assert sp.main(["--config", str(ini), "retry", "demo"]) == 0
    assert pull(ini) == 0
    assert c2[:7] in served(root, "_prod")                  # ...until asked, or Caddy is back


# ── branch deletion, budget, pruning ─────────────────────────────────────

def test_preview_goes_after_its_branch_and_ref_are_deleted(env, monkeypatch):
    remote, root, ini = env
    remote.commit("master")
    c = remote.commit("rascunho")
    remote.publish("rascunho", "rascunho", c)
    assert pull(ini) == 0
    assert (root / "www" / "demo" / "rascunho").exists()
    remote.delete("refs/heads/rascunho")
    remote.delete("refs/sites/rascunho")
    assert pull(ini) == 0
    assert (root / "www" / "demo" / "rascunho").exists()          # grace period
    t0 = sp.time.time()
    monkeypatch.setattr(sp.time, "time", lambda: t0 + sp.GRACE_BOTH + 1)
    assert pull(ini) == 0
    assert not (root / "www" / "demo" / "rascunho").exists()
    assert not (root / "demo" / "rascunho").exists()
    assert "rascunho" not in state(root)


def test_at_most_max_previews(env):
    remote, root, ini = env
    remote.commit("master")
    for i in range(sp.MAX_PREVIEWS + 1):
        c = remote.commit(f"b{i}")
        remote.publish(f"b{i}", f"b{i}", c)
        assert pull(ini) == 0
    live = [n for n in state(root) if n != "_prod"]
    assert len(live) == sp.MAX_PREVIEWS and "b0" not in live


def test_prune_keeps_ten_production_releases(env):
    remote, root, ini = env
    for _ in range(sp.KEEP["prod"] + 2):
        c = remote.commit("master")
        remote.publish("master", "master", c)
        assert pull(ini) == 0
    assert len(sp.releases_of(root / "demo" / "_prod")) == sp.KEEP["prod"]


def test_leftover_staging_is_cleaned(env):
    remote, root, ini = env
    junk = root / "demo" / "_prod" / "releases" / ".staging-x"
    junk.mkdir(parents=True)
    assert pull(ini) == 0
    assert not junk.exists()


# ── owner commands ───────────────────────────────────────────────────────

def test_rollback_holds_until_released(env):
    remote, root, ini = env
    c1 = remote.commit("master")
    remote.publish("master", "master", c1)
    assert pull(ini) == 0
    c2 = remote.commit("master")
    remote.publish("master", "master", c2)
    assert pull(ini) == 0
    assert c2[:7] in served(root, "_prod")
    assert sp.main(["--config", str(ini), "rollback", "demo"]) == 0
    assert c1[:7] in served(root, "_prod")
    c3 = remote.commit("master")
    remote.publish("master", "master", c3)
    assert pull(ini) == 0
    assert c1[:7] in served(root, "_prod")        # held
    assert sp.main(["--config", str(ini), "status"]) in (0, 1)
    assert sp.main(["--config", str(ini), "release", "demo"]) == 0
    assert pull(ini) == 0
    assert c3[:7] in served(root, "_prod")


def test_purge_removes_a_file_from_every_release(env):
    remote, root, ini = env
    for _ in range(3):
        c = remote.commit("master")
        remote.publish("master", "master", c)
        assert pull(ini) == 0
    assert sp.main(["--config", str(ini), "purge", "demo", "images/logo.png"]) == 0
    assert not list((root / "demo").glob("*/releases/*/images/logo.png"))
    with pytest.raises(SystemExit):
        sp.main(["--config", str(ini), "purge", "demo", "../state/demo.json"])


def test_import_serves_a_tarball_and_holds(env, monkeypatch, tmp_path):
    import io
    import tarfile
    remote, root, ini = env
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        data = b"<h1>emergency</h1>"
        info = tarfile.TarInfo("./index.html")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    buf.seek(0)

    class Stdin:
        buffer = buf
    monkeypatch.setattr(sp.sys, "stdin", Stdin)
    assert sp.main(["--config", str(ini), "import", "demo"]) == 0
    assert "emergency" in served(root, "_prod")
    assert state(root)["_prod"]["hold"] is True
