import csv


class CSVParser:
    """One chunk per row, rendered as `column: value` pairs so it reads
    naturally in an LLM prompt while `location` keeps the exact row/column
    for citation."""

    def parse(self, path: str) -> list[dict]:
        chunks = []

        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)

            for row_index, row in enumerate(reader):
                content = "; ".join(f"{col}: {val}" for col, val in row.items())
                chunks.append(
                    {
                        "content": content,
                        "location": {"row": row_index + 2, "columns": list(row.keys())},
                    }
                )

        return chunks
