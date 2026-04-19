import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


async def init_db():
    """Create tables and seed test data on first run."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id          SERIAL PRIMARY KEY,
                name        TEXT NOT NULL,
                category    TEXT,
                description TEXT,
                price       NUMERIC(10,2) NOT NULL,
                image_url   TEXT,
                barcode     TEXT,
                yolo_class  TEXT,
                in_stock    INTEGER DEFAULT 1,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Add yolo_class column if it doesn't exist (for existing DBs)
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'products' AND column_name = 'yolo_class'
                ) THEN
                    ALTER TABLE products ADD COLUMN yolo_class TEXT;
                END IF;
            END $$;
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                email         TEXT NOT NULL UNIQUE,
                name          TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS shopping_sessions (
                id          TEXT PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                store_id    TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'active',
                started_at  TIMESTAMPTZ DEFAULT NOW(),
                ended_at    TIMESTAMPTZ
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS session_cart_items (
                id          SERIAL PRIMARY KEY,
                session_id  TEXT NOT NULL REFERENCES shopping_sessions(id),
                product_id  INTEGER NOT NULL REFERENCES products(id),
                quantity    INTEGER NOT NULL DEFAULT 1,
                added_at    TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS used_entry_tokens (
                jti         TEXT PRIMARY KEY,
                user_id     INTEGER NOT NULL,
                used_at     TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_methods (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                card_type   TEXT NOT NULL,
                last_four   TEXT NOT NULL,
                holder_name TEXT NOT NULL,
                expiry      TEXT NOT NULL,
                is_default  BOOLEAN DEFAULT FALSE,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id          TEXT PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                session_id  TEXT REFERENCES shopping_sessions(id),
                payment_method_id INTEGER REFERENCES payment_methods(id),
                status      TEXT NOT NULL DEFAULT 'paid',
                total       NUMERIC(10,2) NOT NULL,
                paid_at     TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id          SERIAL PRIMARY KEY,
                order_id    TEXT NOT NULL REFERENCES orders(id),
                product_id  INTEGER NOT NULL REFERENCES products(id),
                name        TEXT NOT NULL,
                price       NUMERIC(10,2) NOT NULL,
                quantity    INTEGER NOT NULL
            )
        """)

        # Seed only if products table is empty
        count = await conn.fetchval("SELECT COUNT(*) FROM products")
        if count == 0:
            await conn.executemany(
                """INSERT INTO products
                   (name, category, description, price, barcode, yolo_class)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                [
                    ("BonAqua 1L",                 "Напитки",  "Питьевая вода BonAqua без газа 1 литр",                200,  "4870200011502", "bon_aqua_1l"),
                    ("Coca-Cola 1L",               "Напитки",  "Газированный напиток Coca-Cola 1 литр",                450,  "4870200013834", "coca_cola_1l"),
                    ("Яйца Казгер 10 шт",         "Продукты", "Куриные яйца Казгер 10 штук",                          590,  "4870000000001", "eggs_kazger_10p"),
                    ("Кублей 325г",                "Продукты", "Кублей творожный 325 г",                               380,  "4870000000002", "kublei_325g"),
                    ("Махеев Шашлык 500г",         "Соусы",    "Кетчуп Махеев Шашлык 500 г",                           490,  "4870000000003", "maheev_shashlyk_500g"),
                    ("Майонез Ряба 364мл",         "Соусы",    "Майонез Ряба Провансаль 364 мл",                       420,  "4870000000004", "mayo_ryaba_364ml"),
                    ("Молоко Петропавловск 3.2%",  "Молочные", "Молоко Петропавловск пастеризованное 3.2% 1 литр",     450,  "4870000000005", "milk_petropavlovsk_3.2"),
                    ("Milka Almond 80g",           "Сладости", "Молочный шоколад Milka с миндалём 80 г",               520,  "7622300441937", "milka_almond_80g"),
                    ("Piala 25 пак",               "Напитки",  "Чай Piala чёрный в пакетиках 25 шт",                   680,  "8712100851637", "piala_25b"),
                    ("Red Bull 250мл",             "Напитки",  "Энергетический напиток Red Bull 250 мл",               750,  "9002490100070", "red_bull_250ml"),
                    ("Twix 55г",                   "Сладости", "Шоколадный батончик Twix 55 г",                        350,  "5000159461122", "twix_55g"),
                ],
            )


# ── User helpers ───────────────────────────────────────────────────────────────

async def create_user(email: str, name: str, password_hash: str) -> int:
    """Create a new user and return their ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO users (email, name, password_hash) VALUES ($1, $2, $3) RETURNING id",
            email, name, password_hash,
        )
        return row["id"]


