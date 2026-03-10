import json
import re
from openai import AsyncOpenAI
from database import search_products

client = AsyncOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

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
- ALWAYS use the product from database results even if the name doesn't match exactly.
- If DB returned a similar product (e.g. "Sprite 0.5L" for "Sprite 1L"), use it — never put it in unrecognized.
- Only put in unrecognized if DB returned NO results at all for that product.

Final response format (must be exactly this):
{
  "recognized_items": [
    {
      "product_id": 1,
      "name": "Coca-Cola 1L",
      "price": 450.00,
      "quantity": 1,
      "confidence": 0.98
    }
  ],
  "unrecognized": [],
  "total": 450.00
}
"""


def clean_json_response(raw: str) -> str:
    if not raw:
        return ""
    raw = raw.strip()
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL | re.IGNORECASE)
    raw = raw.strip()
    for prefix in ("```json", "```"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    if "```" in raw:
        raw = raw.split("```")[0]
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start:end + 1]
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

    # Шаг 1: анализ фото + tool call
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

    if not msg.tool_calls:
        raise ValueError("Model did not call the tool")

    # Шаг 2: собираем ВСЕ queries из ВСЕХ tool_calls
    all_queries = []
    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)
        all_queries.extend(args.get("queries", []))

    db_results = await search_products(all_queries)
    db_json = json.dumps(db_results, ensure_ascii=False, default=str)

    # Добавляем assistant message как dict (не SDK-объект)
    messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ],
    })

    # Tool result для КАЖДОГО tool_call
    for tc in msg.tool_calls:
        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": db_json,
        })

    # Шаг 3: финальный JSON
    final_response = await client.chat.completions.create(
        model="qwen3.5:4b",
        messages=messages,
        max_tokens=800,
        temperature=0.0,
        top_p=0.1,
        response_format={"type": "json_object"},
    )

    raw = final_response.choices[0].message.content or ""
    print(final_response)

    clean = clean_json_response(raw)
    if not clean:
        raise ValueError(f"Model returned empty response. Raw: {raw[:300]}")

    try:
        return json.loads(clean)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {clean[:300]}") from e
    