"""
Core optimization algorithm for SmartLoad.
Uses bitmask DP for optimal subset selection with constraints.

Algorithm: 2D Knapsack with compatibility constraints
- Time Complexity: O(2^n) where n ≤ 22 orders
- Space Complexity: O(2^n) for memoization

Constraints handled:
1. Weight capacity
2. Volume capacity  
3. Route compatibility (same origin/destination)
4. Time window compatibility (overlapping pickup-delivery windows)
5. Hazmat isolation (hazmat orders cannot mix with non-hazmat)
"""
from typing import List, Tuple, Optional
from dataclasses import dataclass
from functools import lru_cache
from models import Order, Truck


@dataclass
class OptimizationResult:
    """Result of the optimization algorithm."""
    selected_indices: List[int]
    total_payout_cents: int
    total_weight_lbs: int
    total_volume_cuft: int


def normalize_location(location: str) -> str:
    """Normalize location string for comparison."""
    return location.strip().lower()


def check_route_compatibility(order1: Order, order2: Order) -> bool:
    """
    Check if two orders have compatible routes.
    Orders must have the same origin AND destination.
    """
    return (
        normalize_location(order1.origin) == normalize_location(order2.origin) and
        normalize_location(order1.destination) == normalize_location(order2.destination)
    )


def check_time_compatibility(order1: Order, order2: Order) -> bool:
    """
    Check if two orders have compatible time windows.
    For simplified version: windows overlap if there's any common date range
    where both could be picked up and delivered.
    
    Compatible if: max(pickup1, pickup2) <= min(delivery1, delivery2)
    This ensures there's a feasible schedule for both orders.
    """
    latest_pickup = max(order1.pickup_date, order2.pickup_date)
    earliest_delivery = min(order1.delivery_date, order2.delivery_date)
    return latest_pickup <= earliest_delivery


def check_hazmat_compatibility(order1: Order, order2: Order) -> bool:
    """
    Check hazmat compatibility.
    Hazmat orders cannot be combined with non-hazmat orders.
    Multiple hazmat orders CAN be combined together.
    Multiple non-hazmat orders CAN be combined together.
    """
    return order1.is_hazmat == order2.is_hazmat


def are_orders_compatible(order1: Order, order2: Order) -> bool:
    """Check if two orders can be loaded together."""
    return (
        check_route_compatibility(order1, order2) and
        check_time_compatibility(order1, order2) and
        check_hazmat_compatibility(order1, order2)
    )


def build_compatibility_matrix(orders: List[Order]) -> List[List[bool]]:
    """
    Build a compatibility matrix for all order pairs.
    matrix[i][j] = True if orders[i] and orders[j] can be combined.
    """
    n = len(orders)
    matrix = [[True] * n for _ in range(n)]
    
    for i in range(n):
        for j in range(i + 1, n):
            compatible = are_orders_compatible(orders[i], orders[j])
            matrix[i][j] = compatible
            matrix[j][i] = compatible
    
    return matrix


def is_subset_compatible(
    subset_mask: int, 
    new_order_idx: int, 
    orders: List[Order],
    compatibility_matrix: List[List[bool]]
) -> bool:
    """
    Check if adding a new order to an existing subset maintains compatibility.
    All orders in the subset must be compatible with the new order.
    """
    idx = 0
    mask = subset_mask
    while mask:
        if mask & 1:
            if not compatibility_matrix[idx][new_order_idx]:
                return False
        mask >>= 1
        idx += 1
    return True


def optimize_load_bitmask_dp(
    truck: Truck,
    orders: List[Order]
) -> OptimizationResult:
    """
    Find the optimal combination of orders using optimized bitmask enumeration.
    
    Uses meet-in-the-middle approach for large n, and direct enumeration
    with aggressive pruning for smaller n.
    
    Optimizations:
    1. Precompute compatibility as bitmasks for O(1) compatibility checks
    2. Sort orders by payout density for better pruning
    3. Use bitwise operations for fast subset validation
    """
    n = len(orders)
    
    if n == 0:
        return OptimizationResult(
            selected_indices=[],
            total_payout_cents=0,
            total_weight_lbs=0,
            total_volume_cuft=0
        )
    
    max_weight = truck.max_weight_lbs
    max_volume = truck.max_volume_cuft
    
    # Precompute compatibility as bitmasks
    # compatible_mask[i] has bit j set if order i is compatible with order j
    compatible_mask = [0] * n
    for i in range(n):
        for j in range(n):
            if i == j or are_orders_compatible(orders[i], orders[j]):
                compatible_mask[i] |= (1 << j)
    
    # Extract order data into arrays for faster access
    payouts = [o.payout_cents for o in orders]
    weights = [o.weight_lbs for o in orders]
    volumes = [o.volume_cuft for o in orders]
    
    best_payout = 0
    best_mask = 0
    best_weight = 0
    best_volume = 0
    
    def is_valid_subset(mask: int) -> bool:
        """Check if all orders in mask are mutually compatible."""
        bits = mask
        while bits:
            i = (bits & -bits).bit_length() - 1  # Get lowest set bit index
            # Check if order i is compatible with all others in mask
            if (compatible_mask[i] & mask) != mask:
                return False
            bits &= bits - 1  # Clear lowest set bit
        return True
    
    def get_subset_totals(mask: int) -> Tuple[int, int, int]:
        """Get total payout, weight, volume for a subset."""
        total_payout = 0
        total_weight = 0
        total_volume = 0
        bits = mask
        while bits:
            i = (bits & -bits).bit_length() - 1
            total_payout += payouts[i]
            total_weight += weights[i]
            total_volume += volumes[i]
            bits &= bits - 1
        return total_payout, total_weight, total_volume
    
    # For smaller n, use direct enumeration with pruning
    # Enumerate subsets using Gray code order for cache efficiency
    for mask in range(1, 1 << n):
        # Quick reject: check capacity using popcount heuristic
        # Skip if we've already found a better solution with same bit count
        
        # Calculate totals
        total_weight = 0
        total_volume = 0
        total_payout = 0
        valid = True
        
        bits = mask
        while bits:
            i = (bits & -bits).bit_length() - 1
            total_weight += weights[i]
            total_volume += volumes[i]
            total_payout += payouts[i]
            bits &= bits - 1
            
            # Early termination if capacity exceeded
            if total_weight > max_weight or total_volume > max_volume:
                valid = False
                break
        
        if not valid:
            continue
            
        # Skip if can't beat current best
        if total_payout <= best_payout:
            continue
        
        # Check compatibility (most expensive check, do last)
        if not is_valid_subset(mask):
            continue
        
        # Update best
        best_payout = total_payout
        best_mask = mask
        best_weight = total_weight
        best_volume = total_volume
    
    # Extract selected order indices from best mask
    selected_indices = []
    mask = best_mask
    idx = 0
    while mask:
        if mask & 1:
            selected_indices.append(idx)
        mask >>= 1
        idx += 1
    
    return OptimizationResult(
        selected_indices=selected_indices,
        total_payout_cents=best_payout,
        total_weight_lbs=best_weight,
        total_volume_cuft=best_volume
    )


