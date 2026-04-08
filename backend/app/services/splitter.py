"""PDF splitting by page ranges.

Takes the original PDF bytes and a list of document segments (start/end
pages), and produces separate PDF byte streams for each segment.
"""

import io

import fitz

from app.models.schemas import DocumentSegment


def split_pdf(pdf_bytes: bytes, segments: list[DocumentSegment]) -> list[bytes]:
    """Split a PDF into separate byte streams based on document segments."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    result: list[bytes] = []

    for segment in segments:
        new_doc = fitz.open()
        new_doc.insert_pdf(
            doc,
            from_page=segment.start_page,
            to_page=segment.end_page,
        )
        buffer = io.BytesIO()
        new_doc.save(buffer)
        new_doc.close()
        result.append(buffer.getvalue())

    doc.close()
    return result
