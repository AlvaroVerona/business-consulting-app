from typing import Protocol


class Parser(Protocol):
    """A parser turns one source file into an ordered list of citable
    chunks: {"content": str, "location": dict | None}. `location` carries
    whatever the format allows (page, sheet, row/column range) so a Finding
    built from this chunk can cite it precisely (spec section 5)."""

    def parse(self, path: str) -> list[dict]:
        ...
