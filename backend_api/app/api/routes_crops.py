from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, status

from backend_api.app.models.schemas import (
    ONDCCropListing,
    ONDCCropListingUpdate,
    FarmerCropListingCreate,
    FarmerCropListingUpdate,
    CropCategory,
    QualityGrade,
    WeightUnit
)
from backend_api.app.services.database import db_manager, insert_document, query_documents
from backend_api.app.services.redis_manager import redis_manager
from backend_api.app.services.ml_runner import ml_runner

logger = logging.getLogger("mandisync.crops")
router = APIRouter(prefix="/crops", tags=["Crop Listings (CRUD)"])


def clean_mongo_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


@router.post(
    "",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Create Farmer Crop Listing",
    description="Add a new farmer crop listing to MongoDB using Pydantic validation with optional AI price enrichment."
)
async def create_crop_listing(listing: Union[ONDCCropListing, FarmerCropListingCreate]):
    collection = db_manager.get_collection("crops")

    if isinstance(listing, FarmerCropListingCreate):
        # Transform simplified farmer input into standardized document structure
        crop_id = f"CROP-{listing.crop_name[:4].upper()}-{uuid4().hex[:8]}"
        doc = {
            "id": crop_id,
            "crop_name": listing.crop_name,
            "descriptor": {
                "name": listing.crop_name,
                "short_desc": f"Fresh farm harvest of {listing.crop_name} from {listing.location}",
                "images": []
            },
            "category": listing.category.value if listing.category else "VEGETABLE",
            "price": {
                "currency": "INR",
                "value": listing.price,
                "estimated_mrp": round(listing.price * 1.15, 2)
            },
            "quantity": {
                "unit": listing.unit.value if hasattr(listing.unit, "value") else str(listing.unit),
                "available_quantity": listing.quantity,
                "min_order_quantity": 1.0
            },
            "mandi_info": {
                "mandi_id": f"MANDI-{listing.location[:4].upper()}",
                "market_name": listing.location,
                "district": listing.district or listing.location,
                "state": listing.state or "Maharashtra"
            },
            "variety": listing.variety or "Standard",
            "grade": listing.grade.value if hasattr(listing.grade, "value") else str(listing.grade),
            "farmer_id": listing.farmer_id or f"FARMER-{uuid4().hex[:6]}",
            "farmer_name": listing.farmer_name or "Verified Farmer",
            "status": listing.status or "active",
            "tags": {"source": "farmer_direct_portal"},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        # Enrich with AI price prediction if available
        if ml_runner.is_ready:
            try:
                pred = ml_runner.predict(
                    commodity=listing.crop_name,
                    market=listing.location,
                    modal_price_lag1=listing.price,
                    variety=listing.variety or "Standard"
                )
                doc["ai_predicted_max_price"] = pred.predicted_max_price
                doc["ai_recommended_msp"] = pred.recommended_listing_price
                doc["tags"]["ai_model_version"] = pred.model_version
            except Exception as exc:
                logger.warning(f"AI price forecast enrichment skipped: {exc}")

        inserted_id = await insert_document("crops", doc)
        doc["_id"] = inserted_id
        await redis_manager.delete_pattern("crops:list:*")
        return doc

    else:
        # ONDCCropListing flow
        existing = await collection.find_one({"id": listing.id})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Crop listing with ID '{listing.id}' already exists."
            )

        # Enrich with AI price prediction if available and not manually set
        if ml_runner.is_ready and (listing.ai_predicted_max_price is None or listing.ai_recommended_msp is None):
            try:
                pred = ml_runner.predict(
                    commodity=listing.descriptor.name.split()[0],
                    market=listing.mandi_info.market_name.split()[0],
                    modal_price_lag1=listing.price.value,
                    variety=listing.variety
                )
                if listing.ai_predicted_max_price is None:
                    listing.ai_predicted_max_price = pred.predicted_max_price
                if listing.ai_recommended_msp is None:
                    listing.ai_recommended_msp = pred.recommended_listing_price
                listing.tags["ai_model_version"] = pred.model_version
            except Exception as exc:
                logger.warning(f"AI enrichment skipped: {exc}")

        doc = listing.model_dump(mode="json")
        if "status" not in doc:
            doc["status"] = "active"
            
        inserted_id = await insert_document("crops", doc)
        doc["_id"] = inserted_id
        await redis_manager.delete_pattern("crops:list:*")
        logger.info(f"Created crop listing '{listing.id}' in 'crops' collection.")
        return doc


