"""Configuration management for Ghost Data Still Exists pipeline."""

import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class PipelineConfig(BaseModel):
    """Runtime configuration for the pipeline."""
    base_dir: Path = BASE_DIR
    challenge_dir: Path = BASE_DIR / os.getenv("CHALLENGE_DIR", "challenge")
    sample_output_path: Path = BASE_DIR / os.getenv("SAMPLE_OUTPUT_PATH", "challenge/sample_output.csv")
    runs_dir: Path = BASE_DIR / os.getenv("RUNS_DIR", "runs")
    cache_db_path: Path = BASE_DIR / os.getenv("CACHE_DB_PATH", "data_cache.sqlite3")
    
    # Models & API Settings
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    anthropic_api_key: str = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    
    default_llm_model: str = Field(default_factory=lambda: os.getenv("DEFAULT_LLM_MODEL", "gemini-2.5-flash"))
    default_vlm_model: str = Field(default_factory=lambda: os.getenv("DEFAULT_VLM_MODEL", "gemini-2.5-flash"))
    
    temperature: float = 0.0
    prompt_version: str = Field(default_factory=lambda: os.getenv("PROMPT_VERSION", "v1.0"))
    max_concurrency: int = Field(default_factory=lambda: int(os.getenv("MAX_CONCURRENCY", "5")))
    request_timeout_seconds: int = Field(default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30")))

config = PipelineConfig()
