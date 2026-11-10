from sqlmodel import Session

from app.models.product import Product


def get(session: Session, barcode: str) -> Product | None:
    return session.get(Product, barcode)


def save(session: Session, product: Product) -> Product:
    session.add(product)
    session.commit()
    session.refresh(product)
    return product
