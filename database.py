import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "shop.db")


async def init_db():
    """Создаёт таблицу и наполняет тестовыми данными при первом запуске."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                category    TEXT,
                description TEXT,
                price       REAL NOT NULL,
                image_url   TEXT,
                barcode     TEXT,
                in_stock    INTEGER DEFAULT 1,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.commit()

        # Наполняем только если таблица пустая
        cursor = await db.execute("SELECT COUNT(*) FROM products")
        (count,) = await cursor.fetchone()
        if count == 0:
            await db.executemany(
                """INSERT INTO products
                   (name, category, description, price, barcode)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    ("Coca-Cola 1L",         "Напитки",  "Газированный напиток Coca-Cola 1 литр",       450,  "4870200013834"),
                    ("Lay's Сметана 150г",   "Снеки",    "Чипсы картофельные со вкусом сметаны",        350,  "4823063107456"),
                    ("Sprite 0.5L",          "Напитки",  "Газированный напиток Sprite 500 мл",           320,  "5449000014238"),
                    ("Шоколад Milka 90г",    "Сладости", "Молочный шоколад с альпийским молоком",        520,  "7622300441937"),
                    ("Чай Lipton 25 пак",    "Продукты", "Чай чёрный в пакетиках",                       680,  "8712100851637"),
                    ("Red Bull 250мл",       "Напитки",  "Энергетический напиток Red Bull",              750,  "9002490100070"),
                    ("Snickers 50г",         "Сладости", "Шоколадный батончик Snickers",                 280,  "4600831012501"),
                    ("Orbit Spearmint",      "Прочее",   "Жевательная резинка Orbit мята",               250,  "4009900476003"),
                    ("Вода Bonaqua 1L",      "Напитки",  "Питьевая вода без газа",                       200,  "4870200011502"),
                    ("Pringles Original",    "Снеки",    "Чипсы Pringles в тубе оригинальные",           890,  "0038000845598"),
                ],
            )
            await db.commit()


async def search_products(queries: list[str]) -> list[dict]:
    results = []
    seen_ids: set[int] = set()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        for q in queries:
            # Сначала ищем по полной фразе
            candidates = [q]

            # Добавляем поиск по каждому значимому слову (длиннее 2 букв)
            words = [w for w in q.split() if len(w) > 2]
            candidates.extend(words)

            for term in candidates:
                pattern = f"%{term}%"
                cursor = await db.execute(
                    """
                    SELECT id, name, category, description, price, image_url, barcode
                    FROM products
                    WHERE in_stock = 1
                      AND (name LIKE ? OR description LIKE ?)
                    LIMIT 2
                    """,
                    (pattern, pattern),
                )
                rows = await cursor.fetchall()
                for row in rows:
                    if row["id"] not in seen_ids:
                        seen_ids.add(row["id"])
                        results.append(dict(row))

    return results


async def get_all_products() -> list[dict]:
    """Возвращает все товары из базы данных."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row  # доступ по имени колонки

        cursor = await db.execute(
            """
            SELECT id, name, category, description, price, image_url, barcode, in_stock, created_at
            FROM products
            ORDER BY name
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_product_by_id(product_id: int) -> dict | None:
    """Возвращает товар по ID или None, если не найден."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        cursor = await db.execute(
            """
            SELECT id, name, category, description, price, image_url, barcode, in_stock, created_at
            FROM products
            WHERE id = ?
            """,
            (product_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_product(
    name: str,
    category: str | None = None,
    description: str | None = None,
    price: float = 0.0,
    image_url: str | None = None,
    barcode: str | None = None,
    in_stock: int = 1
) -> int:
    """Создаёт новый товар и возвращает его ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO products (name, category, description, price, image_url, barcode, in_stock)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, category, description, price, image_url, barcode, in_stock)
        )
        await db.commit()
        return cursor.lastrowid


async def update_product(
    product_id: int,
    name: str | None = None,
    category: str | None = None,
    description: str | None = None,
    price: float | None = None,
    image_url: str | None = None,
    barcode: str | None = None,
    in_stock: int | None = None
) -> bool:
    """Обновляет товар. Возвращает True, если товар найден и обновлён."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Сначала проверяем существование товара
        cursor = await db.execute("SELECT id FROM products WHERE id = ?", (product_id,))
        if not await cursor.fetchone():
            return False
        
        # Формируем SQL динамически, обновляя только переданные поля
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if category is not None:
            updates.append("category = ?")
            params.append(category)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if price is not None:
            updates.append("price = ?")
            params.append(price)
        if image_url is not None:
            updates.append("image_url = ?")
            params.append(image_url)
        if barcode is not None:
            updates.append("barcode = ?")
            params.append(barcode)
        if in_stock is not None:
            updates.append("in_stock = ?")
            params.append(in_stock)
        
        if not updates:
            return True  # Нечего обновлять
        
        params.append(product_id)
        sql = f"UPDATE products SET {', '.join(updates)} WHERE id = ?"
        
        await db.execute(sql, params)
        await db.commit()
        return True


async def delete_product(product_id: int) -> bool:
    """Удаляет товар. Возвращает True, если товар найден и удалён."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        await db.commit()
        return cursor.rowcount > 0
    