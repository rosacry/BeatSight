"""Tests for verifier dashboard API routes."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.map_edit import VerificationDecision


class TestVerifierProposalsAuth:
    """Tests for proposal listing endpoint auth."""
    
    def test_list_proposals_no_token_fails(self):
        """Unauthenticated requests without token should fail."""
        client = TestClient(app)
        # Without any Authorization header, should get 401 or 403
        response = client.get("/api/verifier/proposals")
        assert response.status_code in [401, 403]  # Depends on auth middleware
    
    def test_get_proposal_requires_auth(self):
        """Single proposal endpoint requires auth."""
        client = TestClient(app)
        fake_id = uuid.uuid4()
        response = client.get(f"/api/verifier/proposals/{fake_id}")
        assert response.status_code in [401, 403]


class TestVerifierDecisionsAuth:
    """Tests for decision creation endpoint auth."""
    
    def test_create_decision_requires_auth(self):
        """Unauthenticated requests should fail."""
        client = TestClient(app)
        fake_id = uuid.uuid4()
        response = client.post(
            f"/api/verifier/proposals/{fake_id}/decision",
            json={"decision": "approve"},
        )
        assert response.status_code in [401, 403]
    
    def test_decision_enum_validation(self):
        """Invalid decision value should fail validation."""
        client = TestClient(app)
        fake_id = uuid.uuid4()
        response = client.post(
            f"/api/verifier/proposals/{fake_id}/decision",
            json={"decision": "invalid_decision"},
        )
        # Should be 401/403 (auth) or 422 (validation) depending on check order
        assert response.status_code in [401, 403, 422]


class TestVerifierStatsAuth:
    """Tests for verifier statistics endpoint auth."""
    
    def test_get_stats_requires_auth(self):
        """Unauthenticated requests should fail."""
        client = TestClient(app)
        response = client.get("/api/verifier/stats")
        assert response.status_code in [401, 403]


class TestVerifierMyDecisionsAuth:
    """Tests for user's own decision history auth."""
    
    def test_my_decisions_requires_auth(self):
        """Unauthenticated requests should fail."""
        client = TestClient(app)
        response = client.get("/api/verifier/my-decisions")
        assert response.status_code in [401, 403]


class TestVerifierSchemas:
    """Tests for verifier schema validation."""
    
    def test_decision_create_valid_approve(self):
        """Valid approve decision should serialize."""
        from app.api.routes.verifier import DecisionCreate
        
        data = DecisionCreate(decision=VerificationDecision.APPROVE)
        assert data.decision == VerificationDecision.APPROVE
        assert data.notes is None
    
    def test_decision_create_valid_reject(self):
        """Valid reject decision should serialize."""
        from app.api.routes.verifier import DecisionCreate
        
        data = DecisionCreate(decision=VerificationDecision.REJECT, notes="Needs improvement")
        assert data.decision == VerificationDecision.REJECT
        assert data.notes == "Needs improvement"
    
    def test_decision_create_valid_needs_changes(self):
        """Valid needs_changes decision should serialize."""
        from app.api.routes.verifier import DecisionCreate
        
        data = DecisionCreate(decision=VerificationDecision.NEEDS_CHANGES, notes="Please fix timing")
        assert data.decision == VerificationDecision.NEEDS_CHANGES
        assert data.notes == "Please fix timing"
    
    def test_decision_notes_max_length(self):
        """Notes should respect max length."""
        from app.api.routes.verifier import DecisionCreate
        from pydantic import ValidationError
        
        # Should succeed with 512 chars
        data = DecisionCreate(decision=VerificationDecision.REJECT, notes="x" * 512)
        assert len(data.notes) == 512
        
        # Should fail with 513 chars
        with pytest.raises(ValidationError):
            DecisionCreate(decision=VerificationDecision.REJECT, notes="x" * 513)


class TestVerifierListResponse:
    """Tests for proposal list response schema."""
    
    def test_proposal_list_response_schema(self):
        """Proposal list response has correct structure."""
        from app.api.routes.verifier import ProposalListResponse
        
        response = ProposalListResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
            has_next=False,
        )
        
        assert response.items == []
        assert response.total == 0
        assert response.page == 1
        assert response.has_next is False


class TestVerifierStatsResponse:
    """Tests for verifier stats response schema."""
    
    def test_stats_response_schema(self):
        """Stats response has correct structure."""
        from app.api.routes.verifier import VerifierStatsResponse
        
        response = VerifierStatsResponse(
            pending_count=5,
            approved_today=3,
            rejected_today=1,
            total_reviewed_by_user=10,
            avg_review_time_hours=2.5,
        )
        
        assert response.pending_count == 5
        assert response.approved_today == 3
        assert response.rejected_today == 1
        assert response.total_reviewed_by_user == 10
        assert response.avg_review_time_hours == 2.5
    
    def test_stats_response_optional_fields(self):
        """Stats response optional fields work."""
        from app.api.routes.verifier import VerifierStatsResponse
        
        response = VerifierStatsResponse(
            pending_count=0,
            approved_today=0,
            rejected_today=0,
            total_reviewed_by_user=0,
        )
        
        assert response.avg_review_time_hours is None


class TestRouteRegistration:
    """Tests that verifier routes are properly registered."""
    
    def test_verifier_routes_exist(self):
        """Verify all expected routes are registered."""
        from app.main import app
        
        route_paths = [r.path for r in app.routes]
        
        assert "/api/verifier/proposals" in route_paths
        assert "/api/verifier/proposals/{proposal_id}" in route_paths
        assert "/api/verifier/proposals/{proposal_id}/decision" in route_paths
        assert "/api/verifier/stats" in route_paths
        assert "/api/verifier/my-decisions" in route_paths
