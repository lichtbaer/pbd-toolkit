from argparse import Namespace
from typing import Any

_ = None
args: Namespace | None = None
csvwriter: Any = None
csv_file_handle: Any = None
logger = None
output_format: str = "csv"
output_file_path: str | None = None
