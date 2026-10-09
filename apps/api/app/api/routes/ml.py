from fastapi import APIRouter, HTTPException

from app.schemas.ml import FloodRiskRequest, RankExperiencesRequest
from app.services.flood_model_service import FloodModelUnavailable, flood_model_service
from app.services.ml_ranker_service import MLRankerUnavailable, ranker_service


router = APIRouter(prefix="/api/ml", tags=["local ML models"])


@router.get("/status")
def model_status():
    return {
        "experience_ranker": ranker_service.status(),
        "flood_risk_model": flood_model_service.status(),
    }


@router.post("/rank-experiences")
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
        "experimental_warning": status.get("warning") if status.get("ranking_source") == "rule_baseline" else None,
        "ranked_candidates": ranked,
        "filtered_out_candidate_ids": filtered_ids,
    }


@router.post("/flood-risk")
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
