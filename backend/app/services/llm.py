"""Unified LLM client for tool_use calls across providers.

Translates between Anthropic, OpenAI, Google Gemini, and Nanonets
tool-calling conventions so that classifier.py and extractor.py can
stay provider-agnostic.

Nanonets OCR2+ uses a schema-based extraction REST API instead of
chat-style tool_use, so we translate the tool input_schema into a
Nanonets extraction request.
"""

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Parsed tool call returned by any provider."""

    name: str
    input: dict[str, Any]


def tool_use_request(
    *,
    system: str,
    user_message: str,
    tools: list[dict[str, Any]],
    forced_tool: str,
    max_tokens: int = 2048,
    images: list[bytes] | None = None,
) -> ToolResult:
    """Send a tool_use request to the configured LLM provider.

    Args:
        system: System prompt text.
        user_message: User message text.
        tools: Tool definitions in Anthropic format (name, description, input_schema).
        forced_tool: Name of the tool the model must call.
        max_tokens: Maximum output tokens.
        images: Optional list of PNG images to include (for vision path).

    Returns:
        ToolResult with the tool name and parsed input dict.

    Raises:
        RuntimeError: If the model response contains no valid tool call.
    """
    provider = settings.llm_provider
    kwargs: dict[str, Any] = {
        "system": system,
        "user_message": user_message,
        "tools": tools,
        "forced_tool": forced_tool,
        "images": images or [],
    }

    if provider == "nanonets":
        return _nanonets_tool_use(**kwargs)
    if provider == "google":
        return _google_tool_use(**kwargs, max_tokens=max_tokens)
    if provider == "openai":
        return _openai_tool_use(**kwargs, max_tokens=max_tokens)
    return _anthropic_tool_use(**kwargs, max_tokens=max_tokens)


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

_anthropic_client = None


def _get_anthropic_client():
    global _anthropic_client  # noqa: PLW0603
    if _anthropic_client is None:
        import anthropic

        _anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


def _anthropic_tool_use(
    *,
    system: str,
    user_message: str,
    tools: list[dict[str, Any]],
    forced_tool: str,
    max_tokens: int,
    images: list[bytes],
) -> ToolResult:
    client = _get_anthropic_client()

    content: list[dict[str, Any]] | str = user_message
    if images:
        content = []
        for img in images:
            b64 = base64.b64encode(img).decode("ascii")
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": b64},
            })
        content.append({"type": "text", "text": user_message})

    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=max_tokens,
        system=system,
        tools=tools,
        tool_choice={"type": "tool", "name": forced_tool},
        messages=[{"role": "user", "content": content}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == forced_tool:
            return ToolResult(name=block.name, input=block.input)

    raise RuntimeError(f"Anthropic response missing tool_use block for '{forced_tool}'")


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

_openai_client = None


def _get_openai_client():
    global _openai_client  # noqa: PLW0603
    if _openai_client is None:
        from openai import OpenAI

        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def _anthropic_tool_to_openai(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert an Anthropic tool definition to OpenAI function-calling format."""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool["input_schema"],
        },
    }


def _openai_tool_use(
    *,
    system: str,
    user_message: str,
    tools: list[dict[str, Any]],
    forced_tool: str,
    max_tokens: int,
    images: list[bytes],
) -> ToolResult:
    client = _get_openai_client()

    openai_tools = [_anthropic_tool_to_openai(t) for t in tools]

    user_content: list[dict[str, Any]] | str = user_message
    if images:
        user_content = []
        for img in images:
            b64 = base64.b64encode(img).decode("ascii")
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })
        user_content.append({"type": "text", "text": user_message})

    response = client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        tools=openai_tools,
        tool_choice={"type": "function", "function": {"name": forced_tool}},
    )

    message = response.choices[0].message
    if message.tool_calls:
        for tc in message.tool_calls:
            if tc.function.name == forced_tool:
                return ToolResult(
                    name=tc.function.name,
                    input=json.loads(tc.function.arguments),
                )

    raise RuntimeError(f"OpenAI response missing function call for '{forced_tool}'")


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------

_google_client = None


