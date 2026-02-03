from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.models import Cart, CartItem, Order, OrderItem, Product, User
from src.api.schemas import (
    AdminUpdateOrderStatusRequest,
    CheckoutRequest,
    OrderItemResponse,
    OrderResponse,
    ProductResponse,
)
from src.api.security import get_current_user, require_admin

router = APIRouter(prefix="/orders", tags=["orders"])
admin_router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])


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


def _order_to_schema(order: Order) -> OrderResponse:
    # Ensure relationships are loaded.
    items = order.items
    for it in items:
        _ = it.product

    return OrderResponse(
        id=order.id,
        status=order.status,
        subtotal_cents=order.subtotal_cents,
        tax_cents=order.tax_cents,
        shipping_cents=order.shipping_cents,
        total_cents=order.total_cents,
        currency=order.currency,
        created_at=order.created_at,
        items=[
            OrderItemResponse(
                product=_product_to_schema(it.product),
                quantity=it.quantity,
                unit_price_cents=it.unit_price_cents,
                line_total_cents=it.line_total_cents,
            )
            for it in items
        ],
    )


@router.post(
    "/checkout",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Checkout",
    description="Converts the authenticated user's active cart into a new order.",
    operation_id="orders_checkout",
)
def checkout(req: CheckoutRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> OrderResponse:
    """
    Checkout flow:

    - loads user's active cart + items
    - validates stock
    - creates orders + order_items
    - decrements product stock
    - marks cart as converted and creates a new active cart
    """
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id, Cart.status == "active"))
    if not cart:
        raise HTTPException(status_code=400, detail="No active cart")

    cart_items = db.scalars(select(CartItem).where(CartItem.cart_id == cart.id)).all()
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Validate and compute totals
    subtotal = 0
    currency = "USD"
    for ci in cart_items:
        product = db.get(Product, ci.product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=400, detail=f"Product {ci.product_id} unavailable")
        if product.stock_quantity < ci.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for product {product.id}")
        currency = product.currency
        unit_price = product.price_cents
        line_total = unit_price * ci.quantity
        subtotal += line_total

    tax_cents = req.tax_cents
    shipping_cents = req.shipping_cents
    total = subtotal + tax_cents + shipping_cents

    order = Order(
        user_id=user.id,
        status="paid",  # simplified: assume payment successful
        subtotal_cents=subtotal,
        tax_cents=tax_cents,
        shipping_cents=shipping_cents,
        total_cents=total,
        currency=currency,
    )
    db.add(order)
    db.flush()

    # Create order items and decrement stock
    for ci in cart_items:
        product = db.get(Product, ci.product_id)
        unit_price = product.price_cents
        line_total = unit_price * ci.quantity

        oi = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=ci.quantity,
            unit_price_cents=unit_price,
            line_total_cents=line_total,
        )
        db.add(oi)

        product.stock_quantity -= ci.quantity

    # Mark cart converted and create new cart
    cart.status = "converted"
    new_cart = Cart(user_id=user.id, status="active")
    db.add(new_cart)

    # Delete old cart items
    for ci in cart_items:
        db.delete(ci)

    db.commit()
    db.refresh(order)
    return _order_to_schema(order)


@router.get(
    "",
    response_model=List[OrderResponse],
    summary="Order history",
    description="Returns authenticated user's orders (most recent first).",
    operation_id="orders_list_my",
)
def list_my_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> List[OrderResponse]:
    """List current user's orders."""
    orders = db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())).all()
    for o in orders:
        _ = o.items
    return [_order_to_schema(o) for o in orders]


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order",
    description="Get a single order belonging to the authenticated user.",
    operation_id="orders_get_my",
)
def get_my_order(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> OrderResponse:
    """Get single order for user."""
    order = db.get(Order, order_id)
    if not order or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_to_schema(order)


# ---- Admin endpoints ----

@admin_router.get(
    "",
    response_model=List[OrderResponse],
    summary="Admin: list orders",
    description="List all orders (most recent first).",
    operation_id="admin_orders_list",
)
def admin_list_orders(db: Session = Depends(get_db), _: object = Depends(require_admin)) -> List[OrderResponse]:
    """Admin list orders."""
    orders = db.scalars(select(Order).order_by(Order.created_at.desc())).all()
    for o in orders:
        _ = o.items
    return [_order_to_schema(o) for o in orders]


@admin_router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Admin: get order",
    description="Get any order by id.",
    operation_id="admin_orders_get",
)
def admin_get_order(order_id: int, db: Session = Depends(get_db), _: object = Depends(require_admin)) -> OrderResponse:
    """Admin get order."""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_to_schema(order)


@admin_router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Admin: update order status",
    description="Update an order status (pending/paid/shipped/delivered/cancelled/refunded).",
    operation_id="admin_orders_update_status",
)
def admin_update_order_status(
    order_id: int,
    req: AdminUpdateOrderStatusRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> OrderResponse:
    """Admin update order status."""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = req.status
    db.commit()
    db.refresh(order)
    return _order_to_schema(order)
