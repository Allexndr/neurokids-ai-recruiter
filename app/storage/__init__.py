from app.storage.db import Candidate, Session, Store, Vacancy, VoiceJob
from app.storage.factory import create_store

store = create_store()

__all__ = ["Candidate", "Session", "Store", "Vacancy", "VoiceJob", "store"]
