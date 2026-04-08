import base64
import json
import logging

import boto3
import fitz
from mistralai.client import Mistral
from mistralai.client.models import ImageURLChunk

from app.config import settings
from app.models.schemas import PageText

logger = logging.getLogger(__name__)

TEXT_THRESHOLD = 50  # minimum chars to consider a page as having a text layer


def extract_text_from_pdf(
    pdf_bytes: bytes,
    job_id: str | None = None,
    filename: str | None = None,
) -> list[PageText]:
    """Extract text from all pages using PyMuPDF, falling back to configured OCR provider."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[PageText] = []
    ocr_needed: list[int] = []

    for page in doc:
        text = page.get_text("text").strip()
        if len(text) >= TEXT_THRESHOLD:
            pages.append(PageText(page_num=page.number, text=text, used_ocr=False))
        else:
            pages.append(PageText(page_num=page.number, text="", used_ocr=True))
            ocr_needed.append(page.number)

    if ocr_needed:
        provider = settings.ocr_provider
        logger.info(
            "Pages %s need OCR, using %s for %s", ocr_needed, provider, filename or "unknown"
        )
        if provider == "textract":
            _ocr_pages_textract(doc, pages, ocr_needed)
        else:
            _ocr_pages_mistral(doc, pages, ocr_needed)

    doc.close()

    # Persist raw OCR results to S3 for future reprocessing
    if ocr_needed and job_id:
        _save_ocr_results_to_s3(pages, job_id, filename)

    return pages


# ---------------------------------------------------------------------------
# AWS Textract (Detect Document Text — synchronous)
# ---------------------------------------------------------------------------


def _ocr_pages_textract(
    doc: fitz.Document, pages: list[PageText], page_nums: list[int]
) -> None:
    """Use AWS Textract DetectDocumentText to extract text from scanned pages."""
    client = boto3.client("textract", region_name=settings.aws_region)

    for page_num in page_nums:
        page = doc[page_num]
        pixmap = page.get_pixmap(dpi=300)
        image_bytes = pixmap.tobytes("png")

        try:
            response = client.detect_document_text(
                Document={"Bytes": image_bytes}
            )
            text = _textract_response_to_text(response)
            pages[page_num] = PageText(
                page_num=page_num,
                text=text,
                used_ocr=True,
                ocr_provider="textract",
                raw_ocr_result=_clean_textract_response(response),
            )
        except Exception:
            logger.exception("Textract OCR failed for page %d", page_num)


def _clean_textract_response(response: dict) -> dict:
    """Strip HTTP metadata from Textract response, keeping only document data."""
    return {
        k: v for k, v in response.items()
        if k in ("Blocks", "DocumentMetadata", "DetectDocumentTextModelVersion")
    }


def _textract_response_to_text(response: dict) -> str:
    """Extract plain text from a Textract DetectDocumentText response.

    Concatenates all LINE blocks in reading order (Textract returns them
    top-to-bottom, left-to-right by default).
    """
    lines: list[str] = []
    for block in response.get("Blocks", []):
        if block["BlockType"] == "LINE":
            lines.append(block.get("Text", ""))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Mistral OCR
# ---------------------------------------------------------------------------


def _ocr_pages_mistral(
    doc: fitz.Document, pages: list[PageText], page_nums: list[int]
) -> None:
    """Use Mistral OCR API to extract text from scanned pages."""
    if not settings.mistral_api_key:
        logger.warning("Mistral API key not set, skipping OCR for scanned pages")
        return

    client = Mistral(api_key=settings.mistral_api_key)

    for page_num in page_nums:
        page = doc[page_num]
        pixmap = page.get_pixmap(dpi=300)
        image_bytes = pixmap.tobytes("png")

        try:
            b64 = base64.b64encode(image_bytes).decode("ascii")
            result = client.ocr.process(
                model="mistral-ocr-latest",
                document=ImageURLChunk(
                    image_url=f"data:image/png;base64,{b64}",
                ),
            )
            extracted_text = "\n".join(
                p.markdown for p in result.pages if p.markdown
            )
            # Serialize Mistral response to dict for storage
            raw = result.model_dump() if hasattr(result, "model_dump") else str(result)
            pages[page_num] = PageText(
                page_num=page_num,
                text=extracted_text,
                used_ocr=True,
                ocr_provider="mistral",
                raw_ocr_result=raw,
            )
        except Exception:
            logger.exception("Mistral OCR failed for page %d", page_num)


# ---------------------------------------------------------------------------
# OCR result persistence
# ---------------------------------------------------------------------------


def _save_ocr_results_to_s3(
    pages: list[PageText], job_id: str, filename: str | None
) -> None:
    """Save raw OCR results to S3 for future reprocessing.

    Structure: s3://{bucket}/{job_id}/{filename}/{provider}/page_{N}.json
    """
    bucket = settings.s3_ocr_results_bucket
    if not bucket:
        return

    s3 = boto3.client("s3", region_name=settings.aws_region)
    safe_filename = (filename or "unknown").replace("/", "_").replace("\\", "_")

    for page in pages:
        if not page.used_ocr or page.raw_ocr_result is None:
            continue

        provider = page.ocr_provider or "unknown"
        key = f"{job_id}/{safe_filename}/{provider}/page_{page.page_num:04d}.json"

        body = (
            json.dumps(page.raw_ocr_result, default=str, ensure_ascii=False)
            if isinstance(page.raw_ocr_result, dict)
            else json.dumps({"raw": page.raw_ocr_result}, ensure_ascii=False)
        )

        try:
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=body.encode("utf-8"),
                ContentType="application/json",
            )
            logger.info("Saved OCR result to s3://%s/%s", bucket, key)
        except Exception:
            logger.exception("Failed to save OCR result to S3: %s", key)