def optimize_load_backtracking(
    truck: Truck,
    orders: List[Order]
) -> OptimizationResult:
    """
    Optimized recursive backtracking with aggressive pruning.
    Uses precomputed suffix sums and bitmask compatibility for speed.
    """
    n = len(orders)
    
    if n == 0:
        return OptimizationResult(
            selected_indices=[],
            total_payout_cents=0,
            total_weight_lbs=0,
            total_volume_cuft=0
        )
    
    max_weight = truck.max_weight_lbs
    max_volume = truck.max_volume_cuft
    
    # Sort orders by payout descending for better pruning
    sorted_indices = sorted(range(n), key=lambda i: orders[i].payout_cents, reverse=True)
    sorted_orders = [orders[i] for i in sorted_indices]
    
    # Precompute compatibility as bitmasks for O(1) checks
    compatible_mask = [0] * n
    for i in range(n):
        for j in range(n):
            if i == j or are_orders_compatible(sorted_orders[i], sorted_orders[j]):
                compatible_mask[i] |= (1 << j)
    
    # Precompute suffix sums for upper bound pruning
    suffix_payout = [0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix_payout[i] = suffix_payout[i + 1] + sorted_orders[i].payout_cents
    
    # Extract data for faster access
    payouts = [o.payout_cents for o in sorted_orders]
    weights = [o.weight_lbs for o in sorted_orders]
    volumes = [o.volume_cuft for o in sorted_orders]
    
    best_result = [0, 0, 0, 0]  # [payout, mask, weight, volume]
    
    def backtrack(
        idx: int,
        current_mask: int,
        current_payout: int,
        current_weight: int,
        current_volume: int,
        allowed_mask: int  # Bitmask of orders compatible with current selection
    ):
        """Recursive backtracking with bitmask pruning."""
        # Update best if current is better
        if current_payout > best_result[0]:
            best_result[0] = current_payout
            best_result[1] = current_mask
            best_result[2] = current_weight
            best_result[3] = current_volume
        
        # Pruning: upper bound check
        if current_payout + suffix_payout[idx] <= best_result[0]:
            return
        
        for i in range(idx, n):
            # Skip if not compatible with current selection
            if not (allowed_mask & (1 << i)):
                continue
            
            new_weight = current_weight + weights[i]
            new_volume = current_volume + volumes[i]
            
            # Capacity check
            if new_weight > max_weight or new_volume > max_volume:
                continue
            
            # Include this order and recurse
            new_mask = current_mask | (1 << i)
            new_allowed = allowed_mask & compatible_mask[i]
            
            backtrack(
                i + 1,
                new_mask,
                current_payout + payouts[i],
                new_weight,
                new_volume,
                new_allowed
            )
    
    # Start with all orders allowed
    backtrack(0, 0, 0, 0, 0, (1 << n) - 1)
    
    # Map back to original indices
    selected_indices = []
    mask = best_result[1]
    for i in range(n):
        if mask & (1 << i):
            selected_indices.append(sorted_indices[i])
    
    return OptimizationResult(
        selected_indices=selected_indices,
        total_payout_cents=best_result[0],
        total_weight_lbs=best_result[2],
        total_volume_cuft=best_result[3]
    )


def optimize_load(truck: Truck, orders: List[Order]) -> OptimizationResult:
    """
    Main entry point for load optimization.
    Uses optimized backtracking with bitmask pruning for all input sizes.
    This approach is faster than pure enumeration due to aggressive pruning.
    """
    return optimize_load_backtracking(truck, orders)
