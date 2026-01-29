from typing import List, Tuple

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.models import Cart, CartItem, Product, User
from src.api.schemas import CartResponse, CartUpsertItemRequest, CartItemResponse, ProductResponse
from src.api.security import get_current_user

router = APIRouter(prefix="/cart", tags=["cart"])


def _product_to_schema(p: Product) -> ProductResponse:
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


def _get_or_create_active_cart(db: Session, user: User) -> Cart:
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id, Cart.status == "active"))
    if cart:
        return cart
    cart = Cart(user_id=user.id, status="active")
    db.add(cart)
    db.flush()
    return cart


def _cart_totals(items: List[CartItem]) -> Tuple[int, str]:
    subtotal = sum(i.quantity * i.unit_price_cents for i in items)
    currency = "USD"
    if items:
        currency = items[0].product.currency
    return subtotal, currency


@router.get(
    "",
    response_model=CartResponse,
    summary="Get current cart",
    description="Returns the authenticated user's active cart.",
    operation_id="cart_get",
)
def get_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CartResponse:
    """Get active cart with items."""
    cart = _get_or_create_active_cart(db, user)
    db.refresh(cart)
    items = db.scalars(select(CartItem).where(CartItem.cart_id == cart.id)).all()

    # Eager load products
    for it in items:
        _ = it.product

    subtotal, currency = _cart_totals(items)
    return CartResponse(
        id=cart.id,
        status=cart.status,
        items=[
            CartItemResponse(product=_product_to_schema(it.product), quantity=it.quantity, unit_price_cents=it.unit_price_cents)
            for it in items
        ],
        subtotal_cents=subtotal,
        currency=currency,
    )


@router.put(
    "/items",
    response_model=CartResponse,
    summary="Add or update cart item",
    description="Adds an item to cart or updates its quantity (quantity >= 1).",
    operation_id="cart_upsert_item",
)
def upsert_item(
    req: CartUpsertItemRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartResponse:
    """Upsert cart item."""
    product = db.get(Product, req.product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.stock_quantity < req.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    cart = _get_or_create_active_cart(db, user)

    item = db.scalar(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product.id))
    if item:
        item.quantity = req.quantity
        item.unit_price_cents = product.price_cents
    else:
        item = CartItem(cart_id=cart.id, product_id=product.id, quantity=req.quantity, unit_price_cents=product.price_cents)
        db.add(item)

    db.commit()
    return get_cart(user=user, db=db)


@router.delete(
    "/items/{product_id}",
    response_model=CartResponse,
    summary="Remove item from cart",
    description="Removes a product from the active cart.",
    operation_id="cart_remove_item",
)
def remove_item(product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CartResponse:
    """Remove cart item."""
    cart = _get_or_create_active_cart(db, user)
    item = db.scalar(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id))
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    db.delete(item)
    db.commit()
    return get_cart(user=user, db=db)


@router.delete(
    "",
    response_model=CartResponse,
    summary="Clear cart",
    description="Removes all items from the active cart.",
    operation_id="cart_clear",
)
def clear_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CartResponse:
    """Clear active cart."""
    cart = _get_or_create_active_cart(db, user)
    items = db.scalars(select(CartItem).where(CartItem.cart_id == cart.id)).all()
    for it in items:
        db.delete(it)
    db.commit()
    return get_cart(user=user, db=db)
