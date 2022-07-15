import secrets
from pydantic import BaseSettings

# Security
import os
from dotenv import load_dotenv
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

class Settings(BaseSettings):
    PROJECT_NAME: str = "ChatelyWS"

    class Config:
        env_file = ".env"

settings = Settings()
