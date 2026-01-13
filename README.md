# SmartLoad Optimization API

A high-performance REST API for optimizing truck load combinations. Given a truck with capacity constraints and a list of available orders, the service finds the **optimal combination of orders** that maximizes carrier revenue while respecting all constraints.

## Features

- **Optimal Load Selection**: Uses bitmask dynamic programming for guaranteed optimal solutions
- **Constraint Handling**: Weight, volume, hazmat isolation, route compatibility, time windows
- **High Performance**: < 800ms for 22 orders (2²² = 4M states)
- **Stateless Design**: No database required, fully in-memory processing
- **Docker Ready**: Multi-stage build for production deployment

## How to Run

### Using Docker Compose (Recommended)

```bash
git clone <your-repo>
cd smartload-optimizer
docker compose up --build
# → Service will be available at http://localhost:8080
```

### Using Docker Directly

```bash
docker build -t smartload-optimizer .
docker run -p 8080:8080 smartload-optimizer
```

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# Run tests
pip install pytest
pytest test_optimizer.py -v
```

## API Endpoints

### Health Check

```bash
curl http://localhost:8080/healthz
# or
curl http://localhost:8080/actuator/health
```

Response:
```json
{"status": "UP", "service": "smartload-optimizer"}
```

### Optimize Load

```bash
curl -X POST http://localhost:8080/api/v1/load-optimizer/optimize \
  -H "Content-Type: application/json" \
  -d @sample-request.json
```

### API Info

```bash
curl http://localhost:8080/api/v1/load-optimizer/info
```

## Request/Response Format

### Request

```json
{
  "truck": {
    "id": "truck-123",
    "max_weight_lbs": 44000,
    "max_volume_cuft": 3000
  },
  "orders": [
    {
      "id": "ord-001",
      "payout_cents": 250000,
      "weight_lbs": 18000,
      "volume_cuft": 1200,
      "origin": "Los Angeles, CA",
      "destination": "Dallas, TX",
      "pickup_date": "2025-12-05",
      "delivery_date": "2025-12-09",
      "is_hazmat": false
    }
  ]
}
```

### Response

```json
{
  "truck_id": "truck-123",
  "selected_order_ids": ["ord-001", "ord-002"],
  "total_payout_cents": 430000,
  "total_weight_lbs": 30000,
  "total_volume_cuft": 2100,
  "utilization_weight_percent": 68.18,
  "utilization_volume_percent": 70.0
}
```
<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/8df99f18-e3a4-47c0-a3da-f74b61bf92ab" />


## Algorithm

The service uses a **hybrid optimization approach**:

1. **For n ≤ 15 orders**: Recursive backtracking with aggressive pruning
2. **For n > 15 orders**: Bitmask dynamic programming

### Constraints Handled

| Constraint | Description |
|------------|-------------|
| Weight | Total weight ≤ truck max_weight_lbs |
| Volume | Total volume ≤ truck max_volume_cuft |
| Route | All orders must share same origin AND destination |
| Time Windows | Pickup/delivery windows must overlap |
| Hazmat | Hazmat orders cannot mix with non-hazmat |

### Complexity

- **Time**: O(2^n) worst case, heavily pruned in practice
- **Space**: O(2^n) for memoization
- **Performance**: < 800ms for n=22 on typical hardware

## Error Handling

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Invalid request (validation error) |
| 413 | Payload too large (> 1MB) |
| 500 | Internal server error |

## Project Structure

```
smartload-optimizer/
├── main.py              # FastAPI application & endpoints
├── models.py            # Pydantic request/response models
├── optimizer.py         # Core optimization algorithm
├── test_optimizer.py    # Unit tests
├── requirements.txt     # Python dependencies
├── Dockerfile           # Multi-stage Docker build
├── docker-compose.yml   # Docker Compose configuration
├── sample-request.json  # Example API request
└── README.md            # This file
```

## Design Decisions

1. **Integer Cents for Money**: All monetary values use 64-bit integers (cents) to avoid floating-point precision issues.

2. **Stateless Design**: No database required; each request is processed independently.

3. **Precomputed Compatibility**: O(n²) compatibility matrix built once per request.

4. **Hybrid Algorithm**: Switches between backtracking and bitmask DP based on input size for optimal performance.

5. **Early Pruning**: Skips orders that individually exceed truck capacity before optimization.

## Future Enhancements

- [ ] Pareto-optimal solutions (max revenue vs max utilization)
- [ ] Configurable objective weights
- [ ] Multi-stop route optimization
- [ ] Response caching with TTL
- [ ] Async request processing for very large datasets

## License

MIT License
