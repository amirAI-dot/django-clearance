"""
What the documentation site changes in a page as it is built.

The library's docstrings introduce an example as reStructuredText does - a
paragraph ending in ``::`` - and the example is shown as code. The second
colon is the marker, not the sentence's, so it is not shown.
"""

import re
from typing import Any

_MARKER = re.compile(r'::(</p>)')


def on_page_content(html: str, **kwargs: Any) -> str:
    return _MARKER.sub(r':\1', html)
