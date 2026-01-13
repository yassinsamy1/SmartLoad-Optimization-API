"""
Pydantic models for the SmartLoad Optimization API.
All monetary values are in integer cents (64-bit) - never float/double.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import date


class Truck(BaseModel):
    """Truck capacity constraints."""
    id: str = Field(..., min_length=1, description="Unique truck identifier")
    max_weight_lbs: int = Field(..., gt=0, description="Maximum weight capacity in pounds")
    max_volume_cuft: int = Field(..., gt=0, description="Maximum volume capacity in cubic feet")


class Order(BaseModel):
    """Individual order/shipment details."""
    id: str = Field(..., min_length=1, description="Unique order identifier")
    payout_cents: int = Field(..., ge=0, description="Payout to carrier in cents (integer)")
    weight_lbs: int = Field(..., gt=0, description="Order weight in pounds")
    volume_cuft: int = Field(..., gt=0, description="Order volume in cubic feet")
    origin: str = Field(..., min_length=1, description="Origin city")
    destination: str = Field(..., min_length=1, description="Destination city")
    pickup_date: date = Field(..., description="Pickup date")
    delivery_date: date = Field(..., description="Delivery date")
    is_hazmat: bool = Field(default=False, description="Whether order contains hazardous materials")

    @field_validator('delivery_date')
    @classmethod
    def delivery_after_pickup(cls, v, info):
        """Ensure delivery date is on or after pickup date."""
        if 'pickup_date' in info.data and v < info.data['pickup_date']:
            raise ValueError('delivery_date must be on or after pickup_date')
        return v


class OptimizeRequest(BaseModel):
    """Request payload for load optimization."""
    truck: Truck
    orders: List[Order] = Field(..., max_length=25, description="List of available orders (max 25)")

    @field_validator('orders')
    @classmethod
    def orders_not_empty_if_present(cls, v):
        """Orders list can be empty but must be a list."""
        return v


class OptimizeResponse(BaseModel):
    """Response payload with optimal order combination."""
    truck_id: str
    selected_order_ids: List[str]
    total_payout_cents: int  # Integer cents - never float
    total_weight_lbs: int
    total_volume_cuft: int
    utilization_weight_percent: float = Field(..., ge=0, le=100)
    utilization_volume_percent: float = Field(..., ge=0, le=100)


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
