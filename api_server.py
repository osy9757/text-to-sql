#!/usr/bin/env python3
"""
Text-to-SQL API Server
FastAPI 기반 웹 서버로 Flutter 클라이언트와 연동
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import traceback

# 기존 Text-to-SQL 시스템 import
from main import TextToSQLApp

app = FastAPI(
    title="Text-to-SQL API",
    description="자연어를 SQL로 변환하는 API 서버",
    version="1.0.0"
)

# CORS 설정 - Flutter 웹에서 접근할 수 있도록
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용, 실제 배포 시에는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Text-to-SQL 애플리케이션 초기화 (실제 DB 사용)
text_to_sql_app = TextToSQLApp(enable_sql_execution=True, use_real_db=True)

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    success: bool
    result: str
    sql: str
    data: List[Dict[str, Any]]
    execution_time: float
    timestamp: str
    error_type: Optional[str] = None
    error_details: Optional[str] = None

@app.get("/")
async def root():
    """API 상태 확인"""
    return {
        "message": "Text-to-SQL API Server",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/db-check")
async def check_database_connection():
    """데이터베이스 연결 상태 확인 엔드포인트"""
    start_time = asyncio.get_event_loop().time()
    
    try:
        # Text-to-SQL 앱을 통해 DB 연결 테스트
        from database_connector import RealDatabaseConnection
        from config import config
        
        # DB 연결 인스턴스 생성
        db_connection = RealDatabaseConnection(environment=config.database.environment)
        
        # 간단한 테스트 쿼리 실행
        test_result = await db_connection.execute_query("SELECT 1 as test_connection")
        
        execution_time = asyncio.get_event_loop().time() - start_time
        
        if test_result.get("success", False):
            # DB 설정 정보 가져오기
            try:
                ssh_config, db_config = config.database.get_current_configs()
                db_info = {
                    "host": db_config.host,
                    "port": db_config.port,
                    "database": db_config.database,
                    "environment": config.database.environment
                }
            except Exception:
                db_info = {
                    "environment": config.database.environment
                }
                
            return {
                "success": True,
                "status": "connected",
                "message": "✅ 데이터베이스 연결이 정상입니다.",
                "connection_time": round(execution_time, 3),
                "database_info": db_info,
                "test_query_result": test_result.get("data", []),
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "status": "error",
                "message": f"❌ 데이터베이스 연결 실패: {test_result.get('error', '알 수 없는 오류')}",
                "connection_time": round(execution_time, 3),
                "error_details": test_result.get("error"),
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        execution_time = asyncio.get_event_loop().time() - start_time
        return {
            "success": False,
            "status": "error",
            "message": f"❌ 데이터베이스 연결 테스트 중 오류 발생: {str(e)}",
            "connection_time": round(execution_time, 3),
            "error_details": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    자연어 쿼리를 처리하여 SQL로 변환하고 실행
    """
    start_time = asyncio.get_event_loop().time()
    
    try:
        if not request.query or not request.query.strip():
            execution_time = asyncio.get_event_loop().time() - start_time
            return QueryResponse(
                success=False,
                result="❌ 처리 실패: 쿼리가 비어있습니다.",
                sql="",
                data=[],
                execution_time=round(execution_time, 2),
                timestamp=datetime.now().isoformat(),
                error_type="validation",
                error_details="Empty query provided"
            )
        
        print(f"[{datetime.now().isoformat()}] 쿼리 처리 시작: {request.query}")
        
        # Text-to-SQL 애플리케이션 실행
        response = await text_to_sql_app.convert(
            query=request.query.strip(),
            language="korean",
            include_explanation=True,
            optimize_for_performance=True
        )
        
        execution_time = asyncio.get_event_loop().time() - start_time
        
        # 응답이 실패한 경우
        if not response.success:
            raise Exception(response.error_message or "쿼리 처리에 실패했습니다.")
        
        # 결과 파싱
        sql_query = response.sql_query or ""
        execution_data = response.execution_data or []
        
        # 성공 메시지 생성
        if execution_data:
            data_count = len(execution_data)
            if data_count == 1 and "사용자수" in str(execution_data[0]):
                result_message = f"✅ 사용자 수 조회가 완료되었습니다."
            elif any("연령대" in str(item) for item in execution_data):
                if any("거래액" in str(item) for item in execution_data):
                    total_amount = sum(
                        float(str(item.get("연령대별_거래액", "0")).replace(",", "").replace("원", "")) 
                        for item in execution_data if "연령대별_거래액" in item
                    )
                    result_message = f"✅ 연령대별 거래액 비율 조회가 완료되었습니다. (총 거래액: {total_amount:,.0f}원)"
                else:
                    result_message = f"✅ 연령대별 사용자 비율 조회가 완료되었습니다. (총 {data_count}개 연령대 분석)"
            else:
                result_message = f"✅ 쿼리가 성공적으로 실행되었습니다. ({data_count}개 결과)"
        else:
            result_message = "✅ 쿼리가 성공적으로 실행되었습니다."
        
        print(f"[{datetime.now().isoformat()}] 쿼리 처리 완료: {execution_time:.2f}초")
        
        return QueryResponse(
            success=True,
            result=result_message,
            sql=sql_query,
            data=execution_data,
            execution_time=round(execution_time, 2),
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        execution_time = asyncio.get_event_loop().time() - start_time
        error_message = str(e)
        
        print(f"[{datetime.now().isoformat()}] 쿼리 처리 오류: {error_message}")
        print(f"Traceback: {traceback.format_exc()}")
        
        # 에러 타입 및 사용자 친화적 메시지 분류
        error_type = "unknown"
        user_friendly_message = error_message
        
        if "connection" in error_message.lower():
            error_type = "database_connection"
            user_friendly_message = "데이터베이스 연결에 실패했습니다. 연결 설정을 확인해주세요."
        elif "sql" in error_message.lower():
            error_type = "sql_generation"
            user_friendly_message = "SQL 생성 또는 실행 중 오류가 발생했습니다."
        elif "timeout" in error_message.lower():
            error_type = "timeout"
            user_friendly_message = "쿼리 실행 시간이 초과되었습니다."
        elif "validation" in error_message.lower():
            error_type = "validation"
            user_friendly_message = "쿼리 검증 중 오류가 발생했습니다."
        else:
            error_type = "processing"
            user_friendly_message = "쿼리 처리 중 오류가 발생했습니다."
        
        return QueryResponse(
            success=False,
            result=f"❌ 처리 실패: {user_friendly_message}",
            sql="",
            data=[],
            execution_time=round(execution_time, 2),
            timestamp=datetime.now().isoformat(),
            error_type=error_type,
            error_details=error_message
        )

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🚀 Text-to-SQL API Server 시작")
    print("📍 URL: http://localhost:8000")
    print("📚 Docs: http://localhost:8000/docs")
    print("🔍 Health: http://localhost:8000/health")
    print("=" * 60)
    
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )