from pydantic import BaseModel, Field
from typing import Optional


class Product(BaseModel):
    """Target schema for a single product extracted from an e-commerce listing page."""

    name: str = Field(description="The product's display name/title")
    price: float = Field(description="The current price the customer would pay (the sale price if discounted, not the crossed-out original price)")
    original_price: Optional[float] = Field(
        default=None,
        description="The original/regular price shown crossed-out, if the product is on sale. Null if not on sale.",
    )
    rating: Optional[float] = Field(default=None, description="The product's star rating, e.g. 4.5. Null if not shown.")
    image_url: Optional[str] = Field(default=None, description="URL of the product's main image")
    availability: str = Field(description="One of: 'in_stock', 
    'out_of_stock', or 'unknown'")
    needs_review: Optional[str] = Field(
        default=None,
        description=(
            "Set this to a short reason (e.g. 'ambiguous price: unclear if 12.0 is the sale "
            "price or a bundle price') ONLY if, after using vision to carefully re-examine the "
            "product's price/rating region, you still cannot confidently determine the correct "
            "value. Leave null if you are confident. Do NOT guess a value you are not confident "
            "about - flag it here instead."
        ),
    )


class ProductList(BaseModel):
    """A page's worth of extracted products."""

    products: list[Product] = Field(default_factory=list)
