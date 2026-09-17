"""rimi.tests — run the test cases of the rimi. convention against several models.

The package is split the way the specification is: cases are loaded and validated
(`loader`), executed against providers (`runner`, `providers`, `cache`), judged by
deterministic `checks` first and by a `judge` only when no typed check fits, then
turned into a report (`report`). Everything an execution produces is hashed and
chained (`proof`) so that a third party can verify a campaign offline.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
