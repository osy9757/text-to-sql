# 멀티에이전트 텍스트-SQL 시스템 메인 애플리케이션 인터페이스
import asyncio
import os
from typing import Optional
from orchestrator import TextToSQLOrchestrator
from models import TextToSQLRequest, TextToSQLResponse
from config import config
from logger import debug_logger

class TextToSQLApp:
    # 메인 애플리케이션 클래스
    
    def __init__(self, enable_sql_execution: bool = True, use_real_db: bool = False):
        self.orchestrator = TextToSQLOrchestrator(enable_sql_execution=enable_sql_execution, use_real_db=use_real_db)
    
    async def convert(
        self, 
        query: str, 
        language: str = "korean",
        include_explanation: bool = True,
        optimize_for_performance: bool = True
    ) -> TextToSQLResponse:
        # 자연어 쿼리를 SQL로 변환
        
        # 디버그 로깅 시작
        session_id = debug_logger.start_session(query)
        
        request = TextToSQLRequest(
            query=query,
            language=language,
            include_explanation=include_explanation,
            optimize_for_performance=optimize_for_performance
        )
        
        response = await self.orchestrator.convert_text_to_sql(request, session_id)
        
        # 최종 결과 로깅
        debug_logger.log_final_result(
            success=response.success,
            sql_query=response.sql_query,
            error_message=response.error_message,
            processing_time=response.processing_time,
            metadata=response.metadata
        )
        
        return response
    
    async def interactive_mode(self):
        # 대화형 모드로 실행
        print("🤖 멀티에이전트 Text-to-SQL 시스템")
        print("=" * 50)
        print("한국어 질의를 입력하시면 MySQL 쿼리로 변환해드립니다.")
        print("종료하려면 'quit' 또는 'exit'를 입력하세요.")
        print("=" * 50)
        
        while True:
            try:
                user_input = input("\n💬 질의: ").strip()
                
                if user_input.lower() in ['quit', 'exit', '종료', '끝']:
                    print("👋 시스템을 종료합니다.")
                    break
                
                if not user_input:
                    print("❌ 질의를 입력해주세요.")
                    continue
                
                print("\n🚀 처리 중...")
                response = await self.convert(user_input)
                
                if response.success:
                    print(f"\n✅ 변환 성공 (처리시간: {response.processing_time:.2f}초)")
                    print("\n📝 생성된 SQL:")
                    print("-" * 40)
                    print(response.sql_query)
                    print("-" * 40)
                    
                    if response.explanation:
                        print("\n📖 설명:")
                        print(response.explanation)
                    
                    if response.metadata:
                        print(f"\n📊 메타데이터:")
                        for key, value in response.metadata.items():
                            print(f"  - {key}: {value}")
                    
                    if config.debug and response.processing_steps:
                        print(f"\n🔍 처리 단계:")
                        for i, step in enumerate(response.processing_steps, 1):
                            print(f"  {i}. {step}")
                else:
                    print(f"\n❌ 변환 실패: {response.error_message}")
                    
                    if config.debug and response.processing_steps:
                        print(f"\n🔍 처리 단계:")
                        for i, step in enumerate(response.processing_steps, 1):
                            print(f"  {i}. {step}")
                
            except KeyboardInterrupt:
                print("\n\n👋 사용자가 중단했습니다.")
                break
            except Exception as e:
                print(f"\n💥 오류 발생: {str(e)}")

async def main():
    # 메인 함수
    # API 키 확인
    if not config.api.openai_api_key and not config.api.anthropic_api_key:
        print("❌ API 키가 설정되지 않았습니다.")
        print("환경변수를 설정하거나 다음과 같이 키를 입력해주세요:")
        
        if config.api.model_provider == "openai":
            api_key = input("OpenAI API Key: ").strip()
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
                config.api.openai_api_key = api_key
        else:
            api_key = input("Anthropic API Key: ").strip()
            if api_key:
                os.environ["ANTHROPIC_API_KEY"] = api_key
                config.api.anthropic_api_key = api_key
    
    # API 키 설정 확인
    if config.api.model_provider == "openai" and not config.api.openai_api_key:
        print("❌ OpenAI API 키가 필요합니다.")
        return
    elif config.api.model_provider == "anthropic" and not config.api.anthropic_api_key:
        print("❌ Anthropic API 키가 필요합니다.")
        return
    
    # 스키마 파일 존재 확인
    if not os.path.exists(config.database.schema_path):
        print(f"❌ 스키마 파일을 찾을 수 없습니다: {config.database.schema_path}")
        return
    
    print(f"🔧 모델: {config.api.model_provider} - {config.api.model_name}")
    print(f"📊 스키마: {config.database.schema_path}")
    
    # 앱 생성 및 실행 (SQL 실행 활성화)
    enable_sql_exec = os.getenv("ENABLE_SQL_EXECUTION", "true").lower() == "true"
    use_real_db = os.getenv("USE_REAL_DATABASE", "false").lower() == "true"
    app = TextToSQLApp(enable_sql_execution=enable_sql_exec, use_real_db=use_real_db)
    
    # 대화형 모드 또는 명령행 인수로 실행 여부 확인
    import sys
    if len(sys.argv) > 1:
        # 명령행 모드
        query = " ".join(sys.argv[1:])
        print(f"💬 질의: {query}")
        
        response = await app.convert(query)
        
        if response.success:
            print(f"\n✅ 변환 성공:")
            print(response.sql_query)
        else:
            print(f"\n❌ 변환 실패: {response.error_message}")
    else:
        # 대화형 모드
        await app.interactive_mode()

if __name__ == "__main__":
    asyncio.run(main())