async def get_user_by_email(email: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
        return dict(row) if row else None


async def get_user_by_id(user_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        return dict(row) if row else None


# ── Shopping session helpers ───────────────────────────────────────────────────

async def create_session(session_id: str, user_id: int, store_id: str) -> dict:
    """Create a new shopping session and return it."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO shopping_sessions (id, user_id, store_id, status)
               VALUES ($1, $2, $3, 'active')""",
            session_id, user_id, store_id,
        )
        row = await conn.fetchrow(
            "SELECT * FROM shopping_sessions WHERE id = $1", session_id
        )
        return dict(row)


async def get_active_session(user_id: int) -> dict | None:
    """Get the user's current active shopping session."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM shopping_sessions WHERE user_id = $1 AND status = 'active' ORDER BY started_at DESC LIMIT 1",
            user_id,
        )
        return dict(row) if row else None


async def get_session_by_id(session_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM shopping_sessions WHERE id = $1", session_id
        )
        return dict(row) if row else None


async def update_session_status(session_id: str, status: str) -> bool:
    """Update session status (active → completed / cancelled)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if status in ("completed", "cancelled"):
            await conn.execute(
                "UPDATE shopping_sessions SET status = $1, ended_at = NOW() WHERE id = $2",
                status, session_id,
            )
        else:
            await conn.execute(
                "UPDATE shopping_sessions SET status = $1 WHERE id = $2",
                status, session_id,
            )
        return True


# ── Session cart item helpers ──────────────────────────────────────────────────

async def add_cart_item(session_id: str, product_id: int, quantity: int = 1) -> dict:
    """Add an item to the session cart (or increase quantity if exists)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM session_cart_items WHERE session_id = $1 AND product_id = $2",
            session_id, product_id,
        )
        if existing:
            new_qty = existing["quantity"] + quantity
            await conn.execute(
                "UPDATE session_cart_items SET quantity = $1 WHERE id = $2",
                new_qty, existing["id"],
            )
            row = await conn.fetchrow(
                "SELECT * FROM session_cart_items WHERE id = $1", existing["id"]
            )
        else:
            row = await conn.fetchrow(
                "INSERT INTO session_cart_items (session_id, product_id, quantity) VALUES ($1, $2, $3) RETURNING *",
                session_id, product_id, quantity,
            )
        return dict(row)


async def get_cart_items(session_id: str) -> list[dict]:
    """Get all cart items for a session, joined with product info."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT ci.id, ci.session_id, ci.product_id, ci.quantity, ci.added_at,
                      p.name, p.price, p.category, p.image_url, p.barcode
               FROM session_cart_items ci
               JOIN products p ON p.id = ci.product_id
               WHERE ci.session_id = $1
               ORDER BY ci.added_at""",
            session_id,
        )
        return [dict(r) for r in rows]


async def update_cart_item_qty(item_id: int, quantity: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if quantity <= 0:
            await conn.execute("DELETE FROM session_cart_items WHERE id = $1", item_id)
        else:
            await conn.execute(
                "UPDATE session_cart_items SET quantity = $1 WHERE id = $2",
                quantity, item_id,
            )
        return True


async def remove_cart_item(item_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM session_cart_items WHERE id = $1", item_id
        )
        return result == "DELETE 1"


async def search_products(queries: list[str]) -> list[dict]:
    results = []
    seen_ids: set[int] = set()

    pool = await get_pool()
    async with pool.acquire() as conn:
        for q in queries:
            candidates = [q]
            words = [w for w in q.split() if len(w) > 2]
            candidates.extend(words)

            for term in candidates:
                pattern = f"%{term}%"
                rows = await conn.fetch(
                    """
                    SELECT id, name, category, description, price, image_url, barcode
                    FROM products
                    WHERE in_stock = 1
                      AND (name ILIKE $1 OR description ILIKE $1)
                    LIMIT 2
                    """,
                    pattern,
                )
                for row in rows:
                    if row["id"] not in seen_ids:
                        seen_ids.add(row["id"])
                        results.append(dict(row))

    return results


async def get_all_products() -> list[dict]:
    """Return all products sorted by name."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, category, description, price, image_url, barcode, yolo_class, in_stock, created_at
            FROM products
            ORDER BY name
            """
        )
        return [dict(row) for row in rows]


async def get_product_by_id(product_id: int) -> dict | None:
    """Return a product by ID or None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, category, description, price, image_url, barcode, yolo_class, in_stock, created_at
            FROM products
            WHERE id = $1
            """,
            product_id,
        )
        return dict(row) if row else None


async def get_product_by_yolo_class(yolo_class: str) -> dict | None:
    """Return a product by its YOLO detection class name."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, category, description, price, image_url, barcode, yolo_class, in_stock, created_at
            FROM products
            WHERE yolo_class = $1
            """,
            yolo_class,
        )
        return dict(row) if row else None


async def reseed_products():
    """Clear all products and cart items, then re-seed with YOLO-detectable products."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Clear cart items first (FK constraint)
        await conn.execute("DELETE FROM session_cart_items")
        await conn.execute("DELETE FROM products")
        # Reset sequence
        await conn.execute("ALTER SEQUENCE products_id_seq RESTART WITH 1")
        # Re-seed
        await conn.executemany(
            """INSERT INTO products
               (name, category, description, price, barcode, yolo_class)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            [
                ("BonAqua 1L",                 "Напитки",  "Питьевая вода BonAqua без газа 1 литр",                200,  "4870200011502", "bon_aqua_1l"),
                ("Coca-Cola 1L",               "Напитки",  "Газированный напиток Coca-Cola 1 литр",                450,  "4870200013834", "coca_cola_1l"),
                ("Яйца Казгер 10 шт",         "Продукты", "Куриные яйца Казгер 10 штук",                          590,  "4870000000001", "eggs_kazger_10p"),
                ("Кублей 325г",                "Продукты", "Кублей творожный 325 г",                               380,  "4870000000002", "kublei_325g"),
                ("Махеев Шашлык 500г",         "Соусы",    "Кетчуп Махеев Шашлык 500 г",                           490,  "4870000000003", "maheev_shashlyk_500g"),
                ("Майонез Ряба 364мл",         "Соусы",    "Майонез Ряба Провансаль 364 мл",                       420,  "4870000000004", "mayo_ryaba_364ml"),
                ("Молоко Петропавловск 3.2%",  "Молочные", "Молоко Петропавловск пастеризованное 3.2% 1 литр",     450,  "4870000000005", "milk_petropavlovsk_3.2"),
                ("Milka Almond 80g",           "Сладости", "Молочный шоколад Milka с миндалём 80 г",               520,  "7622300441937", "milka_almond_80g"),
                ("Piala 25 пак",               "Напитки",  "Чай Piala чёрный в пакетиках 25 шт",                   680,  "8712100851637", "piala_25b"),
                ("Red Bull 250мл",             "Напитки",  "Энергетический напиток Red Bull 250 мл",               750,  "9002490100070", "red_bull_250ml"),
                ("Twix 55г",                   "Сладости", "Шоколадный батончик Twix 55 г",                        350,  "5000159461122", "twix_55g"),
            ],
        )
        return True


async def create_product(
    name: str,
    category: str | None = None,
    description: str | None = None,
    price: float = 0.0,
    image_url: str | None = None,
    barcode: str | None = None,
    in_stock: int = 1,
) -> int:
    """Create a new product and return its ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO products (name, category, description, price, image_url, barcode, in_stock)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            name, category, description, price, image_url, barcode, in_stock,
        )
        return row["id"]


async def update_product(
    product_id: int,
    name: str | None = None,
    category: str | None = None,
    description: str | None = None,
    price: float | None = None,
    image_url: str | None = None,
    barcode: str | None = None,
    in_stock: int | None = None,
) -> bool:
    """Update a product. Returns True if found and updated."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM products WHERE id = $1", product_id)
        if not existing:
            return False

        updates = []
        params = []
        idx = 1

        for field, value in [
            ("name", name), ("category", category), ("description", description),
            ("price", price), ("image_url", image_url), ("barcode", barcode),
            ("in_stock", in_stock),
        ]:
            if value is not None:
                updates.append(f"{field} = ${idx}")
                params.append(value)
                idx += 1

        if not updates:
            return True

        params.append(product_id)
        sql = f"UPDATE products SET {', '.join(updates)} WHERE id = ${idx}"
        await conn.execute(sql, *params)
        return True


async def delete_product(product_id: int) -> bool:
    """Delete a product. Returns True if found and deleted."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM products WHERE id = $1", product_id)
        return result == "DELETE 1"


