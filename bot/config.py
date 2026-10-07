

from __future__ import annotations

import os
import sys
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    

  
    Bot_Token: str = ""
    App_ID: str = ""

   
    Database_URL: str = "sqlite+aiosqlite:///./data/factcheckbot.db"


    Factchecker: str = ""
    Search: str = ""  
    HCAI: str = ""  

  
    Claim_Dectection_Threshold: float = 0.65
    Teir1_Threshold: float = 0.6
    Teir3_Limit: int = 20
    OCR_Threshold: float = 60.0
    Cache_Expiry: int = 7

  
    Log_lvl: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("Bot_Token")
    @classmethod
    def _require_discord_token(cls, v: str) -> str:
        if not v:
            raise ValueError("Bot_Token must be set")
        return v

    def secrets_safe_repr(self) -> str:
  
        return (
            "Settings("
            f"App_ID={self.App_ID!r}, "
            f"Database_URL=..., "
            f"Claim_Dectection_Threshold={self.Claim_Dectection_Threshold}, "
            f"Teir3_Limit={self.Teir3_Limit}, "
            f"Log_lvl={self.Log_lvl!r})"
        )


def load_settings() -> Settings:

    settings = Settings()
    return settings
