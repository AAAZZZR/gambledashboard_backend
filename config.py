# app/config.py
from pydantic_settings import BaseSettings  # pydantic v2
# 如果你還在 pydantic v1： from pydantic import BaseSettings

class Settings(BaseSettings):
    # The Odds API base
    ODDS_API_BASE: str = "https://api.the-odds-api.com/v4"
    # 你的 API key（必填）
    ODDS_API_KEY: str
    # 前端網域（CORS 用）
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