@router.get(
    "",
    response_model=List[Dict[str, Any]],
    summary="List Active Crop Listings",
    description="Retrieve all active crop listings from MongoDB with optional filtering by crop name, location, category, or grade."
)
async def list_crop_listings(
    crop_name: Optional[str] = Query(None, description="Filter by crop name e.g. Onion, Tomato, Potato"),
    commodity: Optional[str] = Query(None, description="Alias for crop name"),
    location: Optional[str] = Query(None, description="Filter by mandi, market, district, or state"),
    mandi: Optional[str] = Query(None, description="Alias for mandi/market name"),
    status: Optional[str] = Query("active", description="Filter by listing status (default: 'active')"),
    category: Optional[CropCategory] = Query(None, description="Filter by crop category"),
    grade: Optional[QualityGrade] = Query(None, description="Filter by quality grade"),
    skip: int = Query(0, ge=0, description="Number of listings to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max listings to return")
):
    category_val = category.value if category else "None"
    grade_val = grade.value if grade else "None"
    cache_key_raw = f"crops:list:{crop_name}:{commodity}:{location}:{mandi}:{status}:{category_val}:{grade_val}:{skip}:{limit}"
    import hashlib
    cache_key = "crops:list:" + hashlib.md5(cache_key_raw.encode()).hexdigest()
    
    cached_data = await redis_manager.get_cache(cache_key)
    if cached_data:
        return cached_data

    query: Dict[str, Any] = {}

    # Active status filter (treat missing status as active for backward compatibility)
    if status:
        query["$and"] = [
            {"$or": [{"status": status}, {"status": {"$exists": False}}]}
        ]

    crop_term = crop_name or commodity
    if crop_term:
        crop_match = {
            "$or": [
                {"descriptor.name": {"$regex": crop_term, "$options": "i"}},
                {"crop_name": {"$regex": crop_term, "$options": "i"}},
                {"variety": {"$regex": crop_term, "$options": "i"}}
            ]
        }
        if "$and" in query:
            query["$and"].append(crop_match)
        else:
            query.update(crop_match)

    loc_term = location or mandi
    if loc_term:
        loc_match = {
            "$or": [
                {"mandi_info.market_name": {"$regex": loc_term, "$options": "i"}},
                {"mandi_info.district": {"$regex": loc_term, "$options": "i"}},
                {"mandi_info.state": {"$regex": loc_term, "$options": "i"}},
                {"location": {"$regex": loc_term, "$options": "i"}}
            ]
        }
        if "$and" in query:
            query["$and"].append(loc_match)
        else:
            query.update(loc_match)

    if category:
        query["category"] = category.value
    if grade:
        query["grade"] = grade.value

    docs = await query_documents("crops", filter_query=query, limit=limit, skip=skip, sort=[("_id", -1)])
    await redis_manager.set_cache(cache_key, docs, expire_seconds=300)
    return docs


@router.get(
    "/{crop_id}",
    response_model=Dict[str, Any],
    summary="Get Crop Listing by ID",
    description="Fetch a single crop listing by its SKU ID or MongoDB ObjectId."
)
async def get_crop_listing(crop_id: str):
    cache_key = f"crop:{crop_id}"
    cached_data = await redis_manager.get_cache(cache_key)
    if cached_data:
        return cached_data

    collection = db_manager.get_collection("crops")

    doc = await collection.find_one({"id": crop_id})
    if not doc and ObjectId.is_valid(crop_id):
        doc = await collection.find_one({"_id": ObjectId(crop_id)})

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crop listing '{crop_id}' not found."
        )

    cleaned_doc = clean_mongo_doc(doc)
    await redis_manager.set_cache(cache_key, cleaned_doc, expire_seconds=300)
    return cleaned_doc


