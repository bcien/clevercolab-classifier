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
    skip_ocr: bool = False,
) -> list[PageText]:
    """Extract text from all pages using PyMuPDF, falling back to configured OCR provider.

    Args:
        pdf_bytes: Raw PDF file content.
        job_id: Job identifier (used for persisting OCR results).
        filename: Original filename (for logging and result storage).
        skip_ocr: If True, only run PyMuPDF and mark scanned pages as
            ``used_ocr=True`` without calling an external OCR provider.
            Used by the vision pipeline which handles OCR in the LLM call.
    """
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

    if ocr_needed and not skip_ocr:
        provider = settings.ocr_provider
        logger.info(
            "Pages %s need OCR, using %s for %s", ocr_needed, provider, filename or "unknown"
        )
        _OCR_DISPATCH[provider](doc, pages, ocr_needed)
    elif ocr_needed and skip_ocr:
        logger.info(
            "Pages %s need OCR but skipping (vision path) for %s",
            ocr_needed,
            filename or "unknown",
        )

    doc.close()

    # Persist raw OCR results for future reprocessing
    if ocr_needed and job_id:
        if settings.s3_ocr_results_bucket:
            _save_ocr_results_to_s3(pages, job_id, filename)
        elif settings.local_output_dir:
            _save_ocr_results_local(pages, job_id, filename)

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
# OpenAI Vision OCR
# ---------------------------------------------------------------------------


def _ocr_pages_openai(
    doc: fitz.Document, pages: list[PageText], page_nums: list[int]
) -> None:
    """Use OpenAI GPT vision to extract text from scanned pages."""
    if not settings.openai_api_key:
        logger.warning("OpenAI API key not set, skipping OCR for scanned pages")
        return

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)

    for page_num in page_nums:
        page = doc[page_num]
        pixmap = page.get_pixmap(dpi=300)
        image_bytes = pixmap.tobytes("png")

        try:
            b64 = base64.b64encode(image_bytes).decode("ascii")
            response = client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Extract all text from this document image. "
                                    "Return only the raw text, preserving the "
                                    "original layout as much as possible. "
                                    "Do not add commentary."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{b64}",
                                },
                            },
                        ],
                    }
                ],
            )
            text = response.choices[0].message.content or ""
            raw = {
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }
                if response.usage
                else None,
            }
            pages[page_num] = PageText(
                page_num=page_num,
                text=text.strip(),
                used_ocr=True,
                ocr_provider="openai",
                raw_ocr_result=raw,
            )
        except Exception:
            logger.exception("OpenAI OCR failed for page %d", page_num)


# ---------------------------------------------------------------------------
# Google Gemini Vision OCR
# ---------------------------------------------------------------------------


def _ocr_pages_google(
    doc: fitz.Document, pages: list[PageText], page_nums: list[int]
) -> None:
    """Use Google Gemini vision to extract text from scanned pages."""
    if not settings.google_api_key:
        logger.warning("Google API key not set, skipping OCR for scanned pages")
        return

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.google_api_key)

    for page_num in page_nums:
        page = doc[page_num]
        pixmap = page.get_pixmap(dpi=300)
        image_bytes = pixmap.tobytes("png")

        try:
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/png",
            )
            response = client.models.generate_content(
                model=settings.google_model,
                contents=[
                    "Extract all text from this document image. "
                    "Return only the raw text, preserving the "
                    "original layout as much as possible. "
                    "Do not add commentary.",
                    image_part,
                ],
                config=types.GenerateContentConfig(
                    max_output_tokens=4096,
                ),
            )
            text = response.text or ""
            raw = {
                "model": settings.google_model,
                "usage_metadata": response.usage_metadata.model_dump()
                if response.usage_metadata
                and hasattr(response.usage_metadata, "model_dump")
                else None,
            }
            pages[page_num] = PageText(
                page_num=page_num,
                text=text.strip(),
                used_ocr=True,
                ocr_provider="google",
                raw_ocr_result=raw,
            )
        except Exception:
            logger.exception("Google Gemini OCR failed for page %d", page_num)


# ---------------------------------------------------------------------------
# Nanonets OCR2+
# ---------------------------------------------------------------------------


def _ocr_pages_nanonets(
    doc: fitz.Document, pages: list[PageText], page_nums: list[int]
) -> None:
    """Use Nanonets OCR2+ API to extract text from scanned pages."""
    if not settings.nanonets_api_key:
        logger.warning("Nanonets API key not set, skipping OCR for scanned pages")
        return

    import httpx

    client = httpx.Client(timeout=120.0)

    for page_num in page_nums:
        page = doc[page_num]
        pixmap = page.get_pixmap(dpi=300)
        image_bytes = pixmap.tobytes("png")

        try:
            response = client.post(
                settings.nanonets_api_url,
                headers={"Authorization": settings.nanonets_api_key},
                files={
                    "file": (
                        f"page_{page_num}.png",
                        image_bytes,
                        "image/png",
                    )
                },
                data={"output_type": "markdown"},
            )
            response.raise_for_status()
            result = response.json()

            # Extract text from Nanonets response
            text = _nanonets_response_to_text(result)
            pages[page_num] = PageText(
                page_num=page_num,
                text=text,
                used_ocr=True,
                ocr_provider="nanonets",
                raw_ocr_result=result,
            )
        except Exception:
            logger.exception("Nanonets OCR failed for page %d", page_num)

    client.close()


def _nanonets_response_to_text(response: dict) -> str:
    """Extract plain text from a Nanonets OCR API response."""
    # Try common response structures
    if "markdown" in response:
        return response["markdown"]
    if "text" in response:
        return response["text"]
    if "result" in response:
        result = response["result"]
        if isinstance(result, str):
            return result
        if isinstance(result, list):
            return "\n".join(
                item.get("text", item.get("markdown", ""))
                for item in result
                if isinstance(item, dict)
            )
    return json.dumps(response, ensure_ascii=False)


# ---------------------------------------------------------------------------
# OCR provider dispatch
# ---------------------------------------------------------------------------

_OCR_DISPATCH = {
    "textract": _ocr_pages_textract,
    "mistral": _ocr_pages_mistral,
    "openai": _ocr_pages_openai,
    "google": _ocr_pages_google,
    "nanonets": _ocr_pages_nanonets,
}


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


def _save_ocr_results_local(
    pages: list[PageText], job_id: str, filename: str | None
) -> None:
    """Save raw OCR results to local filesystem for development.

    Structure: {local_output_dir}/{job_id}/ocr_results/{filename}/{provider}/page_{N}.json
    """
    from pathlib import Path

    base = Path(settings.local_output_dir) / job_id / "ocr_results"
    safe_filename = (filename or "unknown").replace("/", "_").replace("\\", "_")

    for page in pages:
        if not page.used_ocr or page.raw_ocr_result is None:
            continue

        provider = page.ocr_provider or "unknown"
        out_dir = base / safe_filename / provider
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"page_{page.page_num:04d}.json"

        body = (
            json.dumps(page.raw_ocr_result, default=str, ensure_ascii=False)
            if isinstance(page.raw_ocr_result, dict)
            else json.dumps({"raw": page.raw_ocr_result}, ensure_ascii=False)
        )

        try:
            out_path.write_text(body, encoding="utf-8")
            logger.info("Saved OCR result to %s", out_path)
        except Exception:
            logger.exception("Failed to save OCR result locally: %s", out_path)
