# chimerax-copick 2.0 alpha release runbook

Alpha bundles are GitHub prereleases only. Do not submit an alpha to the public ChimeraX Toolshed.

## Fixed initial inputs

- `copick==2.0.0a1`
- `copick-shared-ui==2.0.0a1`; wheel SHA-256
  `c56d06ee53cffc7cda56a916d480793198e2311b099e7965c132ea27e43f6515`
- `ChimeraX-OME-Zarr==1.0.0a1`; wheel SHA-256
  `fd9f0c49505237d200c65afafb24a088ee1f7eb8f8ab29e84991a358354684b0`
- `zarr==3.1.6` for the minimum-stack run
- ChimeraX Daily 1.13 with Core `>=1.13.dev202608172052` and embedded Python 3.14

These versions and hashes are the release record for the initial alpha stack. Change them only after the complete
downstream matrix passes with a later published artifact.

## Build the tagged source

1. Merge the Release Please PR for `v2.0` only after its version is exactly `2.0.0-alpha.N` and its release is
   marked as a GitHub prerelease.
2. Check out the resulting tag in a clean worktree and record `git rev-parse HEAD`.
3. In ChimeraX Daily 1.13, run `devel build <checkout>`.
4. Locate the single generated wheel under `<checkout>/dist/` and calculate `shasum -a 256 <wheel>`.
5. Run `python scripts/inspect_bundle.py <wheel> --expected-version 2.0.0aN` with the `packaging` library
   available. Record its output.

Generic `uv build` is not a supported bundle build: ChimeraX's bundle builder supplies the dynamic classifier
metadata. The Python floor is static in `pyproject.toml` so the pure-Python bundle keeps `Requires-Python: >=3.14`
instead of the builder's generic ChimeraX 1.0 floor.

## Install and validate in an isolated Daily profile

Use a new ChimeraX user profile reserved for this release candidate. Download
`chimerax_ome_zarr-1.0.0a1-py3-none-any.whl` from its `v1.0.0-alpha.1` GitHub release and verify its SHA-256 against
the value under **Fixed initial inputs** above. Install that wheel first with ChimeraX `toolshed install`. Install the
chimerax-copick wheel second with dependency resolution enabled; confirm the resolver selects the exact copick and
shared-UI alphas above.

Run `scripts/installed_bundle_smoke.py` with the embedded Python, then start the Copick tool and verify every
registered `copick` command is discoverable. Execute the native, local-fixture, backend, and gallery/worker gates
from Epic #85 and retain their logs with:

- ChimeraX/Core and embedded Python versions;
- every package version printed by the installed-bundle smoke;
- upstream and chimerax-copick wheel SHA-256 values;
- the exact Git tag and commit; and
- named results for local, S3-compatible, Secure Shell, ML Croissant, portal, and optional SMB coverage.

## Attach and roll back

Attach only the wheel and a matching `.sha256` file that passed the installed-artifact matrix to the GitHub
prerelease. If any required gate fails, leave the prerelease clearly marked as unqualified (or remove the broken
asset), uninstall the candidate from the isolated profile, and discard that profile. Fixes use the next
`2.0.0-alpha.N`; never replace a previously published artifact under the same version.
