from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.schemas.dashboard import DashboardResponse, DashboardStats
from app.services import analytics_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def dashboard(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    stats = analytics_service.get_dashboard_stats(db, user_id)
    recent = analytics_service.get_recent_syncs(db, user_id)
    return DashboardResponse(stats=DashboardStats(**stats), recent=recent)
