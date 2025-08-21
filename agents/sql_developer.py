# SQL 개발 에이전트 - 최적화된 MySQL SQL 코드 생성
import json
from models import AgentState, AgentType, ProcessingStep, SQLResult
from .base_agent import BaseAgent

class SQLDeveloperAgent(BaseAgent):
    # 최적화된 MySQL SQL 코드 생성 담당 에이전트
    
    def __init__(self):
        super().__init__(AgentType.SQL_DEVELOPER)
    
    def get_system_prompt(self) -> str:
        return """
당신은 MySQL SQL 개발 전문가입니다.

**주요 역할:**
1. MySQL 문법을 완벽하게 준수하는 SQL 쿼리 작성
2. 성능 최적화된 쿼리 구조 구현
3. 비개발자도 이해하기 쉬운 결과 구조 설계
4. 한국어 컬럼 별칭 활용으로 가독성 향상

**MySQL 문법 준수사항:**
- 정확한 테이블명과 컬럼명 사용
- MySQL 함수 및 키워드 정확한 사용
- 적절한 데이터 타입 처리 (DATE, DATETIME, DECIMAL 등)
- 한국어 처리를 위한 UTF8 설정 고려
- LIMIT, OFFSET 올바른 사용

**성능 최적화 기법:**
- 인덱스 활용 가능한 WHERE 조건 구성
- 적절한 JOIN 타입 선택 (INNER, LEFT, RIGHT)
- 서브쿼리보다 JOIN 우선 고려
- GROUP BY, ORDER BY 최적화
- 불필요한 SELECT * 지양

**결과 구조 설계:**
- 의미있는 컬럼 별칭 (한국어) 사용
- 날짜/시간 적절한 포맷팅 (DATE_FORMAT)
- 숫자 형식 정리 (FORMAT, ROUND)
- NULL 값 처리 (COALESCE, IFNULL)

**출력 형식:**
```json
{
    "sql_query": "실행 가능한 완전한 MySQL 쿼리",
    "explanation": "쿼리 동작 방식과 각 부분의 역할 설명",
    "performance_notes": "성능 관련 주의사항 및 권장사항",
    "expected_columns": ["컬럼1", "컬럼2", "컬럼3"]
}
```

**중요 원칙:**
1. 실행 가능한 완전한 쿼리 작성 (세미콜론 포함)
2. 모든 테이블과 컬럼명 정확성 검증
3. 한국어 별칭으로 사용자 친화적 결과 제공
4. 에러 발생 가능성 최소화
5. MySQL 버전 호환성 고려
"""

    async def process(self, state: AgentState) -> AgentState:
        # 쿼리 계획 기반 최적화된 MySQL SQL 코드 생성
        try:
            if not state.query_plan or not state.schema_analysis:
                state.current_step = ProcessingStep.ERROR
                state.error_message = "쿼리 계획 또는 스키마 분석 결과가 없어 SQL을 생성할 수 없습니다."
                return state
            
            # SQL 생성 프롬프트 생성
            prompt_template = self._create_prompt_template(self.get_system_prompt())
            
            # 상세 테이블 정보 준비
            table_details = []
            for table in state.schema_analysis.relevant_tables:
                table_detail = {
                    "table_name": table.table,
                    "korean_name": table.name,
                    "aliases": table.aliases,
                    "columns": {}
                }
                
                # 한국어 별칭과 함께 컴럼 세부 정보 추가
                for col_name, col_info in table.attributes.items():
                    table_detail["columns"][col_name] = {
                        "column": col_info.get("column", col_name),
                        "type": col_info.get("type", ""),
                        "korean_aliases": col_info.get("aliases", [])
                    }
                    # enum 값이 있으면 추가
                    if "values" in col_info:
                        table_detail["columns"][col_name]["enum_values"] = col_info["values"]
                
                table_details.append(table_detail)
            
            input_data = {
                "input": f"""
**사용자 질의:** {state.user_query}

**쿼리 실행 계획:**
- 실행 단계: {state.query_plan.query_steps}
- JOIN 전략: {state.query_plan.join_strategy}
- 서브쿼리 구조: {state.query_plan.subquery_structure}
- 복잡도: {state.query_plan.complexity_level}

**관련 테이블 상세 정보:**
{json.dumps(table_details, ensure_ascii=False, indent=2)}

**테이블 관계:**
{state.schema_analysis.key_relationships}

위 정보를 바탕으로 사용자 질의를 처리하는 완전한 MySQL 쿼리를 작성해주세요.
반드시 실행 가능한 형태로, 한국어 컬럼 별칭을 포함하여 JSON 형식으로 응답해주세요.
"""
            }
            
            # LLM에서 응답 받기
            response = await self._invoke_llm(prompt_template, input_data)
            
            # 상호작용 로그 기록
            self._log_interaction(state, f"Query plan steps: {len(state.query_plan.query_steps)}", response)
            
            # 응답 파싱 및 결과 생성
            try:
                # 응답에서 JSON 추출
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = response[json_start:json_end]
                    sql_data = json.loads(json_str)
                else:
                    raise ValueError("No valid JSON found in response")
                
                # 구조화된 결과로 변환
                sql_result = SQLResult(
                    sql_query=sql_data.get("sql_query", ""),
                    explanation=sql_data.get("explanation", ""),
                    performance_notes=sql_data.get("performance_notes", ""),
                    expected_columns=sql_data.get("expected_columns", [])
                )
                
                # 비어있지 않은 SQL 쿼리인지 검증
                if not sql_result.sql_query.strip():
                    raise ValueError("Generated SQL query is empty")
                
                # 상태 업데이트
                state.sql_result = sql_result
                state.current_step = ProcessingStep.QUALITY_VALIDATION
                state.processing_history.append(
                    f"SQL 생성 완료: {len(sql_result.expected_columns)}개 컬럼 예상"
                )
                
                return state
                
            except (json.JSONDecodeError, ValueError) as e:
                # 대체: 응답 텍스트에서 SQL 추출 시도
                lines = response.split('\n')
                sql_lines = []
                in_sql = False
                
                for line in lines:
                    line = line.strip()
                    if any(keyword in line.upper() for keyword in ['SELECT', 'WITH', 'INSERT', 'UPDATE', 'DELETE']):
                        in_sql = True
                    if in_sql:
                        sql_lines.append(line)
                        if line.endswith(';'):
                            break
                
                fallback_sql = '\n'.join(sql_lines) if sql_lines else ""
                
                state.sql_result = SQLResult(
                    sql_query=fallback_sql,
                    explanation=f"SQL 파싱 오류로 인한 대체 추출: {str(e)}",
                    performance_notes="파싱 오류로 성능 분석 불가",
                    expected_columns=[]
                )
                
                if not fallback_sql:
                    state.current_step = ProcessingStep.ERROR
                    state.error_message = f"SQL 생성 파싱 실패: {str(e)}"
                    return state
                else:
                    state.current_step = ProcessingStep.QUALITY_VALIDATION
                    state.processing_history.append(f"SQL 추출 완료 (파싱 오류 복구): {str(e)}")
                
                return state
                
        except Exception as e:
            state.current_step = ProcessingStep.ERROR
            state.error_message = f"SQL 생성 중 오류 발생: {str(e)}"
            state.processing_history.append(f"SQL 생성 실패: {str(e)}")
            return state