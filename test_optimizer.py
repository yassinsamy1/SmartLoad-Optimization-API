"""
Unit tests for the SmartLoad Optimization API.
Run with: pytest test_optimizer.py -v
"""
import pytest
from datetime import date
from models import Truck, Order, OptimizeRequest
from optimizer import (
    optimize_load,
    check_route_compatibility,
    check_time_compatibility,
    check_hazmat_compatibility,
    are_orders_compatible,
    build_compatibility_matrix
)


# Test Fixtures
@pytest.fixture
def sample_truck():
    return Truck(
        id="truck-123",
        max_weight_lbs=44000,
        max_volume_cuft=3000
    )


@pytest.fixture
def compatible_orders():
    """Orders that are all compatible with each other."""
    return [
        Order(
            id="ord-001",
            payout_cents=250000,
            weight_lbs=18000,
            volume_cuft=1200,
            origin="Los Angeles, CA",
            destination="Dallas, TX",
            pickup_date=date(2025, 12, 5),
            delivery_date=date(2025, 12, 9),
            is_hazmat=False
        ),
        Order(
            id="ord-002",
            payout_cents=180000,
            weight_lbs=12000,
            volume_cuft=900,
            origin="Los Angeles, CA",
            destination="Dallas, TX",
            pickup_date=date(2025, 12, 4),
            delivery_date=date(2025, 12, 10),
            is_hazmat=False
        )
    ]


@pytest.fixture
def hazmat_order():
    return Order(
        id="ord-003",
        payout_cents=320000,
        weight_lbs=30000,
        volume_cuft=1800,
        origin="Los Angeles, CA",
        destination="Dallas, TX",
        pickup_date=date(2025, 12, 6),
        delivery_date=date(2025, 12, 8),
        is_hazmat=True
    )


# Compatibility Tests
class TestCompatibility:
    
    def test_route_compatibility_same(self, compatible_orders):
        """Orders with same origin/destination are compatible."""
        assert check_route_compatibility(
            compatible_orders[0], 
            compatible_orders[1]
        ) is True
    
    def test_route_compatibility_different_origin(self, compatible_orders, hazmat_order):
        """Orders with different origins are not compatible."""
        order1 = compatible_orders[0]
        order2 = Order(
            id="ord-diff",
            payout_cents=100000,
            weight_lbs=5000,
            volume_cuft=500,
            origin="New York, NY",  # Different origin
            destination="Dallas, TX",
            pickup_date=date(2025, 12, 5),
            delivery_date=date(2025, 12, 9),
            is_hazmat=False
        )
        assert check_route_compatibility(order1, order2) is False
    
    def test_route_compatibility_different_destination(self, compatible_orders):
        """Orders with different destinations are not compatible."""
        order1 = compatible_orders[0]
        order2 = Order(
            id="ord-diff",
            payout_cents=100000,
            weight_lbs=5000,
            volume_cuft=500,
            origin="Los Angeles, CA",
            destination="Houston, TX",  # Different destination
            pickup_date=date(2025, 12, 5),
            delivery_date=date(2025, 12, 9),
            is_hazmat=False
        )
        assert check_route_compatibility(order1, order2) is False
    
    def test_time_compatibility_overlapping(self, compatible_orders):
        """Orders with overlapping time windows are compatible."""
        assert check_time_compatibility(
            compatible_orders[0], 
            compatible_orders[1]
        ) is True
    
    def test_time_compatibility_non_overlapping(self):
        """Orders with non-overlapping time windows are not compatible."""
        order1 = Order(
            id="ord-1",
            payout_cents=100000,
            weight_lbs=5000,
            volume_cuft=500,
            origin="Los Angeles, CA",
            destination="Dallas, TX",
            pickup_date=date(2025, 12, 1),
            delivery_date=date(2025, 12, 3),
            is_hazmat=False
        )
        order2 = Order(
            id="ord-2",
            payout_cents=100000,
            weight_lbs=5000,
            volume_cuft=500,
            origin="Los Angeles, CA",
            destination="Dallas, TX",
            pickup_date=date(2025, 12, 5),
            delivery_date=date(2025, 12, 8),
            is_hazmat=False
        )
        assert check_time_compatibility(order1, order2) is False
    
    def test_hazmat_compatibility_both_hazmat(self):
        """Two hazmat orders are compatible."""
        order1 = Order(
            id="ord-1",
            payout_cents=100000,
            weight_lbs=5000,
            volume_cuft=500,
            origin="Los Angeles, CA",
            destination="Dallas, TX",
            pickup_date=date(2025, 12, 5),
            delivery_date=date(2025, 12, 9),
            is_hazmat=True
        )
        order2 = Order(
            id="ord-2",
            payout_cents=100000,
            weight_lbs=5000,
            volume_cuft=500,
            origin="Los Angeles, CA",
            destination="Dallas, TX",
            pickup_date=date(2025, 12, 5),
            delivery_date=date(2025, 12, 9),
            is_hazmat=True
        )
        assert check_hazmat_compatibility(order1, order2) is True
    
    def test_hazmat_compatibility_both_non_hazmat(self, compatible_orders):
        """Two non-hazmat orders are compatible."""
        assert check_hazmat_compatibility(
            compatible_orders[0], 
            compatible_orders[1]
        ) is True
    
    def test_hazmat_compatibility_mixed(self, compatible_orders, hazmat_order):
        """Hazmat and non-hazmat orders are not compatible."""
        assert check_hazmat_compatibility(
            compatible_orders[0], 
            hazmat_order
        ) is False


