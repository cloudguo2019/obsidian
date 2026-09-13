"""Stage 8 research engine for HD-ANCHOR-001.

The package is intentionally free of performance-reporting helpers.  It provides
only the state machine, account ledger, dated tax/fee schedules, and the frozen
T-close to T+1-close execution semantics needed by the Stage 8 gates.
"""

from .stage8_engine import *  # noqa: F401,F403

