# LangGraph를 사용한 텍스트-SQL 변환 멀티에이전트 오케스트레이터
import asyncio
import time
import os
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# 환경변수로 recursion limit 설정
os.environ["LANGCHAIN_GRAPH_RECURSION_LIMIT"] = "100"

from models import AgentState, ProcessingStep, TextToSQLRequest, TextToSQLResponse
from agents.schema_analyst import SchemaAnalystAgent
from agents.query_planner import QueryPlannerAgent
from agents.sql_developer import SQLDeveloperAgent
from agents.quality_validator import QualityValidatorAgent
from sql_execution_agent import SQLExecutionAgent
from config import config
from logger import debug_logger

class TextToSQLOrchestrator:
    # 멀티에이전트 텍스트-SQL 변환 프로세스 오케스트레이션
    
    def __init__(self, enable_sql_execution: bool = True, use_real_db: bool = False):
        self.schema_analyst = SchemaAnalystAgent()
        self.query_planner = QueryPlannerAgent()
        self.sql_developer = SQLDeveloperAgent()
        self.quality_validator = QualityValidatorAgent()
        self.sql_executor = SQLExecutionAgent(use_real_db=use_real_db) if enable_sql_execution else None
        self.enable_sql_execution = enable_sql_execution
        self.use_real_db = use_real_db
        self.workflow = self._build_workflow()
        
        # 현재 세션 ID 저장
        self.current_session_id = None
    
    def _build_workflow(self) -> StateGraph:
        # LangGraph 워크플로우 구축
        # 상태 그래프 생성
        workflow = StateGraph(AgentState)
        
        # 각 에이전트에 대한 노드 추가
        workflow.add_node("schema_analyst", self._schema_analysis_node)
        workflow.add_node("query_planner", self._query_planning_node)
        workflow.add_node("sql_developer", self._sql_development_node)
        workflow.add_node("quality_validator", self._quality_validation_node)
        if self.enable_sql_execution:
            workflow.add_node("sql_executor", self._sql_execution_node)
        workflow.add_node("error_handler", self._error_handler_node)
        
        # 진입점 설정
        workflow.set_entry_point("schema_analyst")
        
        # 조건부 엣지 추가
        workflow.add_conditional_edges(
            "schema_analyst",
            self._route_after_schema_analysis,
            {
                "query_planner": "query_planner",
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "query_planner", 
            self._route_after_query_planning,
            {
                "sql_developer": "sql_developer",
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "sql_developer",
            self._route_after_sql_development,
            {
                "quality_validator": "quality_validator",
                "error": "error_handler"
            }
        )
        
        if self.enable_sql_execution:
            workflow.add_conditional_edges(
                "quality_validator",
                self._route_after_validation,
                {
                    "sql_executor": "sql_executor",
                    "error": "error_handler"
                }
            )
            
            workflow.add_conditional_edges(
                "sql_executor",
                self._route_after_execution,
                {
                    "end": END,
                    "sql_developer": "sql_developer",  # 재시도
                    "error": "error_handler"
                }
            )
        else:
            workflow.add_conditional_edges(
                "quality_validator",
                self._route_after_validation,
                {
                    "end": END,
                    "error": "error_handler"
                }
            )
        
        workflow.add_edge("error_handler", END)
        
        # 상태 지속성을 위한 체크포인트로 컴파일
        memory = MemorySaver()
        return workflow.compile(checkpointer=memory)
    
    async def _schema_analysis_node(self, state: AgentState) -> AgentState:
        # 스키마 분석 노드
        if config.debug:
            print("🔍 Starting schema analysis...")
        debug_logger.log_processing_step("스키마 분석 시작")
        result = await self.schema_analyst.process(state)
        debug_logger.log_processing_step("스키마 분석 완료")
        return result
    
    async def _query_planning_node(self, state: AgentState) -> AgentState:
        # 쿼리 계획 노드
        if config.debug:
            print("📋 Starting query planning...")
        debug_logger.log_processing_step("쿼리 계획 수립 시작")
        result = await self.query_planner.process(state)
        debug_logger.log_processing_step("쿼리 계획 수립 완료")
        return result
    
    async def _sql_development_node(self, state: AgentState) -> AgentState:
        # SQL 개발 노드
        if config.debug:
            print("💻 Starting SQL development...")
        debug_logger.log_processing_step("SQL 코드 생성 시작")
        result = await self.sql_developer.process(state)
        debug_logger.log_processing_step("SQL 코드 생성 완료")
        return result
    
    async def _quality_validation_node(self, state: AgentState) -> AgentState:
        # 품질 검증 노드
        if config.debug:
            print("✅ Starting quality validation...")
        debug_logger.log_processing_step("품질 검증 시작")
        result = await self.quality_validator.process(state)
        debug_logger.log_processing_step("품질 검증 완료")
        return result
    
    async def _sql_execution_node(self, state: AgentState) -> AgentState:
        # SQL 실행 노드
        if config.debug:
            print("🚀 Starting SQL execution...")
        debug_logger.log_processing_step("SQL 실행 시작")
        result = await self.sql_executor.process(state, self.current_session_id)
        debug_logger.log_processing_step("SQL 실행 완료")
        return result
    
    async def _error_handler_node(self, state: AgentState) -> AgentState:
        # 오류 처리 노드
        if config.debug:
            print(f"❌ Error occurred: {state.error_message}")
        state.current_step = ProcessingStep.ERROR
        return state
    
    def _route_after_schema_analysis(self, state: AgentState) -> str:
        # 스키마 분석 후 라우팅 결정
        if state.current_step == ProcessingStep.QUERY_PLANNING:
            return "query_planner"
        return "error"
    
    def _route_after_query_planning(self, state: AgentState) -> str:
        # 쿼리 계획 후 라우팅 결정
        if state.current_step == ProcessingStep.SQL_DEVELOPMENT:
            return "sql_developer"
        return "error"
    
    def _route_after_sql_development(self, state: AgentState) -> str:
        # SQL 개발 후 라우팅 결정
        if state.current_step == ProcessingStep.QUALITY_VALIDATION:
            return "quality_validator"
        return "error"
    
    def _route_after_validation(self, state: AgentState) -> str:
        # 품질 검증 후 라우팅 결정
        if self.enable_sql_execution:
            if state.current_step == ProcessingStep.SQL_EXECUTION:
                return "sql_executor"
            return "error"
        else:
            if state.current_step == ProcessingStep.COMPLETED:
                return "end"
            return "error"
    
    def _route_after_execution(self, state: AgentState) -> str:
        # SQL 실행 후 라우팅 결정
        if state.current_step == ProcessingStep.COMPLETED:
            return "end"
        elif state.current_step == ProcessingStep.SQL_DEVELOPMENT:
            return "sql_developer"  # 재시도
        return "error"
    
    async def convert_text_to_sql(self, request: TextToSQLRequest, session_id: Optional[str] = None) -> TextToSQLResponse:
        # 자연어 텍스트를 SQL 쿼리로 변환
        start_time = time.time()
        
        # 세션 ID 저장
        self.current_session_id = session_id
        
        try:
            # 초기 상태 생성
            initial_state = AgentState(
                user_query=request.query,
                original_language=request.language,
                current_step=ProcessingStep.SCHEMA_ANALYSIS
            )
            
            if config.debug:
                print(f"🚀 Starting text-to-SQL conversion for: '{request.query[:50]}...'")
            
            # 워크플로우 실행 (recursion_limit를 configurable에 포함)
            config_dict = {
                "configurable": {
                    "thread_id": f"session_{int(start_time)}"
                },
                "recursion_limit": 100  # recursion_limit를 최상위 레벨로 이동
            }
            
            # invoke 방식으로 실행 (더 간단하고 안정적)
            final_result = await self.workflow.ainvoke(initial_state, config_dict)
            
            # 결과 디버깅
            if config.debug:
                print(f"🔍 Final result type: {type(final_result)}")
                print(f"🔍 Final result keys: {list(final_result.keys()) if isinstance(final_result, dict) else 'Not a dict'}")
            
            # LangGraph 0.6+에서는 결과가 상태 딕셔너리 형태
            if isinstance(final_result, dict) and 'current_step' in final_result:
                # 딕셔너리를 AgentState 객체로 변환
                final_state = AgentState(**final_result)
                if config.debug:
                    print(f"🔍 Converted dict to AgentState: {final_state.current_step}")
            elif hasattr(final_result, 'current_step'):
                final_state = final_result
            else:
                raise Exception(f"상태 객체를 찾을 수 없습니다. 결과: {final_result}")
            
            # 처리 시간 계산
            processing_time = time.time() - start_time
            
            # 응답 생성
            if final_state.current_step == ProcessingStep.COMPLETED and final_state.final_sql:
                response = TextToSQLResponse(
                    success=True,
                    sql_query=final_state.final_sql,
                    explanation=final_state.explanation if request.include_explanation else None,
                    execution_data=final_state.execution_data if final_state.execution_data else [],
                    processing_steps=[step for step in final_state.processing_history],
                    processing_time=processing_time,
                    metadata={
                        "agent_interactions": len(final_state.agent_interactions),
                        "schema_tables_analyzed": len(final_state.schema_analysis.relevant_tables) if final_state.schema_analysis else 0,
                        "query_complexity": final_state.query_plan.complexity_level if final_state.query_plan else "unknown",
                        "validation_status": "passed" if final_state.validation_result and final_state.validation_result.is_valid else "failed",
                        "execution_status": "executed" if final_state.sql_execution_result else "not_executed"
                    }
                )
            else:
                response = TextToSQLResponse(
                    success=False,
                    error_message=final_state.error_message or "처리 과정에서 알 수 없는 오류가 발생했습니다.",
                    processing_steps=[step for step in final_state.processing_history],
                    processing_time=processing_time,
                    metadata={
                        "failed_at_step": final_state.current_step.value,
                        "agent_interactions": len(final_state.agent_interactions)
                    }
                )
            
            if config.debug:
                print(f"🏁 Conversion completed in {processing_time:.2f}s - Success: {response.success}")
            
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            if config.debug:
                print(f"💥 Conversion failed with exception: {str(e)}")
            
            return TextToSQLResponse(
                success=False,
                error_message=f"시스템 오류가 발생했습니다: {str(e)}",
                processing_time=processing_time,
                metadata={"exception": str(e)}
            )
    
    async def get_workflow_status(self, thread_id: str) -> Dict[str, Any]:
        # 워크플로우 실행의 현재 상태 가져오기
        try:
            config_dict = {"configurable": {"thread_id": thread_id}}
            snapshot = self.workflow.get_state(config_dict)
            
            if snapshot and snapshot.values:
                state = snapshot.values
                return {
                    "current_step": state.current_step.value,
                    "processing_history": state.processing_history,
                    "is_complete": state.current_step in [ProcessingStep.COMPLETED, ProcessingStep.ERROR],
                    "error_message": state.error_message
                }
            else:
                return {"status": "not_found"}
        except Exception as e:
            return {"status": "error", "message": str(e)}