# Optimization Tests
class TestOptimization:
    
    def test_empty_orders(self, sample_truck):
        """Empty orders list returns empty result."""
        result = optimize_load(sample_truck, [])
        assert result.selected_indices == []
        assert result.total_payout_cents == 0
        assert result.total_weight_lbs == 0
        assert result.total_volume_cuft == 0
    
    def test_single_order(self, sample_truck):
        """Single order that fits is selected."""
        order = Order(
            id="ord-001",
            payout_cents=250000,
            weight_lbs=18000,
            volume_cuft=1200,
            origin="Los Angeles, CA",
            destination="Dallas, TX",
            pickup_date=date(2025, 12, 5),
            delivery_date=date(2025, 12, 9),
            is_hazmat=False
        )
        result = optimize_load(sample_truck, [order])
        assert result.selected_indices == [0]
        assert result.total_payout_cents == 250000
        assert result.total_weight_lbs == 18000
        assert result.total_volume_cuft == 1200
    
    def test_two_compatible_orders(self, sample_truck, compatible_orders):
        """Two compatible orders that fit together are both selected."""
        result = optimize_load(sample_truck, compatible_orders)
        assert set(result.selected_indices) == {0, 1}
        assert result.total_payout_cents == 430000
        assert result.total_weight_lbs == 30000
        assert result.total_volume_cuft == 2100
    
    def test_hazmat_isolation(self, sample_truck, compatible_orders, hazmat_order):
        """Hazmat order is not combined with non-hazmat orders."""
        orders = compatible_orders + [hazmat_order]
        result = optimize_load(sample_truck, orders)
        
        # Should select either both non-hazmat orders (430000)
        # or just the hazmat order (320000)
        # Since 430000 > 320000, should select non-hazmat orders
        selected_ids = set(result.selected_indices)
        
        # Either all hazmat or all non-hazmat
        hazmat_indices = {i for i, o in enumerate(orders) if o.is_hazmat}
        non_hazmat_indices = {i for i, o in enumerate(orders) if not o.is_hazmat}
        
        assert selected_ids.issubset(hazmat_indices) or selected_ids.issubset(non_hazmat_indices)
    
    def test_weight_constraint(self, sample_truck):
        """Orders exceeding weight limit are not combined."""
        orders = [
            Order(
                id="ord-1",
                payout_cents=200000,
                weight_lbs=25000,
                volume_cuft=500,
                origin="Los Angeles, CA",
                destination="Dallas, TX",
                pickup_date=date(2025, 12, 5),
                delivery_date=date(2025, 12, 9),
                is_hazmat=False
            ),
            Order(
                id="ord-2",
                payout_cents=200000,
                weight_lbs=25000,
                volume_cuft=500,
                origin="Los Angeles, CA",
                destination="Dallas, TX",
                pickup_date=date(2025, 12, 5),
                delivery_date=date(2025, 12, 9),
                is_hazmat=False
            )
        ]
        result = optimize_load(sample_truck, orders)
        # Combined weight would be 50000 > 44000, so only one can be selected
        assert len(result.selected_indices) == 1
        assert result.total_weight_lbs <= 44000
    
    def test_volume_constraint(self, sample_truck):
        """Orders exceeding volume limit are not combined."""
        orders = [
            Order(
                id="ord-1",
                payout_cents=200000,
                weight_lbs=5000,
                volume_cuft=2000,
                origin="Los Angeles, CA",
                destination="Dallas, TX",
                pickup_date=date(2025, 12, 5),
                delivery_date=date(2025, 12, 9),
                is_hazmat=False
            ),
            Order(
                id="ord-2",
                payout_cents=200000,
                weight_lbs=5000,
                volume_cuft=2000,
                origin="Los Angeles, CA",
                destination="Dallas, TX",
                pickup_date=date(2025, 12, 5),
                delivery_date=date(2025, 12, 9),
                is_hazmat=False
            )
        ]
        result = optimize_load(sample_truck, orders)
        # Combined volume would be 4000 > 3000, so only one can be selected
        assert len(result.selected_indices) == 1
        assert result.total_volume_cuft <= 3000
    
    def test_maximize_revenue(self, sample_truck):
        """Algorithm selects orders that maximize revenue."""
        orders = [
            Order(
                id="ord-1",
                payout_cents=100000,  # Lower payout
                weight_lbs=30000,
                volume_cuft=2000,
                origin="Los Angeles, CA",
                destination="Dallas, TX",
                pickup_date=date(2025, 12, 5),
                delivery_date=date(2025, 12, 9),
                is_hazmat=False
            ),
            Order(
                id="ord-2",
                payout_cents=150000,  # Higher payout
                weight_lbs=20000,
                volume_cuft=1500,
                origin="Los Angeles, CA",
                destination="Dallas, TX",
                pickup_date=date(2025, 12, 5),
                delivery_date=date(2025, 12, 9),
                is_hazmat=False
            ),
            Order(
                id="ord-3",
                payout_cents=120000,  # Medium payout, fits with ord-2
                weight_lbs=15000,
                volume_cuft=1000,
                origin="Los Angeles, CA",
                destination="Dallas, TX",
                pickup_date=date(2025, 12, 5),
                delivery_date=date(2025, 12, 9),
                is_hazmat=False
            )
        ]
        result = optimize_load(sample_truck, orders)
        # ord-2 + ord-3 = 270000 (fits: 35000 lbs, 2500 cuft)
        # ord-1 alone = 100000
        # Should select ord-2 + ord-3
        assert result.total_payout_cents == 270000
        assert set(result.selected_indices) == {1, 2}


class TestPerformance:
    """Performance tests for large order counts."""
    
    def test_performance_20_orders(self, sample_truck):
        """Should complete optimization for 20 orders in under 2 seconds."""
        import time
        
        orders = [
            Order(
                id=f"ord-{i:03d}",
                payout_cents=100000 + i * 1000,
                weight_lbs=2000 + i * 100,
                volume_cuft=100 + i * 10,
                origin="Los Angeles, CA",
                destination="Dallas, TX",
                pickup_date=date(2025, 12, 5),
                delivery_date=date(2025, 12, 9),
                is_hazmat=False
            )
            for i in range(20)
        ]
        
        start = time.time()
        result = optimize_load(sample_truck, orders)
        elapsed = time.time() - start
        
        assert elapsed < 2.0, f"Optimization took {elapsed:.2f}s, expected < 2s"
        assert result.total_weight_lbs <= sample_truck.max_weight_lbs
        assert result.total_volume_cuft <= sample_truck.max_volume_cuft


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
