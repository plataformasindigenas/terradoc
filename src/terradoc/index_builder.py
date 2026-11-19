"""Index data generation and file copying for terradoc."""

import json

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

    output_file = config.bundle_dir / "index.json"
    output_file.write_text(json.dumps(index_data, indent=2), encoding="utf-8")

    print(f"  Exported to {output_file}")
