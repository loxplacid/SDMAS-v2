"""SDMAS SBOM generator.

Produces software bills of materials (SPDX 2.3 and CycloneDX 1.5) from the
repository's dependency lock files (``uv.lock`` / ``requirements.txt`` for
Python, ``package-lock.json`` for Node) plus optional installed-environment
augmentation (``*.dist-info`` METADATA/RECORD).

Design goals:

* **Deterministic output** — every list is sorted, identifiers are derived
  from content via UUIDv5, and the ``created`` timestamp honours
  ``SOURCE_DATE_EPOCH`` so builds are reproducible.  Without
  ``SOURCE_DATE_EPOCH`` the timestamp is wall-clock (spec-compliant, not
  byte-reproducible — see docs/SBOM_VALIDATION.md).
* **Defensive parsing** — a corrupt lock file produces warnings, never a
  crash, so a partially-installed or mixed-manager environment still yields
  a usable (and clearly qualified) SBOM.
* **Stdlib only** — no runtime dependencies; runs on Python >= 3.11
  (``tomllib``).

The canonical entry point is ``python -m sbom.cli`` (wrapped by
``scripts/python_sbom.sh`` and ``scripts/node_sbom.sh``).
"""

__version__ = "1.0.0"
