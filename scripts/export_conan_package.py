#!/usr/bin/env python3
"""Copy the package folder produced by `conan create` into an artifact folder."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def run_json(args: list[str]) -> dict:
    result = subprocess.run(args, check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


def first_package_ref(data: dict, recipe_ref: str) -> str:
    packages = (
        data.get("Local Cache", {})
        .get(recipe_ref, {})
        .get("revisions", {})
    )
    for recipe_revision_id, recipe_revision in packages.items():
        package_entries = recipe_revision.get("packages", {})
        for package_id, package_data in package_entries.items():
            package_revisions = package_data.get("revisions", {})
            for package_revision_id in package_revisions:
                return f"{recipe_ref}#{recipe_revision_id}:{package_id}#{package_revision_id}"
    raise RuntimeError(f"No local package found for {recipe_ref}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", default="forge-output/package")
    args = parser.parse_args()

    recipe_ref = f"{args.name}/{args.version}"
    package_list = run_json(["conan", "list", f"{recipe_ref}:*", "--format=json"])
    package_ref = first_package_ref(package_list, recipe_ref)
    package_path = Path(
        subprocess.run(
            ["conan", "cache", "path", package_ref],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
    )

    output = Path(args.output)
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(package_path, output)

    manifest = output.parent / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "recipe_ref": recipe_ref,
                "package_ref": package_ref,
                "package_path": str(package_path),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Exported {package_ref} from {package_path} to {output}")


if __name__ == "__main__":
    main()
