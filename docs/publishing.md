# Publishing a terradoc site from GitHub

terradoc ships a reusable GitHub Actions workflow,
[`.github/workflows/site.yml`](../.github/workflows/site.yml). A platform repository calls it, and
from then on **every push to every branch is validated, built and published**, with no manual step.

## What happens on a push

1. The terradoc version pinned in the repository's `requirements.txt` is installed.
2. `terradoc build` runs `terradoc check` first. Every error becomes an **annotation** on the
   commit, next to the file and line, and nothing is published.
3. `terradoc guard` compares the new build with the release it replaces. It blocks a module losing
   more than 20 records or 10 % of them, more than 25 % against the fixed baseline (if one exists),
   or more than max(10, 5 %) of the published files. To shrink on purpose, put a line
   `confirma-reducao` in a commit message of that push, or run the workflow by hand with
   "confirm shrink" ticked.
4. The built site is published as the git ref `refs/sites/<name>`. This is not a branch, so normal
   clones never download it. The server polls these refs every couple of minutes
   ([`server/`](../server/README.md)):
   - the default branch (`master`) → `https://<repo>.terradoc.org/`
   - any other branch → `https://previews.terradoc.org/<repo>/<name>/`, where `<name>` is the
     branch name lowercased, with anything other than letters, digits and `-` turned into `-`
     (`FFGerardi-patch-1` → `ffgerardi-patch-1`). Two branches that map to the same name are both
     refused until one is renamed.
5. If anything fails, an issue titled **"Publicação falhou: &lt;branch&gt;"** is opened, or updated if
   one is already open. It explains each problem in Portuguese and English, links the run, and
   @-mentions the people listed in `.github/CODEOWNERS` for the failing files, plus whoever pushed.
   The next successful run closes it. **The live site keeps its last good version.**
6. Deleting a branch deletes its preview (about 10 minutes later) and closes its issue.

The normalised data bundle is kept as a run artifact (30 days). It is not published.

## The caller (copy into `.github/workflows/site.yml` of a platform repository)

```yaml
name: site
on:
  push:
    branches: ['**']
  delete:
  workflow_dispatch:
    inputs:
      confirm_shrink:
        description: "Allow this release to shrink (records or files)"
        type: boolean
        default: false
permissions:
  contents: write   # push refs/sites/*
  issues: write     # failure issues
jobs:
  site:
    # Pin by commit SHA (a tag can be moved), matching the terradoc in requirements.txt.
    uses: plataformasindigenas/terradoc/.github/workflows/site.yml@<commit-sha>  # v0.12.0
    with:
      confirm_shrink: ${{ inputs.confirm_shrink || false }}
```

Also add `.github/CODEOWNERS`, for example:

```text
*                    @owner
data/encyclopedia/   @owner
data/dictionary.tsv  @lexicographer
```

## Trust model

Anyone who can push to the repository can publish to production. GitHub cannot restrict who
pushes `refs/sites/*`, and a writer could also edit the workflow. Write access therefore means
publishing rights. The server serves a ref only if its `.release.json` names the current tip of
the matching branch, so stale or orphaned refs are ignored, and only if the tree holds nothing but
regular files.

Anything pushed to any branch of a public repository is public. That includes previews, and
deleting a branch does not erase the commits: only GitHub Support can purge them. **Material
whose consent is pending must never be pushed.**
