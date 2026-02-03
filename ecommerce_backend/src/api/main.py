import os
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes_auth import router as auth_router
from src.api.routes_cart import router as cart_router
from src.api.routes_orders import admin_router as admin_orders_router
from src.api.routes_orders import router as orders_router
from src.api.routes_products import admin_router as admin_products_router
from src.api.routes_products import router as products_router

openapi_tags = [
    {"name": "health", "description": "Health checks and service metadata."},
    {"name": "auth", "description": "User registration, login and profile."},
    {"name": "products", "description": "Product browse and search."},
    {"name": "cart", "description": "Shopping cart management."},
    {"name": "orders", "description": "Checkout and order history."},
    {"name": "admin-products", "description": "Admin product management."},
    {"name": "admin-orders", "description": "Admin order management."},
]


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _get_cors_allow_origins() -> List[str]:
    """
    Resolve CORS allow-origins.

    Env options:
      - CORS_ALLOW_ORIGINS: comma-separated exact origins (recommended for production)
      - CORS_ALLOW_ALL: if 'true', allow '*'

    Default:
      - allow '*' to make preview environments work out-of-the-box.
    """
    if (os.getenv("CORS_ALLOW_ALL") or "").strip().lower() in {"1", "true", "yes"}:
        return ["*"]

    explicit = _split_csv(os.getenv("CORS_ALLOW_ORIGINS"))
    return explicit if explicit else ["*"]


app = FastAPI(
    title="Modern E-Commerce API",
    description=(
        "FastAPI backend for the modern e-commerce app.\n\n"
        "Auth: Use `Authorization: Bearer <token>`.\n"
        "Admin: user.role must be `admin`."
    ),
    version="1.0.0",
    openapi_tags=openapi_tags,
)

allow_origins = _get_cors_allow_origins()

# Note: when allow_origins=["*"], Starlette's CORSMiddleware will not set
# Access-Control-Allow-Credentials=true safely. For preview this is usually OK.
# If you need credentials, set CORS_ALLOW_ORIGINS to the specific frontend origin(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    tags=["health"],
    summary="Health check",
    description="Simple health check endpoint.",
    operation_id="health_check",
)
def health_check():
    """Return basic health status."""
    return {"message": "Healthy"}


@app.get(
    "/docs/help",
    tags=["health"],
    summary="API usage notes",
    description="Quick notes on how to authenticate and use admin endpoints.",
    operation_id="docs_help",
)
def docs_help():
    """Return usage notes for this API."""
    return {
        "auth": {
            "register": "POST /auth/register",
            "login": "POST /auth/login",
            "me": "GET /auth/me (Authorization: Bearer <token>)",
        },
        "admin": {
            "products": "All /admin/products* endpoints require admin role",
            "orders": "All /admin/orders* endpoints require admin role",
        },
        "cors": {
            "env": {
                "CORS_ALLOW_ORIGINS": "comma-separated list of exact origins",
                "CORS_ALLOW_ALL": "true/false to allow all origins (preview default is allow-all)",
            }
        },
    }


app.include_router(auth_router)
app.include_router(products_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(admin_products_router)
app.include_router(admin_orders_router)
