"""Legacy module-level global state – kept for backward compatibility only.

These globals were the original dependency-passing mechanism before ``Config`` and
``ApplicationContext`` were introduced.  New code should use dependency injection
via ``Config`` or ``ApplicationContext`` instead of reading/writing these globals.

Why this module still exists: some CLI code paths and older test fixtures reference
these globals directly.  Removing them would be a breaking change requiring a
coordinated refactor of ``cli.py`` and the test suite.  The migration target is
``core.context.ApplicationContext``.
"""

from argparse import Namespace
from typing import Any

_ = None
args: Namespace | None = None
csvwriter: Any = None
csv_file_handle: Any = None
logger = None
output_format: str = "csv"
output_file_path: str | None = None
output_writer: Any = None
