# sitepull: the server side of terradoc publishing

CI (`.github/workflows/site.yml`) builds every branch and publishes it as the git ref
`refs/sites/<name>`. On the web server, `sitepull` polls those refs every 2 minutes and serves
them. The server never runs repository code and holds no GitHub credential: the repositories are
public and it reads them anonymously.

| Branch | Served at | Directory on the server |
|---|---|---|
| default (`master`) | `https://<slug>.terradoc.org/` (after cutover) and `https://previews.terradoc.org/<slug>/_prod/` | `/srv/sites/<slug>/_prod/current` |
| any other | `https://previews.terradoc.org/<slug>/<name>/` | `/srv/sites/<slug>/<name>/current` |

`https://previews.terradoc.org/<slug>/` lists what is served. Every preview response carries
`X-Robots-Tag: noindex`.

## What it checks before serving a ref

- `.release.json` must name the branch and its **current tip**. A ref built from an older commit,
  or pushed by hand, waits; it is served only once CI catches up.
- The tree may hold only regular files, with no `..` and no control characters in paths, at most
  20 000 files and 2 GiB (production) or 1 GiB (preview).
- Two branches that map to the same name (`Foo-Bar`, `foo-bar`) are both ignored.
- After switching, it fetches 5 URLs through Caddy (`http://127.0.0.1:8088`, the same routes as
  `previews.terradoc.org`) and compares them byte for byte with the release. If Caddy answers
  wrongly, it switches back and that ref is **never retried**. If Caddy is down, it switches back
  and tries again on the next round.

Unchanged files are hardlinked from the previous release. It keeps 10 production releases and 2
per preview, at most 5 previews per repository (the oldest goes), and opens no new preview
when the disk is over 80% full. A preview goes away 10 minutes after its branch and ref are
both gone (24 h if only the branch is gone).

## Commands (as `tiago` on the server)

```sh
sitectl status                         # what is served, holds, refusals; heartbeat (stale > 15 min)
sitectl log                            # the poller's recent log
sitectl pull                           # one round now
sitectl list enawenenawe [NAME]        # kept releases (NAME defaults to _prod)
sitectl rollback enawenenawe [NAME] [RELEASE]   # serve an older release and HOLD
sitectl release enawenenawe [NAME]     # end the hold: the branch's latest build goes out
sitectl retry enawenenawe [NAME]       # forget refusals, so those refs are tried again
sitectl purge enawenenawe PATH         # delete a file from every kept release (consent withdrawal)
sitectl import enawenenawe < site.tar.gz        # break-glass: serve a tarball, and HOLD
```

A rollback holds until `sitectl release`, so the next push does not undo it. `purge` is not
enough by itself: also remove the file from the repository, or the next build brings it back.
If the file was ever pushed to GitHub, only GitHub Support can erase it from history.

## Install or update

```sh
scp -r server/ tiago@<host>:sitepull-install/
ssh tiago@<host> 'cd sitepull-install && sudo ./setup.sh'
```

`setup.sh` is idempotent. It creates the system user `sites` (no login shell, no sudo) and
`/srv/sites`, installs the root-owned scripts in `/usr/local/lib/sitepull` and `/usr/local/bin/sitectl`,
and enables `sitepull.timer`. It creates `/etc/sitepull/sites.ini` from `sites.ini.example` only if
that file is missing. Caddy is configured by hand from `Caddyfile.sites`: add a slug to its
regexp when a site moves over. Caddy runs with `admin off`, so after `caddy validate` restart it
(never reload).

The service runs sandboxed (`ProtectSystem=strict`, `ReadWritePaths=/srv/sites`, private
`/tmp`, no new privileges, no capabilities). `sitectl` runs the same script via `sudo -u sites`.

## Layout

```
/srv/sites/
  cache/<slug>.git           bare cache of fetched site commits (gc weekly)
  state/<slug>.json          per target: deployed release, refused refs, hold
  heartbeat.json             last round: time, boot id, errors
  <slug>/<name>/releases/<id>/   one directory per release (<UTC time>-<commit>)
  <slug>/<name>/current      symlink to the served release, switched atomically
  www/<slug>/<name>          symlink to ../../<slug>/<name>/current (Caddy's root for previews)
  www/<slug>/index.html      list of previews
```

Tests: `tests/test_sitepull.py` (a local bare repository stands in for GitHub, a local HTTP
server for Caddy).
