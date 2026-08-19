from pypdf import PdfReader


class PDFParser:
    """One chunk per page. Page number is the citation anchor (spec section
    5: 'page/sheet' traceability) — pypdf gives text extraction, not table
    structure, so dense financial tables in PDFs will need a better parser
    later if that turns out to matter in practice."""

    def parse(self, path: str) -> list[dict]:
        reader = PdfReader(path)
        chunks = []

        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                chunks.append({"content": text.strip(), "location": {"page": i + 1}})

        return chunks
