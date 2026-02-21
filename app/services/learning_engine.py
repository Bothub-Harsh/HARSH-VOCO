from __future__ import annotations

from datetime import datetime, timedelta
from random import choice

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ReviewLog, Word

MODE_SINGLE_GROUP = "single_group"
MODE_ALL_ROTATION = "all_rotation"
MODE_SMART_SPACED = "smart_spaced"
VALID_MODES = {MODE_SINGLE_GROUP, MODE_ALL_ROTATION, MODE_SMART_SPACED}
VALID_GROUPS = {"A", "B", "C", "D"}


def compute_next_review(strength_score: int) -> datetime:
    score = max(0, strength_score)
    minutes = min(60 * 24 * 14, 2**score)
    return datetime.utcnow() + timedelta(minutes=minutes)


def apply_review_result(db: Session, word: Word, user_id: int, was_correct: bool) -> Word:
    word.last_seen = datetime.utcnow()
    word.strength_score = max(0, word.strength_score + (1 if was_correct else -1))
    word.next_review = compute_next_review(word.strength_score)
    db.add(ReviewLog(user_id=user_id, word_id=word.id, was_correct=was_correct))
    db.commit()
    db.refresh(word)
    return word


def get_next_word(db: Session, user_id: int, mode: str, selected_group: str | None = None) -> Word | None:
    now = datetime.utcnow()
    base_query = db.query(Word).filter(Word.user_id == user_id)

    if mode == MODE_SINGLE_GROUP:
        if not selected_group or selected_group not in VALID_GROUPS:
            return None
        query = base_query.filter(Word.group_name == selected_group)
        return query.order_by(Word.strength_score.asc(), Word.last_seen.asc().nullsfirst()).first()

    if mode == MODE_ALL_ROTATION:
        group_counts = (
            base_query.with_entities(Word.group_name, func.count(Word.id).label("count"))
            .group_by(Word.group_name)
            .all()
        )
        if not group_counts:
            return None
        least_group = min(group_counts, key=lambda row: row.count).group_name
        return (
            base_query.filter(Word.group_name == least_group)
            .order_by(Word.last_seen.asc().nullsfirst(), Word.strength_score.asc())
            .first()
        )

    if mode == MODE_SMART_SPACED:
        due_word = (
            base_query.filter((Word.next_review.is_(None)) | (Word.next_review <= now))
            .order_by(Word.strength_score.asc(), Word.next_review.asc().nullsfirst())
            .first()
        )
        if due_word:
            return due_word
        fallback_words = base_query.order_by(Word.strength_score.asc(), Word.last_seen.asc().nullsfirst()).all()
        return choice(fallback_words) if fallback_words else None

    return None
