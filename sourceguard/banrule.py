from dataclasses import dataclass
from typing import Sequence
from typing import Optional


@dataclass
class BanRule:
    pattern: str
    description: Sequence[str]
    excluded_paths: Optional[Sequence[str]] = None
