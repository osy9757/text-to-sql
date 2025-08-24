# 스키마 분석 에이전트 - MySQL 스키마 분석 및 관련 테이블/컬럼 식별
import json
from typing import List, Dict, Any
from models import AgentState, AgentType, ProcessingStep, SchemaAnalysisResult, TableInfo
from .base_agent import BaseAgent

class SchemaAnalystAgent(BaseAgent):
    # MySQL 스키마 분석 및 테이블/컬럼 선택 담당 에이전트
    
    def __init__(self):
        super().__init__(AgentType.SCHEMA_ANALYST)
    
    def get_system_prompt(self) -> str:
        return """
당신은 MySQL 데이터베이스 스키마 분석 전문가입니다.

**주요 역할:**
1. 한국어 자연어 질의를 분석하여 관련 테이블과 컬럼을 식별
2. 테이블 간의 관계(외래키)를 파악하여 JOIN 전략 수립
3. 질의에 필요한 최소한의 테이블만 선별하여 성능 최적화

**분석 과정:**
1. 사용자 질의에서 핵심 엔티티와 속성 추출
2. 스키마의 aliases를 활용하여 한국어 표현을 테이블/컬럼에 매핑
3. 필요한 테이블들 간의 관계 분석
4. JOIN이 필요한 경우 최적의 연결 경로 제안

**출력 형식:**
```json
{{
    "relevant_tables": [
        {{
            "name": "User",
            "table": "tb_user", 
            "aliases": ["사용자", "유저"],
            "attributes": {{
                "id": {{"column": "id", "type": "bigint", "aliases": ["사용자ID"]}},
                "name": {{"column": "name", "type": "varchar(50)", "aliases": ["이름"]}}
            }},
            "relationships": ["tb_deposit via userId"]
        }}
    ],
    "key_relationships": [
        "tb_user.id = tb_deposit.userId",
        "tb_deposit.id = tb_orderHistory.depositId0"
    ],
    "suggested_joins": [
        "JOIN tb_deposit ON tb_user.id = tb_deposit.userId",
        "JOIN tb_orderHistory ON tb_deposit.id = tb_orderHistory.depositId0"
    ],
    "analysis_notes": "사용자의 거래 내역을 조회하기 위해 사용자-예치금-주문내역 테이블을 연결해야 합니다."
}}
```

**중요 사항:**
- 한국어 별칭을 적극 활용하여 정확한 매핑 수행
- 불필요한 테이블은 제외하여 쿼리 성능 최적화
- 복합키나 특수한 관계도 정확히 식별
- MySQL 특화 제약사항 고려 (예: 외래키 제약, 인덱스 활용)
"""

    async def process(self, state: AgentState) -> AgentState:
        # 스키마 분석 및 쿼리 관련 테이블 식별
        try:
            # 분석 프롬프트 생성
            prompt_template = self._create_prompt_template(self.get_system_prompt())
            
            # 입력 데이터 준비
            input_data = {
                "input": f"""
**사용자 질의:** {state.user_query}

**사용 가능한 데이터베이스 스키마:**
{json.dumps(self.schema_data, ensure_ascii=False, indent=2)}

위 스키마를 분석하여 사용자 질의를 처리하는데 필요한 테이블과 컬럼을 식별하고, 
테이블 간의 관계를 파악하여 JSON 형식으로 응답해주세요.
"""
            }
            
            # LLM에서 응답 받기
            response = await self._invoke_llm(prompt_template, input_data)
            
            # 상호작용 로그 기록
            self._log_interaction(state, state.user_query, response)
            
            # 응답 파싱 및 결과 생성
            try:
                # 응답에서 JSON 추출
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = response[json_start:json_end]
                    analysis_data = json.loads(json_str)
                else:
                    raise ValueError("No valid JSON found in response")
                
                # 구조화된 결과로 변환
                relevant_tables = []
                for table_data in analysis_data.get("relevant_tables", []):
                    table_info = TableInfo(
                        name=table_data.get("name", ""),
                        table=table_data.get("table", ""),
                        aliases=table_data.get("aliases", []),
                        attributes=table_data.get("attributes", {}),
                        relationships=table_data.get("relationships", [])
                    )
                    relevant_tables.append(table_info)
                
                schema_result = SchemaAnalysisResult(
                    relevant_tables=relevant_tables,
                    key_relationships=analysis_data.get("key_relationships", []),
                    suggested_joins=analysis_data.get("suggested_joins", []),
                    analysis_notes=analysis_data.get("analysis_notes", "")
                )
                
                # 상태 업데이트
                state.schema_analysis = schema_result
                state.current_step = ProcessingStep.QUERY_PLANNING
                state.processing_history.append(f"스키마 분석 완료: {len(relevant_tables)}개 테이블 식별")
                
                return state
                
            except (json.JSONDecodeError, ValueError) as e:
                # 대체: 응답 텍스트로부터 기본 분석 생성
                state.schema_analysis = SchemaAnalysisResult(
                    relevant_tables=[],
                    key_relationships=[],
                    suggested_joins=[],
                    analysis_notes=f"스키마 분석 결과 파싱 오류: {str(e)}\n원본 응답: {response[:500]}"
                )
                state.current_step = ProcessingStep.ERROR
                state.error_message = f"스키마 분석 결과 파싱 실패: {str(e)}"
                return state
                
        except Exception as e:
            state.current_step = ProcessingStep.ERROR
            state.error_message = f"스키마 분석 중 오류 발생: {str(e)}"
            state.processing_history.append(f"스키마 분석 실패: {str(e)}")
            return state