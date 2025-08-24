# 쿼리 계획 에이전트 - SQL 실행 계획 및 전략 수립
import json
from models import AgentState, AgentType, ProcessingStep, QueryPlan
from .base_agent import BaseAgent

class QueryPlannerAgent(BaseAgent):
    # SQL 쿼리 계획 및 실행 전략 담당 에이전트
    
    def __init__(self):
        super().__init__(AgentType.QUERY_PLANNER)
    
    def get_system_prompt(self) -> str:
        return """
당신은 MySQL 쿼리 실행 계획 전문가입니다.

**주요 역할:**
1. 복잡한 질의를 단계별로 분해하여 실행 계획 수립
2. 최적의 JOIN 전략 결정 (INNER, LEFT, RIGHT JOIN 등)
3. 서브쿼리 구조 설계 및 성능 최적화 방안 제시
4. 인덱스 활용 및 쿼리 성능 예측

**계획 수립 원칙:**
1. **JOIN 순서 최적화**: 작은 테이블부터 JOIN하여 중간 결과 최소화
2. **인덱스 활용**: 기본키, 외래키, 인덱스 컬럼 우선 활용
3. **서브쿼리 vs JOIN**: 성능상 유리한 방식 선택
4. **필터링 조건**: WHERE 절을 최대한 앞단에 배치
5. **집계 및 정렬**: GROUP BY, ORDER BY 최적화

**입력 정보 활용:**
- 스키마 분석 결과의 relevant_tables, key_relationships 활용
- 테이블 크기와 데이터 특성 고려
- MySQL 특화 최적화 기법 적용

**출력 형식:**
```json
{{
    "query_steps": [
        "1단계: tb_user 테이블에서 활성 사용자 필터링",
        "2단계: tb_deposit과 LEFT JOIN으로 예치금 정보 결합",
        "3단계: tb_orderHistory와 INNER JOIN으로 거래 내역 결합",
        "4단계: 날짜 조건으로 필터링 및 집계"
    ],
    "join_strategy": [
        "tb_user (기준 테이블) - 사용자 수가 적어 드라이빙 테이블로 선택",
        "LEFT JOIN tb_deposit ON user.id = deposit.userId - 예치금이 없는 사용자도 포함",
        "INNER JOIN tb_orderHistory ON deposit.id = orderHistory.depositId0 - 거래가 있는 경우만"
    ],
    "subquery_structure": [
        "메인쿼리: 사용자별 거래 집계",
        "서브쿼리 없이 JOIN으로 처리 가능"
    ],
    "complexity_level": "중간",
    "estimated_performance": "인덱스 활용 시 1초 이내 예상, tb_user.id, tb_deposit.userId 인덱스 필수"
}}
```

**성능 고려사항:**
- 테이블 크기와 카디널리티 고려
- MySQL 옵티마이저 특성 반영
- EXPLAIN을 통한 실행 계획 예측
"""

    async def process(self, state: AgentState) -> AgentState:
        # 스키마 분석 기반 쿼리 실행 계획 수립
        try:
            if not state.schema_analysis:
                state.current_step = ProcessingStep.ERROR
                state.error_message = "스키마 분석 결과가 없어 쿼리 계획을 수립할 수 없습니다."
                return state
            
            # 계획 프롬프트 생성
            prompt_template = self._create_prompt_template(self.get_system_prompt())
            
            # 입력 데이터 준비
            schema_summary = {
                "relevant_tables": [
                    {
                        "name": table.name,
                        "table": table.table,
                        "aliases": table.aliases,
                        "key_attributes": list(table.attributes.keys())[:5],  # Limit for brevity
                        "relationships": table.relationships
                    }
                    for table in state.schema_analysis.relevant_tables
                ],
                "key_relationships": state.schema_analysis.key_relationships,
                "suggested_joins": state.schema_analysis.suggested_joins
            }
            
            input_data = {
                "input": f"""
**사용자 질의:** {state.user_query}

**스키마 분석 결과:**
{json.dumps(schema_summary, ensure_ascii=False, indent=2)}

**분석 노트:** {state.schema_analysis.analysis_notes}

위 정보를 바탕으로 MySQL 쿼리의 최적 실행 계획을 수립해주세요.
테이블 크기, JOIN 순서, 인덱스 활용 등을 고려하여 성능 최적화된 계획을 JSON 형식으로 제공해주세요.
"""
            }
            
            # LLM에서 응답 받기
            response = await self._invoke_llm(prompt_template, input_data)
            
            # 상호작용 로그 기록
            self._log_interaction(state, f"Schema tables: {len(state.schema_analysis.relevant_tables)}", response)
            
            # 응답 파싱 및 결과 생성
            try:
                # 응답에서 JSON 추출
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = response[json_start:json_end]
                    plan_data = json.loads(json_str)
                else:
                    raise ValueError("No valid JSON found in response")
                
                # 구조화된 결과로 변환
                query_plan = QueryPlan(
                    query_steps=plan_data.get("query_steps", []),
                    join_strategy=plan_data.get("join_strategy", []),
                    subquery_structure=plan_data.get("subquery_structure", []),
                    complexity_level=plan_data.get("complexity_level", "알 수 없음"),
                    estimated_performance=plan_data.get("estimated_performance", "성능 예측 불가")
                )
                
                # 상태 업데이트
                state.query_plan = query_plan
                state.current_step = ProcessingStep.SQL_DEVELOPMENT
                state.processing_history.append(
                    f"쿼리 계획 수립 완료: {len(query_plan.query_steps)}단계, 복잡도 {query_plan.complexity_level}"
                )
                
                return state
                
            except (json.JSONDecodeError, ValueError) as e:
                # 대체: 응답 텍스트로부터 기본 계획 생성
                state.query_plan = QueryPlan(
                    query_steps=[f"쿼리 계획 파싱 오류: {str(e)}"],
                    join_strategy=[],
                    subquery_structure=[],
                    complexity_level="알 수 없음",
                    estimated_performance=f"계획 파싱 실패: {response[:500]}"
                )
                state.current_step = ProcessingStep.ERROR
                state.error_message = f"쿼리 계획 파싱 실패: {str(e)}"
                return state
                
        except Exception as e:
            state.current_step = ProcessingStep.ERROR
            state.error_message = f"쿼리 계획 수립 중 오류 발생: {str(e)}"
            state.processing_history.append(f"쿼리 계획 실패: {str(e)}")
            return state