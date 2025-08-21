# 품질 검증 에이전트 - SQL 쿼리 검증 및 수정
import re
import json
from typing import List, Tuple
from models import AgentState, AgentType, ProcessingStep, ValidationResult
from .base_agent import BaseAgent

class QualityValidatorAgent(BaseAgent):
    # SQL 품질 검증 및 오류 수정 담당 에이전트
    
    def __init__(self):
        super().__init__(AgentType.QUALITY_VALIDATOR)
    
    def get_system_prompt(self) -> str:
        return """
당신은 MySQL SQL 품질 검증 및 오류 수정 전문가입니다.

**주요 역할:**
1. MySQL 구문 검증 및 오류 탐지
2. 논리적 오류 및 성능 이슈 식별
3. 실행 가능한 완전한 쿼리로 수정
4. 최종 품질 보증 및 승인

**검증 항목:**
1. **구문 검증**
   - MySQL 키워드 및 함수 정확성
   - 괄호, 따옴표, 세미콜론 매칭
   - 테이블명, 컬럼명 존재 여부
   - JOIN 구문 정확성

2. **논리적 검증**
   - 외래키 관계 정확성
   - WHERE 조건 적절성
   - GROUP BY, HAVING 절 일관성
   - ORDER BY 절 유효성

3. **성능 검증**
   - 인덱스 활용 가능성
   - 불필요한 조인 제거
   - 서브쿼리 최적화 여부
   - LIMIT 절 활용

4. **사용자 경험**
   - 한국어 별칭 적절성
   - 결과 컬럼 명확성
   - NULL 값 처리
   - 날짜/시간 포맷

**수정 원칙:**
- 원본 의도 최대한 보존
- 최소한의 수정으로 오류 해결
- MySQL 5.7+ 호환성 보장
- 성능 저하 없는 수정

**출력 형식:**
```json
{
    "is_valid": true/false,
    "syntax_errors": ["구문 오류 목록"],
    "logic_warnings": ["논리적 경고 목록"], 
    "suggestions": ["개선 제안사항"],
    "final_sql": "최종 수정된 SQL 쿼리 (오류가 없다면 원본과 동일)"
}
```

**최종 승인 기준:**
1. MySQL에서 실행 가능한 완전한 쿼리
2. 사용자 질의 의도에 부합하는 결과
3. 적절한 성능 특성
4. 사용자 친화적 결과 구조
"""

    def _basic_syntax_check(self, sql: str) -> List[str]:
        # 기본 구문 검증
        errors = []
        
        # 기본 SQL 구조 확인
        sql_upper = sql.upper()
        if not any(keyword in sql_upper for keyword in ['SELECT', 'INSERT', 'UPDATE', 'DELETE']):
            errors.append("SQL 키워드(SELECT, INSERT, UPDATE, DELETE)가 없습니다.")
        
        # 균형 있는 괄호 확인
        if sql.count('(') != sql.count(')'):
            errors.append("괄호가 균형을 이루지 않습니다.")
        
        # 기본 따옴표 매칭 확인(단순화됨)
        single_quotes = sql.count("'")
        if single_quotes % 2 != 0:
            errors.append("작은따옴표가 짝을 이루지 않습니다.")
        
        # 끝에 세미콜론 확인
        if not sql.strip().endswith(';'):
            errors.append("SQL 쿼리는 세미콜론(;)으로 끝나야 합니다.")
        
        return errors
    
    def _check_table_column_references(self, sql: str, schema_data: dict) -> List[str]:
        # 참조된 테이블과 컴럼이 스키마에 존재하는지 확인
        warnings = []
        
        # 스키마에서 모든 데이터베이스 객체 추출
        valid_tables = set()
        valid_columns = {}
        
        for table_name, table_info in schema_data.get("database_schema", {}).items():
            table_db_name = table_info.get("table", "")
            valid_tables.add(table_db_name)
            valid_columns[table_db_name] = set()
            
            for attr_name, attr_info in table_info.get("attributes", {}).items():
                column_name = attr_info.get("column", attr_name)
                valid_columns[table_db_name].add(column_name)
        
        # 테이블 참조를 찾는 간단한 정규식 (이것은 기본적 - 전체 파서가 더 좋음)
        table_pattern = r'\b(tb_\w+)\b'
        referenced_tables = re.findall(table_pattern, sql.lower())
        
        for table in referenced_tables:
            if table not in valid_tables:
                warnings.append(f"테이블 '{table}'이 스키마에 존재하지 않습니다.")
        
        return warnings
    
    async def process(self, state: AgentState) -> AgentState:
        # SQL 쿼리 검증 및 수정
        try:
            if not state.sql_result or not state.sql_result.sql_query:
                state.current_step = ProcessingStep.ERROR
                state.error_message = "검증할 SQL 쿼리가 없습니다."
                return state
            
            original_sql = state.sql_result.sql_query
            
            # 기본 검증 수행
            syntax_errors = self._basic_syntax_check(original_sql)
            logic_warnings = self._check_table_column_references(original_sql, self.schema_data)
            
            # 중요한 오류가 있으면 수정 시도
            if syntax_errors:
                # 수정 프롬프트 생성
                prompt_template = self._create_prompt_template(self.get_system_prompt())
                
                input_data = {
                    "input": f"""
**원본 SQL 쿼리:**
```sql
{original_sql}
```

**발견된 구문 오류:**
{syntax_errors}

**논리적 경고:**
{logic_warnings}

**사용자 원본 질의:** {state.user_query}

**사용 가능한 스키마 테이블:**
{list(self.schema_data.get("database_schema", {}).keys())[:10]}

위 오류들을 수정하여 실행 가능한 MySQL 쿼리로 만들어주세요.
사용자의 원본 의도를 최대한 보존하면서 오류만 수정해주세요.
"""
                }
                
                # 수정된 SQL 받기
                response = await self._invoke_llm(prompt_template, input_data)
                
                # 상호작용 로그 기록
                self._log_interaction(state, f"Errors: {len(syntax_errors)}, Warnings: {len(logic_warnings)}", response)
                
                # 응답 파싱
                try:
                    json_start = response.find('{')
                    json_end = response.rfind('}') + 1
                    if json_start != -1 and json_end != -1:
                        json_str = response[json_start:json_end]
                        validation_data = json.loads(json_str)
                    else:
                        # 대체: 응답에서 SQL 추출
                        sql_match = re.search(r'```sql\s*(.*?)\s*```', response, re.DOTALL | re.IGNORECASE)
                        if sql_match:
                            corrected_sql = sql_match.group(1).strip()
                        else:
                            corrected_sql = original_sql
                        
                        validation_data = {
                            "is_valid": len(syntax_errors) == 0,
                            "syntax_errors": syntax_errors,
                            "logic_warnings": logic_warnings,
                            "suggestions": ["자동 수정 시도됨"],
                            "final_sql": corrected_sql
                        }
                    
                    # 수정된 SQL 재확인
                    corrected_sql = validation_data.get("final_sql", original_sql)
                    if corrected_sql != original_sql:
                        corrected_errors = self._basic_syntax_check(corrected_sql)
                        if len(corrected_errors) < len(syntax_errors):
                            validation_data["syntax_errors"] = corrected_errors
                            validation_data["is_valid"] = len(corrected_errors) == 0
                    
                except (json.JSONDecodeError, ValueError):
                    # 대체 검증 결과
                    validation_data = {
                        "is_valid": False,
                        "syntax_errors": syntax_errors,
                        "logic_warnings": logic_warnings,
                        "suggestions": ["수정 응답 파싱 실패"],
                        "final_sql": original_sql
                    }
            else:
                # 중요한 오류 없음, SQL이 수용 가능
                validation_data = {
                    "is_valid": True,
                    "syntax_errors": [],
                    "logic_warnings": logic_warnings,
                    "suggestions": ["쿼리가 유효합니다."] if not logic_warnings else ["경고사항을 확인해주세요."],
                    "final_sql": original_sql
                }
            
            # 검증 결과 생성
            validation_result = ValidationResult(
                is_valid=validation_data.get("is_valid", False),
                syntax_errors=validation_data.get("syntax_errors", []),
                logic_warnings=validation_data.get("logic_warnings", []),
                suggestions=validation_data.get("suggestions", []),
                final_sql=validation_data.get("final_sql", original_sql)
            )
            
            # 상태 업데이트
            state.validation_result = validation_result
            
            if validation_result.is_valid:
                state.final_sql = validation_result.final_sql
                state.explanation = state.sql_result.explanation
                state.current_step = ProcessingStep.COMPLETED
                state.processing_history.append("품질 검증 완료: SQL이 유효합니다.")
            else:
                state.current_step = ProcessingStep.ERROR
                state.error_message = f"SQL 검증 실패: {', '.join(validation_result.syntax_errors)}"
                state.processing_history.append(f"품질 검증 실패: {len(validation_result.syntax_errors)}개 오류")
            
            return state
            
        except Exception as e:
            state.current_step = ProcessingStep.ERROR
            state.error_message = f"품질 검증 중 오류 발생: {str(e)}"
            state.processing_history.append(f"품질 검증 실패: {str(e)}")
            return state