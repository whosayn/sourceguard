from dataclasses import dataclass
from typing import Sequence
from typing import Optional, Union


@dataclass
class BanRule:
    pattern: str
    description: Union[str, Sequence[str]]
    excluded_paths: Optional[Sequence[str]] = None
    id: Optional[str] = None
    severity: str = "error"