# ── Payment method helpers ─────────────────────────────────────────────────────

async def create_payment_method(
    user_id: int, card_type: str, last_four: str, holder_name: str, expiry: str,
) -> dict:
    """Create a new payment method for a user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # If this is the user's first card, make it default
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM payment_methods WHERE user_id = $1", user_id
        )
        is_default = count == 0

        row = await conn.fetchrow(
            """INSERT INTO payment_methods (user_id, card_type, last_four, holder_name, expiry, is_default)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
            user_id, card_type, last_four, holder_name, expiry, is_default,
        )
        return dict(row)


async def get_payment_methods(user_id: int) -> list[dict]:
    """Get all payment methods for a user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM payment_methods WHERE user_id = $1 ORDER BY is_default DESC, created_at DESC",
            user_id,
        )
        return [dict(r) for r in rows]


async def delete_payment_method(method_id: int, user_id: int) -> bool:
    """Delete a payment method. Returns True if found and deleted."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM payment_methods WHERE id = $1 AND user_id = $2",
            method_id, user_id,
        )
        return result == "DELETE 1"


async def set_default_payment_method(method_id: int, user_id: int) -> bool:
    """Set a payment method as the default (unsets others)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Verify it exists
        row = await conn.fetchrow(
            "SELECT id FROM payment_methods WHERE id = $1 AND user_id = $2",
            method_id, user_id,
        )
        if not row:
            return False
        # Unset all defaults for this user
        await conn.execute(
            "UPDATE payment_methods SET is_default = FALSE WHERE user_id = $1",
            user_id,
        )
        # Set new default
        await conn.execute(
            "UPDATE payment_methods SET is_default = TRUE WHERE id = $1",
            method_id,
        )
        return True


# ── Order helpers ──────────────────────────────────────────────────────────────

async def create_order(
    order_id: str, user_id: int, session_id: str | None,
    payment_method_id: int, total: float, items: list[dict],
) -> dict:
    """Create an order with its items. Each item dict needs: product_id, name, price, quantity."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO orders (id, user_id, session_id, payment_method_id, status, total)
                   VALUES ($1, $2, $3, $4, 'paid', $5)""",
                order_id, user_id, session_id, payment_method_id, total,
            )
            for item in items:
                await conn.execute(
                    """INSERT INTO order_items (order_id, product_id, name, price, quantity)
                       VALUES ($1, $2, $3, $4, $5)""",
                    order_id, item["product_id"], item["name"],
                    item["price"], item["quantity"],
                )
            row = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
            return dict(row)


async def get_user_orders(user_id: int) -> list[dict]:
    """Get all orders for a user, newest first, with item count."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT o.*,
                      (SELECT COUNT(*) FROM order_items oi WHERE oi.order_id = o.id) AS item_count,
                      pm.card_type, pm.last_four
               FROM orders o
               LEFT JOIN payment_methods pm ON pm.id = o.payment_method_id
               WHERE o.user_id = $1
               ORDER BY o.paid_at DESC""",
            user_id,
        )
        return [dict(r) for r in rows]


async def get_order_detail(order_id: str, user_id: int) -> dict | None:
    """Get a single order with its items."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            """SELECT o.*, pm.card_type, pm.last_four, pm.holder_name AS card_holder
               FROM orders o
               LEFT JOIN payment_methods pm ON pm.id = o.payment_method_id
               WHERE o.id = $1 AND o.user_id = $2""",
            order_id, user_id,
        )
        if not order:
            return None
        items = await conn.fetch(
            "SELECT * FROM order_items WHERE order_id = $1 ORDER BY id",
            order_id,
        )
        result = dict(order)
        result["items"] = [dict(i) for i in items]
        return result