def _get_google_client():
    global _google_client  # noqa: PLW0603
    if _google_client is None:
        from google import genai

        _google_client = genai.Client(api_key=settings.google_api_key)
    return _google_client


def _anthropic_tool_to_gemini(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert an Anthropic tool definition to Gemini function declaration."""
    return {
        "name": tool["name"],
        "description": tool.get("description", ""),
        "parameters": tool["input_schema"],
    }


def _google_tool_use(
    *,
    system: str,
    user_message: str,
    tools: list[dict[str, Any]],
    forced_tool: str,
    max_tokens: int,
    images: list[bytes],
) -> ToolResult:
    from google.genai import types

    client = _get_google_client()

    gemini_declarations = [_anthropic_tool_to_gemini(t) for t in tools]
    gemini_tools = types.Tool(
        function_declarations=gemini_declarations,
    )

    contents: list[Any] = []
    for img in images:
        contents.append(types.Part.from_bytes(data=img, mime_type="image/png"))
    contents.append(user_message)

    response = client.models.generate_content(
        model=settings.google_model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system,
            tools=[gemini_tools],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",
                    allowed_function_names=[forced_tool],
                ),
            ),
            max_output_tokens=max_tokens,
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.function_call and part.function_call.name == forced_tool:
            args = dict(part.function_call.args) if part.function_call.args else {}
            return ToolResult(name=forced_tool, input=args)

    raise RuntimeError(
        f"Gemini response missing function call for '{forced_tool}'"
    )


# ---------------------------------------------------------------------------
# Nanonets OCR2+
# ---------------------------------------------------------------------------

_httpx_client = None


def _get_httpx_client():
    global _httpx_client  # noqa: PLW0603
    if _httpx_client is None:
        import httpx

        _httpx_client = httpx.Client(timeout=120.0)
    return _httpx_client


def _nanonets_tool_use(
    *,
    system: str,
    user_message: str,
    tools: list[dict[str, Any]],
    forced_tool: str,
    images: list[bytes],
) -> ToolResult:
    """Send a schema-based extraction request to Nanonets OCR2+.

    Nanonets doesn't use chat-style tool_use. Instead we POST the document
    text as a file together with the tool's JSON schema, and the API returns
    structured data matching that schema.
    """
    client = _get_httpx_client()

    # Find the forced tool's schema
    tool = next(t for t in tools if t["name"] == forced_tool)
    schema = tool["input_schema"]

    # If images provided, send first image; otherwise send text as document
    if images:
        file_tuple = ("document.png", images[0], "image/png")
    else:
        document_content = f"{system}\n\n{user_message}"
        file_tuple = ("document.txt", document_content.encode("utf-8"), "text/plain")

    response = client.post(
        settings.nanonets_api_url,
        headers={"Authorization": settings.nanonets_api_key},
        files={"file": file_tuple},
        data={
            "schema": json.dumps(schema, ensure_ascii=False),
            "output_type": "json",
        },
    )
    response.raise_for_status()

    result_data = response.json()
    extracted = _parse_nanonets_response(result_data, schema)

    return ToolResult(name=forced_tool, input=extracted)


def _parse_nanonets_response(
    response_data: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Extract the structured fields from a Nanonets API response.

    The API may return results nested under different keys depending on
    the endpoint version. We try common structures and fall back to
    returning the top-level dict filtered to schema properties.
    """
    # Some Nanonets responses nest results under "result" or "data"
    for key in ("result", "data", "extracted_data"):
        if key in response_data and isinstance(response_data[key], dict):
            return response_data[key]

    # If the response is a list of results, take the first
    for key in ("result", "data", "results"):
        if key in response_data and isinstance(response_data[key], list):
            items = response_data[key]
            if items and isinstance(items[0], dict):
                return items[0]

    # Fall back: filter top-level keys to those in the schema
    schema_props = set(schema.get("properties", {}).keys())
    filtered = {k: v for k, v in response_data.items() if k in schema_props}
    if filtered:
        return filtered

    logger.warning(
        "Nanonets response did not match expected structure: %s",
        list(response_data.keys()),
    )
    return response_data
