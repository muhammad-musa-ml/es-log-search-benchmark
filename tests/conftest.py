"""Put the artifact root on the import path, and say why it is not a package.

The modules under test - `canonkit`, `gate`, `esbench.guards` - live at the
repository root, which is not on `sys.path` when pytest is pointed at
`tests/`. Inserting it here rather than shipping a `setup.py` keeps the artifact
a directory someone can clone and run, rather than a package they must install
first.

NOTHING HERE IMPORTS THE ELASTICSEARCH CLIENT, and that is a constraint rather
than a coincidence. The suite is run with an interpreter that does not have it:
the benchmark itself runs on the host Python where the hash-pinned client is
installed, while these tests run under the tooling environment. So the modules
they reach for - `esbench.guards`, `esbench.queries`, `esbench.mappings` - all
stop at the standard library, and `esbench.bench` and `esbench.load`, which do
not, are never imported here.
"""
from __future__ import annotations

import os
import sys

ARTIFACT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if ARTIFACT_ROOT not in sys.path:
    sys.path.insert(0, ARTIFACT_ROOT)
