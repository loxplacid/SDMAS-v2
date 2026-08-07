"""Shared SPDX license-expression handling for emitters and validators.

The generator deliberately does not ship a full SPDX license list database.
Instead it recognises a compact set of common ids plus the special values
``NOASSERTION``/``NONE``.  Anything else is treated as *unresolvable*:

* emitters downgrade the declared license to ``NOASSERTION`` and preserve
  the original text verbatim in a package comment / property, so no
  information is lost while the document stays schema-valid;
* the analyser flags the raw value as a ``custom_license`` finding so it is
  visible to consumers.
"""

from __future__ import annotations

import re

#: Common SPDX ids the generator recognises verbatim.
COMMON_SPDX_IDS = frozenset(
    """MIT Apache-2.0 BSD-2-Clause BSD-3-Clause ISC GPL-2.0-only GPL-2.0-or-later
    GPL-3.0-only GPL-3.0-or-later LGPL-2.0-only LGPL-2.0-or-later LGPL-2.1-only
    LGPL-2.1-or-later LGPL-3.0-only LGPL-3.0-or-later MPL-2.0 AGPL-3.0-only
    AGPL-3.0-or-later 0BSD CC0-1.0 CC-BY-4.0 CC-BY-SA-4.0 Unlicense Python-2.0
    Zlib BSL-1.0 EPL-2.0 OFL-1.1 Artistic-2.0 WTFPL PostgreSQL Apache-1.1
    BlueOak-1.0.0 MIT-0 BSD-1-Clause BSD-4-Clause AFL-3.0 CDDL-1.0 CDDL-1.1
    CC-BY-3.0 EPL-1.0 GPL-1.0-only OpenSSL Ruby X11 W3C ZPL-2.1
    Unicode-DFS-2016 BSL-1.0 NCSA HPND Vim UPL-1.0""".split()
)

#: SPDX special values that are always legal in any expression position.
SPECIAL = frozenset({"NOASSERTION", "NONE"})


def is_valid_expression(expr: str) -> bool:
    """True when *expr* is a well-formed SPDX expression over recognised ids.

    Accepts compound expressions (``A AND B``, ``A OR B``, ``A WITH X``) and
    parenthesised grouping (npm writes ``(MIT OR CC0-1.0)``); parentheses are
    grouping, not part of the ids.
    """
    if expr in SPECIAL:
        return True
    tokens = re.split(r"\s+(?:AND|OR|WITH)\s+", expr)
    tokens = [t.strip("() ") for t in tokens]
    return bool(tokens) and all(t in COMMON_SPDX_IDS for t in tokens)
