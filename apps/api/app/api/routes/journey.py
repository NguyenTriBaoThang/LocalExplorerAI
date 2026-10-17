from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.guards import public
from app.services.journey_service import landmark_context, pilot_status

router = APIRouter(prefix="/api/journey", tags=["journey"], dependencies=[Depends(public("public journey catalogue"))])


@router.get("/pilot")
def get_pilot_status(db: Session = Depends(get_db)):
    return pilot_status(db)


@router.get("/landmarks/{model_id}")
def get_landmark_context(model_id: str, demo: bool = False, db: Session = Depends(get_db)):
    return landmark_context(db, model_id, demo)
