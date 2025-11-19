import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

# Database helpers
from database import db, create_document, get_documents
from schemas import Product as ProductSchema

app = FastAPI(title="E-Commerce API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# ----------------------
# E-COMMERCE ENDPOINTS
# ----------------------

# Pydantic response model (includes id as string)
class ProductOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
    image: Optional[str] = None


class ProductIn(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0)
    category: str = Field(...)
    in_stock: bool = Field(True)
    image: Optional[str] = Field(None, description="Image URL")


def _doc_to_product_out(doc: dict) -> ProductOut:
    return ProductOut(
        id=str(doc.get("_id")),
        title=doc.get("title", ""),
        description=doc.get("description"),
        price=float(doc.get("price", 0)),
        category=doc.get("category", ""),
        in_stock=bool(doc.get("in_stock", True)),
        image=doc.get("image"),
    )


@app.get("/api/products", response_model=List[ProductOut])
def list_products(limit: Optional[int] = 24, category: Optional[str] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    filter_dict = {}
    if category:
        filter_dict["category"] = category

    docs = get_documents("product", filter_dict=filter_dict, limit=limit)
    return [_doc_to_product_out(d) for d in docs]


@app.post("/api/products", response_model=ProductOut, status_code=201)
def create_product(payload: ProductIn):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Validate with schemas.Product to keep consistency
    validated = ProductSchema(
        title=payload.title,
        description=payload.description,
        price=payload.price,
        category=payload.category,
        in_stock=payload.in_stock,
    )

    data = validated.model_dump()
    data["image"] = payload.image
    inserted_id = create_document("product", data)
    # Fetch created document
    doc = db["product"].find_one({"_id": ObjectId(inserted_id)})
    return _doc_to_product_out(doc)


@app.post("/api/products/seed", response_model=List[ProductOut])
def seed_products():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    count = db["product"].count_documents({})
    if count > 0:
        docs = get_documents("product", limit=24)
        return [_doc_to_product_out(d) for d in docs]

    samples = [
        {
            "title": "Aurora No. 01",
            "description": "Iridescent florals with a cool, glassy finish.",
            "price": 89.0,
            "category": "fragrance",
            "in_stock": True,
            "image": "https://images.unsplash.com/photo-1611930022073-b7a4ba5fcccd?q=80&w=1200&auto=format&fit=crop",
        },
        {
            "title": "Prism Eau de Parfum",
            "description": "A minimalist blend of citrus and white musk.",
            "price": 112.0,
            "category": "fragrance",
            "in_stock": True,
            "image": "https://images.unsplash.com/photo-1547887538-047f814b043e?q=80&w=1200&auto=format&fit=crop",
        },
        {
            "title": "Violet Glass",
            "description": "Powdery iris over clean cedar and skin.",
            "price": 98.0,
            "category": "fragrance",
            "in_stock": True,
            "image": "https://images.unsplash.com/photo-1610375461246-83df859d849e?q=80&w=1200&auto=format&fit=crop",
        },
        {
            "title": "Studio Light",
            "description": "Transparent amber with a soft, modern glow.",
            "price": 129.0,
            "category": "fragrance",
            "in_stock": True,
            "image": "https://images.unsplash.com/photo-1523293182086-7651a899d37f?q=80&w=1200&auto=format&fit=crop",
        },
    ]

    created_ids: List[str] = []
    for s in samples:
        validated = ProductSchema(**{k: s[k] for k in ["title", "description", "price", "category", "in_stock"]})
        data = validated.model_dump()
        data["image"] = s.get("image")
        new_id = create_document("product", data)
        created_ids.append(new_id)

    docs = db["product"].find({"_id": {"$in": [ObjectId(i) for i in created_ids]}})
    return [_doc_to_product_out(d) for d in docs]


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
