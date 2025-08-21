# 멀티에이전트 텍스트-SQL 시스템 설정
import os
from typing import Optional, Literal
from pydantic import BaseModel

class APIConfig(BaseModel):
    # API 설정
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    model_provider: Literal["openai", "anthropic"] = "openai"
    model_name: str = "gpt-4o"  # 또는 "claude-3-5-sonnet-20241022"
    temperature: float = 0.1
    max_tokens: int = 4000

class DatabaseConfig(BaseModel):
    # 데이터베이스 설정
    schema_path: str = "private/schema_ontology.json"
    env_path: str = "private/.env"
    
class SystemConfig(BaseModel):
    # 시스템 설정
    api: APIConfig = APIConfig()
    database: DatabaseConfig = DatabaseConfig()
    debug: bool = False
    
def load_config() -> SystemConfig:
    # 환경 변수에서 설정 로드
    config = SystemConfig()
    
    # private/.env 파일에서 로드 시도
    env_file = config.database.env_path
    if os.path.exists(env_file):
        from dotenv import load_dotenv
        load_dotenv(env_file)
    
    # API 키 로드
    config.api.openai_api_key = os.getenv("OPENAI_API_KEY")
    config.api.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    
    # 모델 제공자와 이름 설정
    config.api.model_provider = os.getenv("MODEL_PROVIDER", "openai")
    if config.api.model_provider == "openai":
        config.api.model_name = os.getenv("MODEL_NAME", "gpt-4o")
    else:
        config.api.model_name = os.getenv("MODEL_NAME", "claude-3-5-sonnet-20241022")
    
    # 기타 설정
    config.api.temperature = float(os.getenv("TEMPERATURE", "0.1"))
    config.api.max_tokens = int(os.getenv("MAX_TOKENS", "4000"))
    config.debug = os.getenv("DEBUG", "false").lower() == "true"
    
    return config

# 전역 설정 인스턴스
config = load_config()