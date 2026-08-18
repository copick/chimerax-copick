"""Inspect release-wheel metadata without importing the ChimeraX bundle."""

from __future__ import annotations

import argparse
import email
import sys
import zipfile
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version


EXPECTED_REQUIREMENTS = {
    "chimerax-core": ">=1.13.dev202608172052",
    "chimerax-ome-zarr": ">=1.0.0a1,<2",
    "copick": ">=2.0.0a1,<3",
    "copick-shared-ui": ">=2.0.0a1,<3",
    "numpy": ">=2.0.2",
}
FORBIDDEN_DIRECT_REQUIREMENTS = {"aiohttp", "hatchling", "pydantic", "s3fs"}


def inspect_wheel(path: Path, expected_version: str | None) -> None:
    with zipfile.ZipFile(path) as archive:
        metadata_files = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_files) != 1:
            raise ValueError(f"expected one METADATA file, found {metadata_files}")
        metadata = email.message_from_bytes(archive.read(metadata_files[0]))

    if canonicalize_name(metadata["Name"]) != "chimerax-copick":
        raise ValueError(f"unexpected distribution name: {metadata['Name']}")
    if expected_version is not None and Version(metadata["Version"]) != Version(expected_version):
        raise ValueError(f"expected version {expected_version}, found {metadata['Version']}")
    if metadata["Requires-Python"] != ">=3.14":
        raise ValueError(f"expected Requires-Python >=3.14, found {metadata['Requires-Python']}")

    requirements = {
        canonicalize_name(requirement.name): requirement
        for requirement in map(Requirement, metadata.get_all("Requires-Dist", []))
        if requirement.marker is None or "extra" not in str(requirement.marker)
    }
    for name, specifier in EXPECTED_REQUIREMENTS.items():
        requirement = requirements.get(name)
        if requirement is None or requirement.specifier != SpecifierSet(specifier):
            raise ValueError(f"expected {name}{specifier}, found {requirement}")
    unexpected = FORBIDDEN_DIRECT_REQUIREMENTS.intersection(requirements)
    if unexpected:
        raise ValueError(f"unexpected direct runtime requirements: {sorted(unexpected)}")

    print(f"validated {path.name}: chimerax-copick {metadata['Version']}, Python {metadata['Requires-Python']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--expected-version")
    arguments = parser.parse_args(argv)
    try:
        inspect_wheel(arguments.wheel, arguments.expected_version)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
