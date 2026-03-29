from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import (
    get_all_products,
    get_product_by_id,
    create_product,
    update_product,
    delete_product,
    reseed_products,
)

router = APIRouter(prefix="/products", tags=["products"])


# ── Pydantic модели для валидации ───────────────────────────────────────────────
class ProductCreate(BaseModel):
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    barcode: Optional[str] = None
    in_stock: int = 1


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    barcode: Optional[str] = None
    in_stock: Optional[int] = None


class ProductResponse(BaseModel):
    id: int
    name: str
    category: Optional[str]
    description: Optional[str]
    price: float
    image_url: Optional[str]
    barcode: Optional[str]
    in_stock: int
    created_at: str


# ── Endpoints ───────────────────────────────────────────────────────────────────
@router.get("", response_model=dict)
async def get_products():
    """
    Получить список всех товаров.
    
    Возвращает все товары из базы данных, отсортированные по названию.
    """
    products = await get_all_products()
    return {
        "count": len(products),
        "products": products
    }


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int):
    """
    Получить товар по ID.
    """
    product = await get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("", response_model=ProductResponse, status_code=201)
async def create_new_product(product: ProductCreate):
    """
    Создать новый товар.
    """
    product_id = await create_product(
        name=product.name,
        category=product.category,
        description=product.description,
        price=product.price,
        image_url=product.image_url,
        barcode=product.barcode,
        in_stock=product.in_stock
    )
    
    created_product = await get_product_by_id(product_id)
    return created_product


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product_endpoint(product_id: int, product: ProductUpdate):
    """
    Обновить существующий товар.
    
    Обновляет только переданные поля. Если товар не найден, возвращает 404.
    """
    updated = await update_product(
        product_id=product_id,
        name=product.name,
        category=product.category,
        description=product.description,
        price=product.price,
        image_url=product.image_url,
        barcode=product.barcode,
        in_stock=product.in_stock
    )
    
    if not updated:
        raise HTTPException(status_code=404, detail="Product not found")
    
    updated_product = await get_product_by_id(product_id)
    return updated_product


@router.delete("/{product_id}", status_code=204)
async def delete_product_endpoint(product_id: int):
    """
    Удалить товар.
    
    Если товар не найден, возвращает 404.
    """
    deleted = await delete_product(product_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return None


@router.post("/reseed")
async def reseed_products_endpoint():
    """
    Re-seed the products table with the 5 YOLO-detectable products.
    WARNING: This clears all existing products and cart items.
    """
    try:
        await reseed_products()
        return {"message": "Products re-seeded successfully", "count": 5}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Re-seed failed: {e}")
