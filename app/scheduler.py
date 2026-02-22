from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User, Word
from app.services.learning_engine import MODE_SMART_SPACED, get_next_word

user_learning_preferences: dict[int, dict[str, str | None]] = {}


class LearningScheduler:
    def __init__(self, websocket_manager) -> None:
        self.websocket_manager = websocket_manager
        self.scheduler = BackgroundScheduler()
        self.active_users: set[int] = set()

    def start(self) -> None:
        if not self.scheduler.get_job("learning_dispatch"):
            self.scheduler.add_job(self._run_dispatch_cycle, "interval", minutes=1, id="learning_dispatch", replace_existing=True)
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def update_user_preference(self, user_id: int, mode: str, selected_group: str | None) -> None:
        user_learning_preferences[user_id] = {"mode": mode, "selected_group": selected_group}

    def start_learning_for_user(self, user_id: int, mode: str, selected_group: str | None) -> None:
        self.start()
        self.update_user_preference(user_id, mode, selected_group)
        self.active_users.add(user_id)

    def stop_learning_for_user(self, user_id: int) -> None:
        self.active_users.discard(user_id)

    def _run_dispatch_cycle(self) -> None:
        with SessionLocal() as db:
            users = db.query(User).all()
            for user in users:
                if user.id not in self.active_users:
                    continue
                preference = user_learning_preferences.get(user.id, {"mode": MODE_SMART_SPACED, "selected_group": None})
                next_word = get_next_word(
                    db=db,
                    user_id=user.id,
                    mode=str(preference.get("mode", MODE_SMART_SPACED)),
                    selected_group=preference.get("selected_group"),
                )
                if not next_word:
                    continue
                seconds_left = self._seconds_until_next_cycle()
                payload = {
                    "type": "next_word",
                    "word": {
                        "id": next_word.id,
                        "word": next_word.word,
                        "meaning": next_word.meaning,
                        "group_name": next_word.group_name,
                        "strength_score": next_word.strength_score,
                    },
                    "countdown_seconds": seconds_left,
                    "sent_at": datetime.utcnow().isoformat(),
                }
                self.websocket_manager.send_to_user(user.id, payload)

    @staticmethod
    def _seconds_until_next_cycle() -> int:
        now = datetime.utcnow()
        next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        return max(1, int((next_minute - now).total_seconds()))


def get_due_word_count(db: Session, user_id: int) -> int:
    now = datetime.utcnow()
    return db.query(Word).filter(Word.user_id == user_id, (Word.next_review.is_(None)) | (Word.next_review <= now)).count()
