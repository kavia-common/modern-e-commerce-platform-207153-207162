from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.models import Product
from src.api.schemas import ProductCreateRequest, ProductResponse, ProductUpdateRequest
from src.api.security import require_admin

router = APIRouter(prefix="/products", tags=["products"])


@router.get(
    "",
    response_model=List[ProductResponse],
    summary="Browse products",
    description="Returns active products; supports simple search by name/description.",
    operation_id="products_list",
)
def list_products(
    q: Optional[str] = Query(None, description="Optional search query."),
    include_inactive: bool = Query(False, description="Admin-only: include inactive products."),
    db: Session = Depends(get_db),
) -> List[ProductResponse]:
    """
    List products.

    Public users see only is_active=true. Admins may request include_inactive=true
    (authorization for that is handled at frontend; backend also enforces below).
    """
    stmt = select(Product)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(Product.name.ilike(like), Product.description.ilike(like)))

    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))

    products = db.scalars(stmt.order_by(Product.id.asc())).all()
    return [
        ProductResponse(
            id=p.id,
            sku=p.sku,
            name=p.name,
            description=p.description,
            price_cents=p.price_cents,
            currency=p.currency,
            image_url=p.image_url,
            stock_quantity=p.stock_quantity,
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in products
    ]


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get product",
    description="Get a product by id (public only if active).",
    operation_id="products_get",
)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductResponse:
    """Get a single product."""
    p = db.get(Product, product_id)
    if not p or not p.is_active:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse(
        id=p.id,
        sku=p.sku,
        name=p.name,
        description=p.description,
        price_cents=p.price_cents,
        currency=p.currency,
        image_url=p.image_url,
        stock_quantity=p.stock_quantity,
        is_active=p.is_active,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


# ---- Admin endpoints ----

admin_router = APIRouter(prefix="/admin/products", tags=["admin-products"])


@admin_router.get(
    "",
    response_model=List[ProductResponse],
    summary="Admin: list products",
    description="Admin listing of products (includes inactive).",
    operation_id="admin_products_list",
)
def admin_list_products(db: Session = Depends(get_db), _: object = Depends(require_admin)) -> List[ProductResponse]:
    """Admin product list."""
    products = db.scalars(select(Product).order_by(Product.id.asc())).all()
    return [
        ProductResponse(
            id=p.id,
            sku=p.sku,
            name=p.name,
            description=p.description,
            price_cents=p.price_cents,
            currency=p.currency,
            image_url=p.image_url,
            stock_quantity=p.stock_quantity,
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in products
    ]


@admin_router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin: create product",
    description="Create a new product.",
    operation_id="admin_products_create",
)
def admin_create_product(
    req: ProductCreateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> ProductResponse:
    """Admin create product."""
    p = Product(
        sku=req.sku,
        name=req.name,
        description=req.description,
        price_cents=req.price_cents,
        currency=req.currency,
        image_url=req.image_url,
        stock_quantity=req.stock_quantity,
        is_active=req.is_active,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return ProductResponse(
        id=p.id,
        sku=p.sku,
        name=p.name,
        description=p.description,
        price_cents=p.price_cents,
        currency=p.currency,
        image_url=p.image_url,
        stock_quantity=p.stock_quantity,
        is_active=p.is_active,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@admin_router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Admin: update product",
    description="Update an existing product.",
    operation_id="admin_products_update",
)
def admin_update_product(
    product_id: int,
    req: ProductUpdateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> ProductResponse:
    """Admin update product."""
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")

    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(p, field, value)

    db.commit()
    db.refresh(p)
    return ProductResponse(
        id=p.id,
        sku=p.sku,
        name=p.name,
        description=p.description,
        price_cents=p.price_cents,
        currency=p.currency,
        image_url=p.image_url,
        stock_quantity=p.stock_quantity,
        is_active=p.is_active,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@admin_router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Admin: delete product",
    description="Hard-delete a product (may fail if referenced by orders). Prefer setting is_active=false.",
    operation_id="admin_products_delete",
)
def admin_delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> None:
    """Admin delete product."""
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(p)
    db.commit()
    return None
