import json
import re
import asyncio
from openai import AsyncOpenAI
from database import search_products

client = AsyncOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

# ── Твои TOOLS (оставь как было) ─────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search for products in the store database. Call this once with ALL product names you see in the image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of product names/brands visible in the photo.",
                    }
                },
                "required": ["queries"],
            },
        },
    }
]

SYSTEM_PROMPT = """You are a smart cashier vision system for a retail store in Kazakhstan.

CRITICAL RULES:
- Analyze the photo carefully.
- Call search_products tool ONCE with ALL product names you see.
- After getting results, return ONLY valid JSON. NO thinking, NO <think>, NO explanations, NO markdown.

Final response format (must be exactly this):
{
  "recognized_items": [
    {
      "product_id": 1,
      "name": "Red Bull 0.25L",
      "price": 350.00,
      "quantity": 1,
      "confidence": 0.98
    }
  ],
  "unrecognized": [],
  "total": 350.00
}
"""

def clean_json_response(raw: str) -> str:
    if not raw:
        return "{}"
    raw = raw.strip()
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL | re.IGNORECASE)
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]
    if "```" in raw:
        raw = raw.split("```")[0]
    return raw.strip()


async def recognize_from_image_ollama(image_base64: str) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}",
                        "detail": "high",
                    },
                },
                {"type": "text", "text": "Identify all products in this photo and search them in the database."},
            ],
        },
    ]

    # Шаг 1: Анализ фото + tool call
    response = await client.chat.completions.create(
        model="qwen3.5:4b",
        messages=messages,
        tools=TOOLS,
        tool_choice="required",
        max_tokens=1200,
        temperature=0.0,
        top_p=0.1,
    )

    msg = response.choices[0].message

    # Шаг 2: Поиск в БД (ИСПРАВЛЕНО — работает и с sync, и с async функцией)
    db_results = []
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            args = json.loads(tool_call.function.arguments)
            queries = args.get("queries", [])

            # ←←← ГЛАВНЫЙ ФИКС ←←←
            if asyncio.iscoroutinefunction(search_products):
                db_results = await search_products(queries)
            else:
                db_results = await asyncio.to_thread(search_products, queries)

        messages.append(msg)
        messages.append({
            "role": "tool",
            "tool_call_id": msg.tool_calls[0].id,
            "content": json.dumps(db_results, ensure_ascii=False, default=str),
        })

    # Шаг 3: Финальный JSON
    final_response = await client.chat.completions.create(
        model="qwen3.5:4b",
        messages=messages,
        max_tokens=800,
        temperature=0.0,
        top_p=0.1,
        response_format={"type": "json_object"},
    )

    raw = final_response.choices[0].message.content or ""
    clean_raw = clean_json_response(raw)

    # Отладка в консоли (после теста можешь закомментировать)
    print("=== RAW FROM QWEN ===")
    print(repr(raw[:500]))
    print("=== CLEANED ===")
    print(repr(clean_raw))

    try:
        return json.loads(clean_raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model returned invalid JSON: {clean_raw[:300]}") from e