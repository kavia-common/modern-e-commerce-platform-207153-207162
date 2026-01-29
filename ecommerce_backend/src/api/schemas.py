from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token.")
    token_type: str = Field("bearer", description="Token type for Authorization header.")
    user: "UserPublic" = Field(..., description="The authenticated user.")


class UserRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User email (unique).")
    password: str = Field(..., min_length=6, description="User password (min 6 chars).")
    full_name: Optional[str] = Field(None, description="User full name.")


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email.")
    password: str = Field(..., description="User password.")


class UserPublic(BaseModel):
    id: int = Field(..., description="User id.")
    email: EmailStr = Field(..., description="User email.")
    full_name: Optional[str] = Field(None, description="User full name.")
    role: str = Field(..., description="User role (customer/admin).")


class ProductBase(BaseModel):
    sku: Optional[str] = Field(None, description="Optional SKU.")
    name: str = Field(..., description="Product name.")
    description: Optional[str] = Field(None, description="Product description.")
    price_cents: int = Field(..., ge=0, description="Price in cents.")
    currency: str = Field("USD", description="Currency code (e.g. USD).")
    image_url: Optional[str] = Field(None, description="Optional image URL.")
    stock_quantity: int = Field(0, ge=0, description="Available inventory.")
    is_active: bool = Field(True, description="If false, product is hidden from browse.")


class ProductCreateRequest(ProductBase):
    pass


class ProductUpdateRequest(BaseModel):
    sku: Optional[str] = Field(None, description="Optional SKU.")
    name: Optional[str] = Field(None, description="Product name.")
    description: Optional[str] = Field(None, description="Product description.")
    price_cents: Optional[int] = Field(None, ge=0, description="Price in cents.")
    currency: Optional[str] = Field(None, description="Currency code.")
    image_url: Optional[str] = Field(None, description="Optional image URL.")
    stock_quantity: Optional[int] = Field(None, ge=0, description="Available inventory.")
    is_active: Optional[bool] = Field(None, description="If false, product is hidden from browse.")


class ProductResponse(ProductBase):
    id: int = Field(..., description="Product id.")
    created_at: datetime = Field(..., description="Created timestamp.")
    updated_at: datetime = Field(..., description="Updated timestamp.")


class CartItemResponse(BaseModel):
    product: ProductResponse = Field(..., description="Product details snapshot (current).")
    quantity: int = Field(..., ge=1, description="Quantity in cart.")
    unit_price_cents: int = Field(..., ge=0, description="Unit price captured at add-time.")


class CartResponse(BaseModel):
    id: int = Field(..., description="Cart id.")
    status: str = Field(..., description="Cart status: active/converted/abandoned.")
    items: List[CartItemResponse] = Field(..., description="Cart line items.")
    subtotal_cents: int = Field(..., ge=0, description="Subtotal of items (sum qty*unit_price).")
    currency: str = Field(..., description="Currency code.")


class CartUpsertItemRequest(BaseModel):
    product_id: int = Field(..., description="Product id to add/update.")
    quantity: int = Field(..., ge=1, description="Desired quantity (>=1).")


class OrderItemResponse(BaseModel):
    product: ProductResponse = Field(..., description="Product details (current).")
    quantity: int = Field(..., ge=1, description="Quantity ordered.")
    unit_price_cents: int = Field(..., ge=0, description="Unit price at purchase time.")
    line_total_cents: int = Field(..., ge=0, description="quantity * unit_price_cents")


class OrderResponse(BaseModel):
    id: int = Field(..., description="Order id.")
    status: str = Field(..., description="Order status.")
    subtotal_cents: int = Field(..., ge=0, description="Order subtotal.")
    tax_cents: int = Field(..., ge=0, description="Tax amount.")
    shipping_cents: int = Field(..., ge=0, description="Shipping amount.")
    total_cents: int = Field(..., ge=0, description="Total amount.")
    currency: str = Field(..., description="Currency.")
    created_at: datetime = Field(..., description="Created timestamp.")
    items: List[OrderItemResponse] = Field(..., description="Order items.")


class CheckoutRequest(BaseModel):
    """
    Checkout request.

    Note: Payment is not processed here; this simply converts the active cart into a new order.
    """
    tax_cents: int = Field(0, ge=0, description="Tax override (optional).")
    shipping_cents: int = Field(0, ge=0, description="Shipping override (optional).")


class AdminUpdateOrderStatusRequest(BaseModel):
    status: str = Field(
        ...,
        description="New status: pending/paid/shipped/delivered/cancelled/refunded",
    )


TokenResponse.model_rebuild()
