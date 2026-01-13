"""
SmartLoad Optimization API - Main Application

A stateless REST API for optimizing truck load combinations.
Finds the most profitable set of orders that fit within truck capacity
and satisfy all compatibility constraints.

Endpoints:
- POST /api/v1/load-optimizer/optimize - Optimize load selection
- GET /healthz - Health check
- GET /api/v1/load-optimizer/info - API information
"""
import time
from typing import List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from models import (
    OptimizeRequest, 
    OptimizeResponse, 
    ErrorResponse,
    Order
)
from optimizer import optimize_load


# Constants
MAX_ORDERS = 25  # Maximum orders allowed per request
MAX_PAYLOAD_SIZE = 1024 * 1024  # 1 MB max payload


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("SmartLoad Optimization API starting...")
    yield
    # Shutdown
    print("SmartLoad Optimization API shutting down...")


app = FastAPI(
    title="SmartLoad Optimization API",
    description="Optimal truck load planning service for carrier logistics",
    version="1.0.0",
    lifespan=lifespan
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with proper 400 status."""
    errors = []
    for error in exc.errors():
        loc = " -> ".join(str(x) for x in error["loc"])
        errors.append(f"{loc}: {error['msg']}")
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Validation Error",
            "detail": "; ".join(errors)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": str(exc)
        }
    )


# Middleware for payload size check
@app.middleware("http")
async def check_payload_size(request: Request, call_next):
    """Check if payload exceeds maximum size."""
    if request.method == "POST":
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_PAYLOAD_SIZE:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error": "Payload Too Large",
                    "detail": f"Request body exceeds maximum size of {MAX_PAYLOAD_SIZE} bytes"
                }
            )
    return await call_next(request)


# Health check endpoints
@app.get("/healthz", tags=["Health"])
@app.get("/actuator/health", tags=["Health"])
async def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "UP", "service": "smartload-optimizer"}


@app.get("/api/v1/load-optimizer/info", tags=["Info"])
async def api_info():
    """API information endpoint."""
    return {
        "service": "SmartLoad Optimization API",
        "version": "1.0.0",
        "description": "Optimal truck load planning for carrier logistics",
        "constraints": {
            "max_orders": MAX_ORDERS,
            "max_payload_bytes": MAX_PAYLOAD_SIZE
        },
        "algorithm": "Bitmask DP / Backtracking with pruning"
    }


@app.post(
    "/api/v1/load-optimizer/optimize",
    response_model=OptimizeResponse,
    responses={
        200: {"description": "Optimization successful", "model": OptimizeResponse},
        400: {"description": "Invalid request", "model": ErrorResponse},
        413: {"description": "Payload too large", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    tags=["Optimization"]
)
async def optimize_truck_load(request: OptimizeRequest):
    """
    Optimize truck load selection.
    
    Finds the optimal combination of orders that:
    - Maximizes total payout (revenue)
    - Respects truck weight and volume capacity
    - Ensures all orders are compatible (same route, time windows, hazmat)
    
    **Algorithm**: Uses bitmask dynamic programming for up to 22 orders,
    with recursive backtracking as fallback. Guaranteed optimal solution.
    
    **Performance**: < 800ms for 22 orders on typical hardware.
    
    **Constraints**:
    - Maximum 25 orders per request
    - All monetary values in integer cents (never float)
    - Hazmat orders cannot be combined with non-hazmat orders
    - Orders must share the same origin and destination
    - Time windows must overlap (feasible pickup-delivery schedule)
    """
    start_time = time.time()
    
    truck = request.truck
    orders = request.orders
    
    # Validate order count
    if len(orders) > MAX_ORDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many orders: {len(orders)}. Maximum allowed: {MAX_ORDERS}"
        )
    
    # Handle empty orders case
    if not orders:
        return OptimizeResponse(
            truck_id=truck.id,
            selected_order_ids=[],
            total_payout_cents=0,
            total_weight_lbs=0,
            total_volume_cuft=0,
            utilization_weight_percent=0.0,
            utilization_volume_percent=0.0
        )
    
    # Validate individual orders don't exceed truck capacity
    valid_orders: List[Order] = []
    order_map = {}  # index -> original order for ID lookup
    
    for i, order in enumerate(orders):
        # Skip orders that individually exceed truck capacity
        if order.weight_lbs > truck.max_weight_lbs:
            continue
        if order.volume_cuft > truck.max_volume_cuft:
            continue
        
        valid_orders.append(order)
        order_map[len(valid_orders) - 1] = order
    
    # Handle case where no orders fit
    if not valid_orders:
        return OptimizeResponse(
            truck_id=truck.id,
            selected_order_ids=[],
            total_payout_cents=0,
            total_weight_lbs=0,
            total_volume_cuft=0,
            utilization_weight_percent=0.0,
            utilization_volume_percent=0.0
        )
    
    # Run optimization
    result = optimize_load(truck, valid_orders)
    
    # Map indices back to order IDs
    selected_order_ids = [
        order_map[idx].id for idx in result.selected_indices
    ]
    
    # Calculate utilization percentages
    utilization_weight = (result.total_weight_lbs / truck.max_weight_lbs) * 100
    utilization_volume = (result.total_volume_cuft / truck.max_volume_cuft) * 100
    
    elapsed_time = time.time() - start_time
    
    # Log performance (in production, use proper logging)
    print(f"Optimization completed in {elapsed_time*1000:.2f}ms for {len(orders)} orders")
    
    return OptimizeResponse(
        truck_id=truck.id,
        selected_order_ids=selected_order_ids,
        total_payout_cents=result.total_payout_cents,
        total_weight_lbs=result.total_weight_lbs,
        total_volume_cuft=result.total_volume_cuft,
        utilization_weight_percent=round(utilization_weight, 2),
        utilization_volume_percent=round(utilization_volume, 2)
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
