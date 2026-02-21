from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import ReviewLog, User, Word

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    total_words = db.query(Word).filter(Word.user_id == user.id).count()
    strong_words = db.query(Word).filter(Word.user_id == user.id, Word.strength_score >= 4).count()
    weak_words = db.query(Word).filter(Word.user_id == user.id, Word.strength_score <= 1).count()

    total_reviews = db.query(ReviewLog).filter(ReviewLog.user_id == user.id).count()
    correct_reviews = db.query(ReviewLog).filter(ReviewLog.user_id == user.id, ReviewLog.was_correct.is_(True)).count()
    accuracy = round((correct_reviews / total_reviews) * 100, 2) if total_reviews else 0.0

    streak = _calculate_learning_streak(db, user.id)
    return {
        "total_words": total_words,
        "strong_words": strong_words,
        "weak_words": weak_words,
        "accuracy_percentage": accuracy,
        "learning_streak_days": streak,
    }


def _calculate_learning_streak(db: Session, user_id: int) -> int:
    days = (
        db.query(func.date(ReviewLog.reviewed_at).label("review_day"))
        .filter(ReviewLog.user_id == user_id)
        .group_by("review_day")
        .order_by("review_day desc")
        .all()
    )
    unique_days = [date.fromisoformat(row.review_day) for row in days]
    if not unique_days:
        return 0

    today = date.today()
    expected_day = today if unique_days[0] == today else today - timedelta(days=1)
    streak = 0

    for active_day in unique_days:
        if active_day == expected_day:
            streak += 1
            expected_day -= timedelta(days=1)
        elif active_day < expected_day:
            break

    return streak
