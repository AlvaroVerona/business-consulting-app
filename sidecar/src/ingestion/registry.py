from src.ingestion.csv_parser import CSVParser
from src.ingestion.docx_parser import DocxParser
from src.ingestion.pdf_parser import PDFParser
from src.ingestion.text_parser import TextParser
from src.ingestion.xlsx_parser import XLSXParser

PARSERS_BY_EXTENSION = {
    ".txt": TextParser(),
    ".md": TextParser(),
    ".csv": CSVParser(),
    ".docx": DocxParser(),
    ".pdf": PDFParser(),
    ".xlsx": XLSXParser(),
}


class UnsupportedFileType(ValueError):
    pass


def parse_document(path: str, extension: str) -> list[dict]:
    parser = PARSERS_BY_EXTENSION.get(extension.lower())

    if parser is None:
        raise UnsupportedFileType(
            f"No parser registered for '{extension}'. Supported: {sorted(PARSERS_BY_EXTENSION)}"
        )

    return parser.parse(path)
