from app.core.config import settings
from sqlalchemy import create_engine

engine = create_engine(settings.DATABASE_URL)
