"""Index data generation and file copying for terradoc."""

import json
import shutil

from terradoc.config import TerradocConfig


def generate_index(counts: dict[str, int], config: TerradocConfig):
    """Generate index JSON with module counts."""
    print("=== Generating Index Data ===")

    index_data = {
        "meta": {"description": f"{config.project_name} - Index data"},
        "data": [
            {f"{name}_count": count for name, count in counts.items()}
        ],
    }

    output_file = config.data_dir / "index.json"
    output_file.write_text(json.dumps(index_data, indent=2), encoding="utf-8")

    print(f"  Exported to {output_file}")


def copy_data_to_docs(config: TerradocConfig):
    """Copy generated data files to docs/ for fetch-based loading."""
    if config.is_module_enabled("dictionary"):
        src = config.data_dir / "dictionary.json"
        dst = config.docs_dir / "dictionary-data.json"
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  Copied {src.name} → {dst}")

    if config.is_module_enabled("corpus"):
        src = config.data_dir / "corpus.json"
        dst = config.docs_dir / "corpus-data.json"
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  Copied {src.name} → {dst}")

    if config.is_module_enabled("encyclopedia"):
        src = config.data_dir / "encyclopedia_index.json"
        dst = config.docs_dir / "encyclopedia-data.json"
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  Copied {src.name} → {dst}")

        if config.is_graph_enabled("encyclopedia"):
            src = config.data_dir / "encyclopedia_graph.json"
            dst = config.docs_dir / "encyclopedia-graph.json"
            if src.exists():
                shutil.copy2(src, dst)
                print(f"  Copied {src.name} → {dst}")
