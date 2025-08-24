# 멀티에이전트 텍스트-SQL 시스템 데이터 모델
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum

class AgentType(str, Enum):
    # 사용 가능한 에이전트 타입
    SCHEMA_ANALYST = "schema_analyst"
    QUERY_PLANNER = "query_planner" 
    SQL_DEVELOPER = "sql_developer"
    QUALITY_VALIDATOR = "quality_validator"
    SQL_EXECUTOR = "sql_executor"

class ProcessingStep(str, Enum):
    # 워크플로우 처리 단계
    SCHEMA_ANALYSIS = "schema_analysis"
    QUERY_PLANNING = "query_planning"
    SQL_DEVELOPMENT = "sql_development"
    QUALITY_VALIDATION = "quality_validation"
    SQL_EXECUTION = "sql_execution"
    COMPLETED = "completed"
    ERROR = "error"

class TableInfo(BaseModel):
    # 데이터베이스 테이블 정보
    name: str
    table: str
    aliases: List[str]
    attributes: Dict[str, Dict[str, Any]]
    relationships: Optional[List[str]] = []

class SchemaAnalysisResult(BaseModel):
    # 스키마 분석 결과
    relevant_tables: List[TableInfo]
    key_relationships: List[str]
    suggested_joins: List[str]
    analysis_notes: str

class QueryPlan(BaseModel):
    # 쿼리 실행 계획
    query_steps: List[str]
    join_strategy: List[str]
    subquery_structure: Optional[List[str]] = []
    complexity_level: str
    estimated_performance: str

class SQLResult(BaseModel):
    # 생성된 SQL 결과
    sql_query: str
    explanation: str
    performance_notes: str
    expected_columns: List[str]

class ValidationResult(BaseModel):
    # 검증 결과
    is_valid: bool
    syntax_errors: List[str]
    logic_warnings: List[str]
    suggestions: List[str]
    final_sql: Optional[str] = None

class SQLExecutionResult(BaseModel):
    # SQL 실행 결과
    sql_query: str
    execution_success: bool
    result_data: Optional[List[Dict[str, Any]]] = None
    result_columns: Optional[List[str]] = None
    row_count: int = 0
    execution_time: float = 0.0
    error_message: Optional[str] = None
    analysis: Optional[Dict[str, Any]] = None

class AgentState(BaseModel):
    # 에이전트 간 전달되는 상태
    # 입력
    user_query: str
    original_language: str = "korean"
    
    # 처리 상태
    current_step: ProcessingStep = ProcessingStep.SCHEMA_ANALYSIS
    processing_history: List[str] = Field(default_factory=list)
    
    # 에이전트 결과
    schema_analysis: Optional[SchemaAnalysisResult] = None
    query_plan: Optional[QueryPlan] = None
    sql_result: Optional[SQLResult] = None
    validation_result: Optional[ValidationResult] = None
    sql_execution_result: Optional[SQLExecutionResult] = None
    
    # 최종 출력
    final_sql: Optional[str] = None
    explanation: Optional[str] = None
    execution_data: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None
    
    # 메타데이터
    processing_time: Optional[float] = None
    agent_interactions: List[Dict[str, Any]] = Field(default_factory=list)
    retry_count: int = 0  # 재시도 횟수 추적
    
    class Config:
        extra = "allow"

class TextToSQLRequest(BaseModel):
    # 텍스트-SQL 변환 요청
    query: str
    language: str = "korean"
    include_explanation: bool = True
    optimize_for_performance: bool = True

class TextToSQLResponse(BaseModel):
    # 텍스트-SQL 변환 응답
    success: bool
    sql_query: Optional[str] = None
    explanation: Optional[str] = None
    execution_data: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None
    processing_steps: List[str] = Field(default_factory=list)
    processing_time: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)