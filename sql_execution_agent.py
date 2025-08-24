# SQL 실행 및 검증 에이전트
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from models import AgentState, AgentType, ProcessingStep, SQLExecutionResult
from agents.base_agent import BaseAgent
from database_connector import DatabaseConnection, MockDatabaseConnection, RealDatabaseConnection, SQLValidator
from config import config

class SQLExecutionAgent(BaseAgent):
    # SQL 실행 및 결과 검증 담당 에이전트
    
    def __init__(self, db_connection: Optional[DatabaseConnection] = None, use_real_db: bool = False):
        super().__init__(AgentType.SQL_EXECUTOR)
        
        # DB 연결 설정
        if db_connection:
            self.db_connection = db_connection
        elif use_real_db:
            self.db_connection = RealDatabaseConnection(environment=config.database.environment)
        else:
            self.db_connection = MockDatabaseConnection()
            
        self.validator = SQLValidator()
        
        # 세션별 실패 로그 관리
        self.session_failures = {}
        
    def get_system_prompt(self) -> str:
        return """
당신은 SQL 실행 결과 분석 및 검증 전문가입니다.

**주요 역할:**
1. SQL 쿼리 실행 결과 분석
2. 결과가 사용자 질의 의도와 일치하는지 검증
3. 오류 발생 시 문제점 분석 및 수정 방향 제시

**검증 기준:**
1. **결과 존재성**: 적절한 수의 결과가 반환되었는가?
2. **데이터 품질**: NULL 값이나 빈 값이 과도하게 있지 않은가?
3. **의도 일치성**: 사용자가 원하는 정보가 포함되어 있는가?
4. **논리적 정확성**: 결과가 비즈니스 로직에 맞는가?

**분석 결과 형식:**
{{
    "is_valid": true/false,
    "result_quality": "excellent/good/poor",
    "issues_found": ["문제점 목록"],
    "recommendations": ["개선 제안사항"],
    "needs_retry": true/false,
    "retry_reason": "재시도가 필요한 이유"
}}

**재시도 기준:**
- 결과가 0건인 경우 (조건 너무 제한적)
- 예상과 전혀 다른 컬럼이 반환된 경우  
- 명백한 논리적 오류가 있는 경우
- SQL 실행 오류가 발생한 경우
"""

    async def process(self, state: AgentState, session_id: Optional[str] = None) -> AgentState:
        # SQL 실행 및 결과 검증
        try:
            if not state.validation_result or not state.validation_result.final_sql:
                state.current_step = ProcessingStep.ERROR
                state.error_message = "실행할 SQL이 없습니다."
                return state
            
            sql_query = state.validation_result.final_sql
            
            # 1. SQL 안전성 검증
            is_safe, safety_errors = self.validator.validate_sql_safety(sql_query)
            if not is_safe:
                state.current_step = ProcessingStep.ERROR
                state.error_message = f"안전하지 않은 SQL: {', '.join(safety_errors)}"
                return state
            
            # 2. SQL 실행
            execution_start = time.time()
            execution_result = await self.db_connection.execute_query(sql_query)
            execution_time = time.time() - execution_start
            
            # 3. DB 연결 오류 검사 (재시도 방지)
            error_message = execution_result.get("error") or ""
            is_connection_error = any(keyword in str(error_message).lower() for keyword in [
                "db 연결 실패", "connection error", "ssh", "paramiko", "tunnel", "connection failed", 
                "연결 실패", "연결 오류", "has no attribute"
            ])
            
            if is_connection_error:
                # DB 연결 오류는 재시도하지 않고 바로 오류로 처리
                sql_exec_result = SQLExecutionResult(
                    sql_query=sql_query,
                    execution_success=False,
                    result_data=None,
                    result_columns=None,
                    row_count=0,
                    execution_time=execution_time,
                    error_message=error_message,
                    analysis={"is_valid": False, "needs_retry": False, "retry_reason": "DB 연결 오류"}
                )
                
                state.sql_execution_result = sql_exec_result
                await self._log_failure_for_retry(state.user_query, sql_query, execution_result, {
                    "is_valid": False,
                    "needs_retry": False,
                    "retry_reason": "DB 연결 오류는 재시도할 수 없습니다."
                }, session_id)
                state.current_step = ProcessingStep.ERROR
                state.error_message = f"데이터베이스 연결 실패: {error_message}"
                state.processing_history.append("DB 연결 오류로 SQL 실행 불가")
                return state
            
            # 4. 결과 분석 (연결 오류가 아닌 경우)
            analysis = await self._analyze_execution_result(
                state.user_query, 
                sql_query, 
                execution_result
            )
            
            # 5. 결과 객체 생성
            sql_exec_result = SQLExecutionResult(
                sql_query=sql_query,
                execution_success=execution_result["success"],
                result_data=execution_result.get("data"),
                result_columns=execution_result.get("columns"),
                row_count=execution_result.get("row_count", 0),
                execution_time=execution_time,
                error_message=execution_result.get("error"),
                analysis=analysis
            )
            
            # 6. 상태 업데이트
            state.sql_execution_result = sql_exec_result
            
            if execution_result["success"] and analysis.get("is_valid", False):
                # 성공적 실행 및 검증
                state.current_step = ProcessingStep.COMPLETED
                state.final_sql = sql_query
                state.execution_data = execution_result["data"]
                state.processing_history.append(
                    f"SQL 실행 성공: {execution_result['row_count']}건 조회 ({execution_time:.2f}초)"
                )
            else:
                # 실행 실패 또는 검증 실패
                if analysis.get("needs_retry", False) and state.retry_count < 20:  # 최대 20회 재시도 제한
                    # 재시도 필요 및 제한 내
                    state.retry_count += 1
                    await self._log_failure_for_retry(state.user_query, sql_query, execution_result, analysis, session_id)
                    state.current_step = ProcessingStep.SQL_DEVELOPMENT  # SQL 재생성으로 돌아감
                    state.error_message = f"SQL 재생성 필요 ({state.retry_count}/20): {analysis.get('retry_reason', '결과 검증 실패')}"
                    state.processing_history.append(f"SQL 실행 결과 불만족으로 재생성 요청 (시도 {state.retry_count})")
                else:
                    # 완전 실패 또는 재시도 횟수 초과
                    await self._log_failure_for_retry(state.user_query, sql_query, execution_result, analysis, session_id)
                    state.current_step = ProcessingStep.ERROR
                    if state.retry_count >= 20:
                        state.error_message = f"최대 재시도 횟수 초과 (20회): 더 구체적인 질의를 시도해보세요."
                    else:
                        state.error_message = execution_result.get("error") or "SQL 실행 결과가 유효하지 않습니다."
                    state.processing_history.append("SQL 실행 실패")
            
            return state
            
        except Exception as e:
            await self._log_failure_for_retry(state.user_query, "", {"error": str(e)}, {"needs_retry": False}, session_id)
            state.current_step = ProcessingStep.ERROR
            state.error_message = f"SQL 실행 중 시스템 오류: {str(e)}"
            state.processing_history.append(f"SQL 실행 에이전트 오류: {str(e)}")
            return state
    
    async def _analyze_execution_result(self, user_query: str, sql_query: str, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        # LLM을 사용한 실행 결과 분석
        try:
            # 결과 분석 프롬프트 생성
            prompt_template = self._create_prompt_template(self.get_system_prompt())
            
            # 실행 결과 요약 (데이터가 많을 경우 샘플링)
            result_summary = self._summarize_execution_result(execution_result)
            
            input_data = {
                "input": f"""
**사용자 원본 질의:** {user_query}

**실행된 SQL:**
```sql
{sql_query}
```

**실행 결과:**
- 성공 여부: {"성공" if execution_result["success"] else "실패"}
- 반환 행 수: {execution_result.get("row_count", 0)}
- 실행 시간: {execution_result.get("execution_time", 0):.3f}초
- 오류 메시지: {execution_result.get("error", "없음")}
- 컬럼: {execution_result.get("columns", [])}
- 데이터 샘플: {result_summary}

위 실행 결과를 분석하여 사용자 질의 의도와 일치하는지, 재시도가 필요한지 판단해주세요.
"""
            }
            
            # LLM 분석
            response = await self._invoke_llm(prompt_template, input_data)
            
            # JSON 파싱
            try:
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = response[json_start:json_end]
                    analysis = json.loads(json_str)
                else:
                    raise ValueError("No valid JSON found")
                
                return analysis
                
            except (json.JSONDecodeError, ValueError):
                # 파싱 실패시 기본 분석
                return self._basic_result_analysis(execution_result)
                
        except Exception as e:
            if config.debug:
                print(f"LLM 결과 분석 오류: {e}")
            return self._basic_result_analysis(execution_result)
    
    def _summarize_execution_result(self, execution_result: Dict[str, Any]) -> str:
        # 실행 결과 요약 (큰 데이터셋의 경우 샘플링)
        if not execution_result["success"]:
            return "실행 실패"
        
        data = execution_result.get("data", [])
        if not data:
            return "데이터 없음"
        
        # 처음 3개 행만 샘플링
        sample_size = min(3, len(data))
        sample_data = data[:sample_size]
        
        if len(data) > sample_size:
            return f"{json.dumps(sample_data, ensure_ascii=False, indent=2)}\n... (총 {len(data)}건 중 {sample_size}건 표시)"
        else:
            return json.dumps(sample_data, ensure_ascii=False, indent=2)
    
    def _basic_result_analysis(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        # 기본적인 결과 분석 (LLM 분석 실패시 대체)
        if not execution_result["success"]:
            return {
                "is_valid": False,
                "result_quality": "poor",
                "issues_found": [execution_result.get("error", "실행 실패")],
                "recommendations": ["SQL 구문을 확인하고 수정이 필요합니다."],
                "needs_retry": True,
                "retry_reason": "SQL 실행 오류"
            }
        
        row_count = execution_result.get("row_count", 0)
        
        if row_count == 0:
            return {
                "is_valid": False,
                "result_quality": "poor", 
                "issues_found": ["결과가 0건입니다"],
                "recommendations": ["조건을 완화하거나 데이터 존재 여부를 확인해주세요"],
                "needs_retry": True,
                "retry_reason": "결과 없음"
            }
        elif row_count > 1000:
            return {
                "is_valid": False,
                "result_quality": "poor",
                "issues_found": ["결과가 너무 많습니다"],
                "recommendations": ["LIMIT 절을 추가하거나 조건을 더 구체적으로 만들어주세요"],
                "needs_retry": True,
                "retry_reason": "결과 과다"
            }
        else:
            return {
                "is_valid": True,
                "result_quality": "good",
                "issues_found": [],
                "recommendations": [],
                "needs_retry": False,
                "retry_reason": ""
            }
    
    async def _log_failure_for_retry(self, user_query: str, sql_query: str, execution_result: Dict[str, Any], analysis: Dict[str, Any], session_id: Optional[str] = None):
        # 세션별로 실패한 SQL과 분석 결과를 통합 로그에 저장
        if not config.debug or not session_id:
            return
        
        try:
            # 실패 로그 디렉토리 생성
            failure_log_dir = Path("log") / "sql_failures" / datetime.now().strftime("%Y-%m-%d")
            failure_log_dir.mkdir(parents=True, exist_ok=True)
            
            # 세션 기반 파일명
            log_file = failure_log_dir / f"session_{session_id}_failures.json"
            
            # 현재 실패 정보
            failure_entry = {
                "timestamp": datetime.now().isoformat(),
                "attempt_number": None,  # 나중에 계산
                "generated_sql": sql_query,
                "execution_result": {
                    "success": execution_result.get("success", False),
                    "error": execution_result.get("error"),
                    "row_count": execution_result.get("row_count", 0),
                    "execution_time": execution_result.get("execution_time", 0)
                },
                "analysis": analysis,
                "retry_needed": analysis.get("needs_retry", False)
            }
            
            # 기존 로그 파일이 있으면 읽기, 없으면 새로 생성
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    session_failures = json.load(f)
            else:
                session_failures = {
                    "session_info": {
                        "session_id": session_id,
                        "user_query": user_query,
                        "start_time": datetime.now().isoformat()
                    },
                    "failures": []
                }
            
            # 시도 번호 설정
            failure_entry["attempt_number"] = len(session_failures["failures"]) + 1
            
            # 실패 항목 추가
            session_failures["failures"].append(failure_entry)
            
            # 세션별 통합 로그 파일 저장
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(session_failures, f, ensure_ascii=False, indent=2)
            
            if config.debug:
                print(f"📝 SQL 실패 로그 저장 (세션 {session_id}, 시도 {failure_entry['attempt_number']}): {log_file}")
                
        except Exception as e:
            if config.debug:
                print(f"❌ 실패 로그 저장 오류: {e}")