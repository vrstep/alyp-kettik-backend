import json
import os
from openai import AsyncOpenAI
from database import search_products

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── Tool definition для function calling ──────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Search for products in the store database. "
                "Call this once with ALL product names you see in the image."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "List of product names/brands visible in the photo. "
                            "E.g. ['Coca-Cola', 'Lays chips', 'Milka chocolate']"
                        ),
                    }
                },
                "required": ["queries"],
            },
        },
    }
]

SYSTEM_PROMPT = """You are a smart cashier vision system for a retail store in Kazakhstan.

Your task:
1. Carefully examine the photo — it shows products placed on a table/surface
2. Identify ALL visible product names, brands, and types
3. Call the search_products tool ONCE with all product names you identified
4. After receiving search results, return a JSON response

Response format (after tool call):
{
  "recognized_items": [
    {
      "product_id": 1,
      "name": "Coca-Cola 1L",
      "price": 450.00,
      "quantity": 1,
      "confidence": 0.95
    }
  ],
  "unrecognized": ["item name if not found in DB"],
  "total": 450.00
}

Rules:
- If multiple identical items visible, set quantity > 1
- confidence: 0.0-1.0 based on how clearly you see the product
- ALWAYS use the product from database results even if the name doesn't match exactly
- If DB returned a similar product (e.g. "Sprite 0.5L" for "Sprite 1L"), use it — never put it in unrecognized
- Only put in unrecognized if DB returned NO results at all for that product
- Always respond in the JSON format above after the tool call
"""


async def recognize_from_image(image_base64: str) -> dict:
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
                {
                    "type": "text",
                    "text": "Identify all products in this photo and search for them in the database.",
                },
            ],
        },
    ]

    # Шаг 1: GPT-4o анализирует фото
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=TOOLS,
        tool_choice="required",
        max_tokens=1000,
    )

    msg = response.choices[0].message

    if not msg.tool_calls:
        raise ValueError("Model did not call the tool")

    # Шаг 2: собираем ВСЕ queries из ВСЕХ tool_calls, ищем одним запросом
    all_queries = []
    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)
        all_queries.extend(args.get("queries", []))

    db_results = await search_products(all_queries)
    db_json = json.dumps(db_results, ensure_ascii=False, default=str)

    # Добавляем assistant message
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

    # Добавляем tool result для КАЖДОГО tool_call (обязательно!)
    for tc in msg.tool_calls:
        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": db_json,
        })

    # Шаг 3: финальный JSON
    final_response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=1000,
        response_format={"type": "json_object"},
    )

    print(final_response)

    return json.loads(final_response.choices[0].message.content)
