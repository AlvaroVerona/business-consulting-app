class TextParser:
    """Handles .txt and .md: one chunk per non-empty paragraph."""

    def parse(self, path: str) -> list[dict]:
        with open(path, encoding="utf-8") as f:
            text = f.read()

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        return [
            {"content": p, "location": {"paragraph": i + 1}}
            for i, p in enumerate(paragraphs)
        ]
