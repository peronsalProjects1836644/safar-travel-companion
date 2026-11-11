"""Checks that the OpenAI key works and that the configured model accepts our request format.

Run: python -m scripts.check_openai
Costs well under one cent. Prints the exact model names your key can use, so OPENAI_MODEL can be set correctly.
"""

import asyncio
import json
import sys

from openai import AsyncOpenAI, OpenAIError

from app.core.config import Settings


async def main() -> int:
    s = Settings()
    if not s.openai_api_key:
        print("OPENAI_API_KEY is empty in .env.")
        return 1
    client = AsyncOpenAI(api_key=s.openai_api_key, timeout=30)
    try:
        models = sorted(m.id for m in (await client.models.list()).data)
    except OpenAIError as exc:
        print(f"Key rejected or OpenAI unreachable: {exc}")
        return 1
    print(f"Key works. {len(models)} models available.")
    chat = [m for m in models if m.startswith(("gpt", "o"))]
    print("Chat-capable models:", ", ".join(chat[:40]) + (" ..." if len(chat) > 40 else ""))
    if s.openai_model not in models:
        print(f"\nOPENAI_MODEL='{s.openai_model}' is NOT in your list. Pick one above and set it in .env.")
        return 1
    schema = {
        "name": "ping", "strict": True,
        "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
                   "additionalProperties": False},
    }
    try:
        r = await client.chat.completions.create(
            model=s.openai_model,
            messages=[{"role": "user", "content": 'Reply with {"ok": true}.'}],
            response_format={"type": "json_schema", "json_schema": schema},
            max_completion_tokens=50,
        )
        data = json.loads(r.choices[0].message.content or "{}")
    except (OpenAIError, ValueError) as exc:
        print(f"Model '{s.openai_model}' failed the structured-output test: {exc}")
        return 1
    print(f"Model '{s.openai_model}' OK. Structured output works: {data}. Tokens used: {r.usage.total_tokens}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
