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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT NOT NULL UNIQUE,
                name          TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shopping_sessions (
                id          TEXT PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                store_id    TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'active',
                started_at  TEXT DEFAULT (datetime('now')),
                ended_at    TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS session_cart_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL REFERENCES shopping_sessions(id),
                product_id  INTEGER NOT NULL REFERENCES products(id),
                quantity    INTEGER NOT NULL DEFAULT 1,
                added_at    TEXT DEFAULT (datetime('now'))
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



# ── User helpers ───────────────────────────────────────────────────────────────

async def create_user(email: str, name: str, password_hash: str) -> int:
    """Create a new user and return their ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
            (email, name, password_hash),
        )
        await db.commit()
        return cursor.lastrowid


async def get_user_by_email(email: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_by_id(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


# ── Shopping session helpers ───────────────────────────────────────────────────

async def create_session(session_id: str, user_id: int, store_id: str) -> dict:
    """Create a new shopping session and return it."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO shopping_sessions (id, user_id, store_id, status)
               VALUES (?, ?, ?, 'active')""",
            (session_id, user_id, store_id),
        )
        await db.commit()
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM shopping_sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        return dict(row)


async def get_active_session(user_id: int) -> dict | None:
    """Get the user's current active shopping session."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM shopping_sessions WHERE user_id = ? AND status = 'active' ORDER BY started_at DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_session_by_id(session_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM shopping_sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_session_status(session_id: str, status: str) -> bool:
    """Update session status (active → completed / cancelled)."""
    async with aiosqlite.connect(DB_PATH) as db:
        ended = "datetime('now')" if status in ("completed", "cancelled") else "NULL"
        await db.execute(
            f"UPDATE shopping_sessions SET status = ?, ended_at = {ended} WHERE id = ?",
            (status, session_id),
        )
        await db.commit()
        return True


# ── Session cart item helpers ──────────────────────────────────────────────────

async def add_cart_item(session_id: str, product_id: int, quantity: int = 1) -> dict:
    """Add an item to the session cart (or increase quantity if exists)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Check if item already in cart
        cursor = await db.execute(
            "SELECT * FROM session_cart_items WHERE session_id = ? AND product_id = ?",
            (session_id, product_id),
        )
        existing = await cursor.fetchone()
        if existing:
            new_qty = existing["quantity"] + quantity
            await db.execute(
                "UPDATE session_cart_items SET quantity = ? WHERE id = ?",
                (new_qty, existing["id"]),
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM session_cart_items WHERE id = ?", (existing["id"],)
            )
        else:
            cursor = await db.execute(
                "INSERT INTO session_cart_items (session_id, product_id, quantity) VALUES (?, ?, ?)",
                (session_id, product_id, quantity),
            )
            await db.commit()
            item_id = cursor.lastrowid
            cursor = await db.execute(
                "SELECT * FROM session_cart_items WHERE id = ?", (item_id,)
            )
        row = await cursor.fetchone()
        return dict(row)


async def get_cart_items(session_id: str) -> list[dict]:
    """Get all cart items for a session, joined with product info."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT ci.id, ci.session_id, ci.product_id, ci.quantity, ci.added_at,
                      p.name, p.price, p.category, p.image_url, p.barcode
               FROM session_cart_items ci
               JOIN products p ON p.id = ci.product_id
               WHERE ci.session_id = ?
               ORDER BY ci.added_at""",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def update_cart_item_qty(item_id: int, quantity: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        if quantity <= 0:
            await db.execute("DELETE FROM session_cart_items WHERE id = ?", (item_id,))
        else:
            await db.execute(
                "UPDATE session_cart_items SET quantity = ? WHERE id = ?",
                (quantity, item_id),
            )
        await db.commit()
        return True


async def remove_cart_item(item_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM session_cart_items WHERE id = ?", (item_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


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
    