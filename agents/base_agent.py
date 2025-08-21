# 멀티에이전트 텍스트-SQL 시스템 기본 에이전트 클래스
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import json
import os
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from config import config
from models import AgentState, AgentType

class BaseAgent(ABC):
    # 시스템 모든 에이전트의 기본 클래스
    
    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type
        self.llm = self._initialize_llm()
        self.schema_data = self._load_schema_data()
    
    def _initialize_llm(self):
        # 설정에 따라 언어 모델 초기화
        if config.api.model_provider == "openai":
            if not config.api.openai_api_key:
                raise ValueError("OpenAI API key is required")
            return ChatOpenAI(
                api_key=config.api.openai_api_key,
                model=config.api.model_name,
                temperature=config.api.temperature,
                max_tokens=config.api.max_tokens
            )
        elif config.api.model_provider == "anthropic":
            if not config.api.anthropic_api_key:
                raise ValueError("Anthropic API key is required")
            return ChatAnthropic(
                api_key=config.api.anthropic_api_key,
                model=config.api.model_name,
                temperature=config.api.temperature,
                max_tokens=config.api.max_tokens
            )
        else:
            raise ValueError(f"Unsupported model provider: {config.api.model_provider}")
    
    def _load_schema_data(self) -> Dict[str, Any]:
        # JSON 파일에서 스키마 데이터 로드
        schema_path = config.database.schema_path
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _create_prompt_template(self, system_message: str) -> ChatPromptTemplate:
        # 시스템 메시지와 사용자 메시지로 프롬프트 템플릿 생성
        return ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", "{input}")
        ])
    
    async def _invoke_llm(self, prompt_template: ChatPromptTemplate, input_data: Dict[str, Any]) -> str:
        # 주어진 프롬프트와 입력으로 언어 모델 호출
        try:
            chain = prompt_template | self.llm
            response = await chain.ainvoke(input_data)
            return response.content
        except Exception as e:
            if config.debug:
                print(f"LLM invocation error in {self.agent_type}: {e}")
            raise
    
    def _log_interaction(self, state: AgentState, input_data: str, output_data: str):
        # 에이전트 상호작용 로그
        interaction = {
            "agent": self.agent_type.value,
            "input": input_data[:500] + "..." if len(input_data) > 500 else input_data,
            "output": output_data[:500] + "..." if len(output_data) > 500 else output_data,
            "step": state.current_step.value
        }
        state.agent_interactions.append(interaction)
    
    @abstractmethod
    async def process(self, state: AgentState) -> AgentState:
        # 에이전트 상태 처리 후 업데이트된 상태 반환
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        # 이 에이전트의 시스템 프롬프트 반환
        pass