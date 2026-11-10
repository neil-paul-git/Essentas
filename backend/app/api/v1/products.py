from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.api.deps import FoodDataProviderDep, SessionDep, get_current_user
from app.schemas.product import BARCODE_PATTERN, ProductRead
from app.services import products as products_service

# Login required: only signed-in users can make us spend Open Food Facts quota.
router = APIRouter(prefix="/products", tags=["products"], dependencies=[Depends(get_current_user)])

Barcode = Annotated[
    str,
    Path(pattern=BARCODE_PATTERN, description="EAN-8, UPC-A, EAN-13 or GTIN-14 (digits only)"),
]


@router.get(
    "/{barcode}",
    response_model=ProductRead,
    responses={
        404: {"description": "No product with this barcode"},
        503: {"description": "Product database temporarily unavailable"},
    },
)
def get_product(
    barcode: Barcode, session: SessionDep, provider: FoodDataProviderDep
) -> ProductRead:
    product = products_service.lookup_product(session, provider, barcode)
    return ProductRead.model_validate(product)
