"""Inspect public recipes from an existing local version JAR; no network or game controls."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from minekin_core.adapters.public_recipe_archive import load_recipe_knowledge


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--sha256")
    parser.add_argument("--product", required=True)
    args = parser.parse_args()
    try:
        knowledge = load_recipe_knowledge(
            args.archive, game_version=args.version, expected_sha256=args.sha256
        )
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Recipe knowledge refused: {exc}\n")
    print(
        json.dumps(
            {
                "source": "PUBLIC_VERSION_ARCHIVE",
                "game_version": knowledge.game_version,
                "archive_sha256": knowledge.archive_sha256,
                "expected_digest_matched": knowledge.digest_matched,
                "player_recipe_unlocked": "unknown",
                "current_server_compatibility": "unknown",
                "current_materials": "not_observed",
                "runtime_planner_connected": False,
                "crafting_recipes_loaded": len(knowledge.recipes),
                "public_item_tags_loaded": len(knowledge.item_tags),
                "unsupported_types": dict(knowledge.unsupported_types),
                "recipes": [asdict(recipe) for recipe in knowledge.for_product(args.product)],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
