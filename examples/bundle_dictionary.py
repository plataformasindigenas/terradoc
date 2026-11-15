"""An independent consumer of terradoc's export bundle: renders the dictionary.

Uses only the Python standard library and reads only the bundle (manifest.json and
dictionary.json), never terradoc itself. It exists to keep the bundle honest: if a
terradoc change breaks what another renderer would need, the test that runs this
script fails. See docs/bundle.md.

    python examples/bundle_dictionary.py BUNDLE_DIR OUT.html
"""

import html
import json
import sys
from pathlib import Path

SUPPORTED = {"0-experimental"}


def main(bundle: Path, out: Path) -> int:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("bundle_schema") not in SUPPORTED:
        print(f"unsupported bundle_schema {manifest.get('bundle_schema')!r}", file=sys.stderr)
        return 2
    if "dictionary" not in manifest.get("modules", {}):
        print("the bundle has no dictionary module", file=sys.stderr)
        return 2
    doc = json.loads((bundle / "dictionary.json").read_text(encoding="utf-8"))
    records = doc["data"]
    if len(records) != manifest["modules"]["dictionary"]:
        print("manifest record count does not match dictionary.json", file=sys.stderr)
        return 1
    rows = []
    for r in sorted(records, key=lambda r: (r.get("entry") or "").lstrip("-").casefold()):
        ipa = f' <span class="ipa">[{html.escape(r["ipa"])}]</span>' if r.get("ipa") else ""
        rows.append(f'<li id="{html.escape(str(r["id"]))}"><b>{html.escape(r.get("entry") or "")}</b>{ipa}'
                    f' — {html.escape(str(r.get("definition") or r.get("definition_pt") or ""))}</li>')
    out.write_text("<!doctype html>\n<meta charset=\"utf-8\">\n"
                   f"<title>{html.escape(manifest.get('project', ''))}: dictionary</title>\n"
                   f"<ul>\n" + "\n".join(rows) + "\n</ul>\n", encoding="utf-8")
    print(f"{len(rows)} entries → {out}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
