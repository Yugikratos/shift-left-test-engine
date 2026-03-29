"""API endpoint tests using FastAPI TestClient."""

from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_health_check():
    """Health endpoint returns 200 with expected fields."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "llm_mode" in data
    assert "database_ready" in data


def test_list_tables():
    """Tables endpoint returns list of source tables."""
    response = client.get("/api/v1/tables")
    assert response.status_code == 200
    data = response.json()
    assert "tables" in data
    assert data["count"] > 0


def test_provision_endpoint():
    """Provision endpoint runs pipeline and returns success."""
    response = client.post("/api/v1/provision", json={
        "scenario": "test",
        "tables": ["stg_business_entity", "business_credit_score", "business_address_match"],
        "record_count": 5,
        "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"


def test_status_unknown_request():
    """Status endpoint returns 404 for unknown request ID."""
    response = client.get("/api/v1/status/nonexistent")
    assert response.status_code == 404


def test_results_unknown_request():
    """Results endpoint returns 404 for unknown request ID."""
    response = client.get("/api/v1/results/nonexistent")
    assert response.status_code == 404
