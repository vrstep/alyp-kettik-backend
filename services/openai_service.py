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
- Always respond in the JSON format above after the tool call
"""


async def recognize_from_image(image_base64: str) -> dict:
    """
    Полный цикл: изображение → OpenAI Vision → function calling → DB поиск → результат.
    """
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
                    "text": "Please identify all products in this photo and search for them in the database.",
                },
            ],
        },
    ]

    # ── Шаг 1: GPT-4o анализирует фото ────────────────────────────────────────
    response = await client.chat.completions.create(
        model="gpt-5-mini-2025-08-07",
        messages=messages,
        tools=TOOLS,
        tool_choice="required",  # обязываем вызвать tool
        max_tokens=1000,
    )

    msg = response.choices[0].message

    # ── Шаг 2: Выполняем поиск в БД ───────────────────────────────────────────
    db_results = []
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            args = json.loads(tool_call.function.arguments)
            queries = args.get("queries", [])
            db_results = await search_products(queries)

        # Добавляем ответ модели и результат tool в messages
        messages.append(msg)
        messages.append({
            "role": "tool",
            "tool_call_id": msg.tool_calls[0].id,
            "content": json.dumps(db_results, ensure_ascii=False, default=str),
        })

    # ── Шаг 3: GPT-4o формирует финальный ответ ───────────────────────────────
    final_response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=1000,
        response_format={"type": "json_object"},
    )

    raw = final_response.choices[0].message.content
    return json.loads(raw)