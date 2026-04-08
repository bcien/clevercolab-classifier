"""Application settings loaded from environment variables and .env file."""

from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    mistral_api_key: str = ""

    aws_region: str = "us-east-1"
    s3_input_bucket: str = "clevercolab-input"
    s3_output_bucket: str = "clevercolab-output"
    s3_ocr_results_bucket: str = "clevercolab-ocr-results"
    dynamodb_table: str = "clevercolab-jobs"

    log_level: str = "INFO"
    job_ttl_hours: int = 24

    # LLM provider: "anthropic", "openai", "google", or "nanonets"
    llm_provider: Literal["anthropic", "openai", "google", "nanonets"] = "anthropic"

    # Claude model for classification/extraction
    claude_model: str = "claude-sonnet-4-20250514"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4"

    # Google Gemini
    google_api_key: str = ""
    google_model: str = "gemini-3.1-pro"

    # Nanonets OCR2+
    nanonets_api_key: str = ""
    nanonets_api_url: str = "https://extraction-api.nanonets.com/extract"

    # OCR provider for scanned pages
    ocr_provider: Literal[
        "textract", "mistral", "openai", "google", "nanonets"
    ] = "textract"

    # Local development: save output files to this directory instead of S3
    local_output_dir: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
