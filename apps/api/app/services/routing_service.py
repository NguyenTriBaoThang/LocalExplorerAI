from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.adapters.routing.goong import GoongDirectionsProvider, GoongGeocodingProvider
from app.adapters.routing.provider import MockRoutingProvider, RouteEstimate, RoutingConfigurationError, RoutingProvider
from app.core.config import settings
from app.services.integration_config import IntegrationSecretConfigurationError, resolve_integration_value


def make_routing_provider(db: Session | None = None) -> RoutingProvider:
    try:
        provider_name = (resolve_integration_value(db, "routing", "provider") or "goong").strip().lower()
        if provider_name == "mock":
            return MockRoutingProvider()
        if provider_name == "goong":
            return GoongDirectionsProvider(
                resolve_integration_value(db, "routing", "goong_api_key"),
                base_url=resolve_integration_value(db, "routing", "goong_api_base_url") or settings.goong_api_base_url,
                eta_ttl_seconds=settings.goong_eta_ttl_seconds,
                timeout_seconds=settings.goong_timeout_seconds,
            )
    except IntegrationSecretConfigurationError as error:
        raise RoutingConfigurationError("Routing integration configuration is unavailable.") from error
    raise RoutingConfigurationError(f"Unsupported ROUTING_PROVIDER '{provider_name}'.")


def make_geocoding_provider(db: Session | None = None) -> GoongGeocodingProvider:
    try:
        provider_name = (resolve_integration_value(db, "routing", "geocoding_provider") or "goong").strip().lower()
        if provider_name != "goong":
            raise RoutingConfigurationError(f"Unsupported GEOCODING_PROVIDER '{provider_name}'.")
        return GoongGeocodingProvider(
            resolve_integration_value(db, "routing", "goong_api_key"),
            base_url=resolve_integration_value(db, "routing", "goong_api_base_url") or settings.goong_api_base_url,
            cache_ttl_seconds=settings.geocode_cache_ttl_seconds,
            timeout_seconds=settings.goong_timeout_seconds,
        )
    except IntegrationSecretConfigurationError as error:
        raise RoutingConfigurationError("Geocoding integration configuration is unavailable.") from error


class RoutingService:
    def __init__(self, provider: RoutingProvider | None = None, db: Session | None = None):
        self.provider = provider or make_routing_provider(db)

    def get_route(self, origin: tuple[float, float], destination: tuple[float, float], mode: str) -> RouteEstimate:
        return self.provider.get_route(origin, destination, mode)

    @staticmethod
    def eta_metadata(estimate: RouteEstimate, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        calculated_at = estimate.calculated_at or now
        if calculated_at.tzinfo is None:
            calculated_at = calculated_at.replace(tzinfo=timezone.utc)
        valid_until = estimate.valid_until
        if valid_until and valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)
        return {
            "provider": estimate.provider,
            "is_realtime": estimate.is_realtime,
            "eta_source": estimate.eta_source,
            "eta_source_uri": estimate.source_uri,
            "eta_calculated_at": calculated_at,
            "eta_age_seconds": max(0, int((now - calculated_at).total_seconds())),
            "eta_valid_until": valid_until,
            "geometry": estimate.geometry,
        }