@router.put(
    "/{crop_id}",
    response_model=Dict[str, Any],
    summary="Replace Crop Listing",
    description="Fully replace an existing crop listing using ONDC format or farmer direct format."
)
async def replace_crop_listing(crop_id: str, listing: Union[ONDCCropListing, FarmerCropListingCreate]):
    collection = db_manager.get_collection("crops")
    
    query = {"$or": [{"id": crop_id}, {"_id": crop_id}] + ([{"_id": ObjectId(crop_id)}] if ObjectId.is_valid(crop_id) else [])}
    existing = await collection.find_one(query)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crop listing '{crop_id}' not found to replace."
        )

    if isinstance(listing, FarmerCropListingCreate):
        doc = {
            "id": crop_id,
            "crop_name": listing.crop_name,
            "descriptor": {
                "name": listing.crop_name,
                "short_desc": f"Fresh farm harvest of {listing.crop_name} from {listing.location}",
                "images": existing.get("descriptor", {}).get("images", []) if isinstance(existing.get("descriptor"), dict) else []
            },
            "category": listing.category.value if listing.category else "VEGETABLE",
            "price": {
                "currency": "INR",
                "value": listing.price,
                "estimated_mrp": round(listing.price * 1.15, 2)
            },
            "quantity": {
                "unit": listing.unit.value if hasattr(listing.unit, "value") else str(listing.unit),
                "available_quantity": listing.quantity,
                "min_order_quantity": 1.0
            },
            "mandi_info": {
                "mandi_id": f"MANDI-{listing.location[:4].upper()}",
                "market_name": listing.location,
                "district": listing.district or listing.location,
                "state": listing.state or "Maharashtra"
            },
            "variety": listing.variety or "Standard",
            "grade": listing.grade.value if hasattr(listing.grade, "value") else str(listing.grade),
            "farmer_id": listing.farmer_id or existing.get("farmer_id") or f"FARMER-{uuid4().hex[:6]}",
            "farmer_name": listing.farmer_name or existing.get("farmer_name") or "Verified Farmer",
            "status": listing.status or "active",
            "tags": existing.get("tags", {"source": "farmer_direct_portal"}),
            "created_at": existing.get("created_at", datetime.now(timezone.utc).isoformat()),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    else:
        doc = listing.model_dump(mode="json")
        doc["id"] = crop_id
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()
        if "status" not in doc:
            doc["status"] = "active"

    if "_id" in existing:
        doc["_id"] = existing["_id"]

    await collection.replace_one(query, doc)
    await redis_manager.delete_pattern("crops:list:*")
    await redis_manager.delete_cache(f"crop:{crop_id}")
    logger.info(f"Replaced crop listing '{crop_id}'.")
    return clean_mongo_doc(doc)


@router.patch(
    "/{crop_id}",
    response_model=Dict[str, Any],
    summary="Update Crop Listing (Partial)",
    description="Partially update specific fields of an existing crop listing."
)
async def update_crop_listing(crop_id: str, patch: Union[ONDCCropListingUpdate, FarmerCropListingUpdate, Dict[str, Any]]):
    collection = db_manager.get_collection("crops")

    if hasattr(patch, "model_dump"):
        raw_patch = patch.model_dump(mode="json", exclude_unset=True)
    elif isinstance(patch, dict):
        raw_patch = patch
    else:
        raw_patch = dict(patch)

    raw_data = {k: v for k, v in raw_patch.items() if v is not None}
    if not raw_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid fields provided for update."
        )

    update_data: Dict[str, Any] = {}
    for k, v in raw_data.items():
        if k == "crop_name":
            update_data["crop_name"] = v
            update_data["descriptor.name"] = v
        elif k == "price":
            if isinstance(v, (int, float)):
                update_data["price.value"] = float(v)
            elif isinstance(v, dict):
                update_data["price"] = v
        elif k == "quantity":
            if isinstance(v, (int, float)):
                update_data["quantity.available_quantity"] = float(v)
            elif isinstance(v, dict):
                update_data["quantity"] = v
        elif k == "unit":
            unit_val = v.value if hasattr(v, "value") else str(v)
            update_data["quantity.unit"] = unit_val
        elif k == "location":
            update_data["location"] = v
            update_data["mandi_info.market_name"] = v
        elif k == "district":
            update_data["district"] = v
            update_data["mandi_info.district"] = v
        elif k == "state":
            update_data["state"] = v
            update_data["mandi_info.state"] = v
        else:
            update_data[k] = v.value if hasattr(v, "value") else v

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    query = {"$or": [{"id": crop_id}, {"_id": crop_id}] + ([{"_id": ObjectId(crop_id)}] if ObjectId.is_valid(crop_id) else [])}
    res = await collection.find_one_and_update(
        query,
        {"$set": update_data},
        return_document=True
    )

    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crop listing '{crop_id}' not found to update."
        )

    logger.info(f"Updated crop listing '{crop_id}'.")
    await redis_manager.delete_pattern("crops:list:*")
    await redis_manager.delete_cache(f"crop:{crop_id}")
    return clean_mongo_doc(res)


@router.delete(
    "/{crop_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Crop Listing",
    description="Remove a crop listing from the database."
)
async def delete_crop_listing(crop_id: str):
    collection = db_manager.get_collection("crops")

    query = {"$or": [{"id": crop_id}, {"_id": crop_id}] + ([{"_id": ObjectId(crop_id)}] if ObjectId.is_valid(crop_id) else [])}
    res = await collection.delete_one(query)

    if res.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crop listing '{crop_id}' not found to delete."
        )

    logger.info(f"Deleted crop listing '{crop_id}'.")
    await redis_manager.delete_pattern("crops:list:*")
    await redis_manager.delete_cache(f"crop:{crop_id}")
    return {"status": "success", "message": f"Crop listing '{crop_id}' deleted successfully."}
