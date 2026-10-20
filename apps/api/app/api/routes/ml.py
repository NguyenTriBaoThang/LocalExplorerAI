from fastapi import APIRouter, HTTPException, Depends, Query, Response

from app.core.config import settings
from app.schemas.ml import FloodRiskRequest, RankExperiencesRequest
from app.services.flood_model_service import FloodModelUnavailable, flood_model_service
from app.services.ml_ranker_service import MLRankerUnavailable, ranker_service
from app.services.open_meteo_service import OpenMeteoUnavailable, current_conditions
from app.api.guards import public


router = APIRouter(prefix="/api/ml", tags=["local ML models"])


@router.get("/status", dependencies=[Depends(public('local model inference; nothing is persisted'))])
def model_status():
    return {
        "experience_ranker": ranker_service.status(),
        "flood_risk_model": flood_model_service.status(),
    }


@router.get("/location-context", dependencies=[Depends(public('live weather and air-quality data for a map coordinate; nothing is persisted'))])
def location_context(
    response: Response,
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
):
    """Return live weather/AQI at a selected map point and an honest flood-data status."""
    try:
        conditions = current_conditions(latitude, longitude)
    except OpenMeteoUnavailable as error:
        raise HTTPException(status_code=502, detail={
            "code": "LOCATION_CONTEXT_UNAVAILABLE",
            "message": "Live weather or air-quality data is temporarily unavailable for this point.",
        }) from error

    response.headers["Cache-Control"] = f"public, max-age={max(60, min(900, settings.open_meteo_cache_ttl_seconds))}"
    flood_status = flood_model_service.status()
    return {
        "coordinates": {"latitude": latitude, "longitude": longitude},
        "conditions": conditions,
        "flood": {
            "status": "not_assessed",
            "probability": None,
            "risk_state": "unknown",
            "prediction_available": False,
            "model_deployment_allowed": bool(flood_status.get("deployment_allowed")),
            "model_version": flood_status.get("model_version"),
            "message_vi": "Chưa thể dự đoán ngập tại điểm này: cần dữ liệu mưa, địa hình, thoát nước và quan trắc đã xác minh theo đoạn đường. Mưa không tự chứng minh có ngập.",
            "message_en": "Flood risk is not assessed here: verified segment-level rainfall, terrain, drainage, and observation inputs are required. Rain alone does not establish flooding.",
        },
    }


@router.post("/rank-experiences", dependencies=[Depends(public('local model inference; nothing is persisted'))])
def rank_experiences(payload: RankExperiencesRequest):
    query = payload.query.model_dump()
    candidates = [candidate.model_dump() for candidate in payload.candidates]
    try:
        ranked, filtered_ids, status = ranker_service.rank(query, candidates)
    except MLRankerUnavailable as error:
        raise HTTPException(status_code=503, detail={"code": "RANKER_NOT_READY", "message": str(error)}) from error
    return {
        "model_version": status.get("model_version"),
        "model_family": status.get("model_family"),
        "ranking_source": status.get("ranking_source"),
        "dataset_status": status.get("dataset_status"),
        "score_type": "relative_ranking_score_not_probability",
        "warning": status.get("warning"),
        "experimental_warning": status.get("warning") if status.get("ranking_source") in {"rule_baseline", "bootstrap_ml_model"} else None,
        "ranked_candidates": ranked,
        "filtered_out_candidate_ids": filtered_ids,
    }


@router.post("/flood-risk", dependencies=[Depends(public('local model inference; nothing is persisted'))])
def predict_flood_risk(payload: FloodRiskRequest):
    samples = [sample.model_dump(mode="json", exclude_none=True) for sample in payload.samples]
    try:
        predictions, status = flood_model_service.predict(samples)
    except FloodModelUnavailable as error:
        raise HTTPException(status_code=503, detail={"code": "FLOOD_MODEL_NOT_READY", "message": str(error)}) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail={"code": "INVALID_FLOOD_SAMPLE", "message": str(error)}) from error
    return {
        "model_version": status.get("model_version"),
        "predictions": predictions,
        "safety_note": "Predictions are not verified flood/road-closure reports. Preserve hard blocks; unknown is not no-flood.",
    }
