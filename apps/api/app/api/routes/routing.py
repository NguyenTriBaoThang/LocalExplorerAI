from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.adapters.routing.provider import RoutingConfigurationError, RoutingProviderError
from app.schemas.geocoding import GeocodeResponse
from app.api.dependencies import get_db
from app.core.config import settings
from app.services.integration_config import IntegrationSecretConfigurationError, resolve_integration_value
from app.services.routing_service import make_geocoding_provider
from app.api.guards import public

router = APIRouter(prefix="/api", tags=["routing and geocoding"])


@router.get("/routing/capabilities", dependencies=[Depends(public('routing provider capabilities'))])
def routing_capabilities(db: Session = Depends(get_db)):
    try:
        routing_provider = (resolve_integration_value(db, "routing", "provider") or "goong").strip().lower()
        geocoding_provider = (resolve_integration_value(db, "routing", "geocoding_provider") or "goong").strip().lower()
        goong_api_key = resolve_integration_value(db, "routing", "goong_api_key")
    except IntegrationSecretConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail={"code": "ROUTING_CONFIGURATION_UNAVAILABLE", "message": "Routing integration settings are unavailable."},
        ) from error
    modes = {
        "mock": ["walking", "bicycling", "driving", "motorcycle", "car", "transit"],
        "goong": ["motorcycle", "walking", "car"],
    }.get(routing_provider, [])
    mock_allowed = not settings.real_data_only
    return {
        "provider": routing_provider,
        "configured": (routing_provider == "mock" and mock_allowed) or (routing_provider == "goong" and bool(goong_api_key)),
        "supported_modes": modes,
        "eta_is_realtime": False,
        "geocoding_provider": geocoding_provider,
        "geocoding_configured": geocoding_provider == "goong" and bool(goong_api_key),
        "mock_allowed": mock_allowed,
        "data_mode": "real" if settings.real_data_only else "mixed",
    }


@router.get("/geocoding/forward", response_model=GeocodeResponse, dependencies=[Depends(public('address lookup; relies on rate limiting'))])
def forward_geocode(address: str = Query(min_length=3, max_length=300), db: Session = Depends(get_db)):
    try:
        result = make_geocoding_provider(db).forward(address)
    except RoutingConfigurationError as error:
        raise HTTPException(status_code=503, detail={"code": "GEOCODING_NOT_CONFIGURED", "message": str(error)}) from error
    except RoutingProviderError as error:
        raise HTTPException(status_code=502, detail={"code": "GEOCODING_PROVIDER_ERROR", "message": str(error)}) from error

    now = datetime.now(timezone.utc)
    resolved_at = result.resolved_at
    if resolved_at.tzinfo is None:
        resolved_at = resolved_at.replace(tzinfo=timezone.utc)
    return {
        "query": address,
        "provider": result.provider,
        "source_uri": result.source_uri,
        "resolved_at": resolved_at,
        "valid_until": result.valid_until,
        "age_seconds": max(0, int((now - resolved_at).total_seconds())),
        "results": [candidate.__dict__ for candidate in result.results],
    }
