# 데이터베이스 연결 및 SQL 실행을 위한 인터페이스
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
import re
import time
from datetime import datetime
from pathlib import Path

class DatabaseConnection(ABC):
    # 데이터베이스 연결 추상 클래스
    
    @abstractmethod
    async def execute_query(self, sql: str, timeout: int = 30) -> Dict[str, Any]:
        """
        SQL 쿼리 실행
        
        Args:
            sql: 실행할 SQL 쿼리
            timeout: 타임아웃 (초)
            
        Returns:
            Dict[str, Any]: 실행 결과
            {
                "success": bool,
                "data": List[Dict] | None,
                "columns": List[str] | None,
                "row_count": int,
                "execution_time": float,
                "error": str | None
            }
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """데이터베이스 연결 테스트"""
        pass
    
    @abstractmethod
    async def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """테이블 정보 조회"""
        pass

class MockDatabaseConnection(DatabaseConnection):
    # 개발/테스트용 모의 데이터베이스 연결
    
    def __init__(self):
        self.connected = False
        
    async def execute_query(self, sql: str, timeout: int = 30) -> Dict[str, Any]:
        # 모의 실행 (실제 DB 연결 전 테스트용)
        start_time = time.time()
        
        # SQL 안전성 검증
        if not self._is_safe_query(sql):
            return {
                "success": False,
                "data": None,
                "columns": None,
                "row_count": 0,
                "execution_time": time.time() - start_time,
                "error": "허용되지 않는 SQL 구문입니다. SELECT 쿼리만 허용됩니다."
            }
        
        # SQL에 따른 적절한 모의 응답 생성
        sql_upper = sql.upper()
        
        if "COUNT" in sql_upper:
            # COUNT 쿼리인 경우
            return {
                "success": True,
                "data": [{"사용자 수": 1247}, {"COUNT(*)": 1247}, {"COUNT(ID)": 1247}][0:1],
                "columns": ["사용자 수"] if "사용자 수" in sql else ["COUNT(*)"] if "COUNT(*)" in sql else ["COUNT(ID)"],
                "row_count": 1,
                "execution_time": time.time() - start_time,
                "error": None
            }
        elif "tb_user" in sql.lower() and ("LIMIT 5" in sql_upper or "TOP 5" in sql_upper):
            # 최근 사용자 조회인 경우
            return {
                "success": True,
                "data": [
                    {"id": 1001, "name": "홍길동", "email": "hong@test.com", "생성일시": "2025-08-20 15:30:00"},
                    {"id": 1002, "name": "김철수", "email": "kim@test.com", "생성일시": "2025-08-21 09:15:00"},
                    {"id": 1003, "name": "이영희", "email": "lee@test.com", "생성일시": "2025-08-21 14:22:00"},
                    {"id": 1004, "name": "박민수", "email": "park@test.com", "생성일시": "2025-08-22 10:10:00"},
                    {"id": 1005, "name": "최지은", "email": "choi@test.com", "생성일시": "2025-08-22 11:45:00"}
                ],
                "columns": ["id", "name", "email", "생성일시"],
                "row_count": 5,
                "execution_time": time.time() - start_time,
                "error": None
            }
        elif "tb_user" in sql.lower():
            # 일반적인 tb_user 조회
            return {
                "success": True,
                "data": [
                    {"id": 1001, "name": "홍길동", "email": "hong@test.com"},
                    {"id": 1002, "name": "김철수", "email": "kim@test.com"},
                    {"id": 1003, "name": "이영희", "email": "lee@test.com"}
                ],
                "columns": ["id", "name", "email"],
                "row_count": 3,
                "execution_time": time.time() - start_time,
                "error": None
            }
        elif "tb_transaction" in sql.lower():
            # 거래 관련 쿼리
            return {
                "success": True,
                "data": [
                    {"사용자 이름": "홍길동", "총 거래 금액": 1500000},
                    {"사용자 이름": "김철수", "총 거래 금액": 1200000},
                    {"사용자 이름": "이영희", "총 거래 금액": 1000000}
                ],
                "columns": ["사용자 이름", "총 거래 금액"],
                "row_count": 3,
                "execution_time": time.time() - start_time,
                "error": None
            }
        else:
            # 기본 응답
            return {
                "success": True,
                "data": [{"result": "SUCCESS"}],
                "columns": ["result"],
                "row_count": 1,
                "execution_time": time.time() - start_time,
                "error": None
            }
    
    async def test_connection(self) -> bool:
        # 모의 연결 테스트
        return True
    
    async def get_table_info(self, table_name: str) -> Dict[str, Any]:
        # 모의 테이블 정보
        return {
            "exists": True,
            "columns": ["id", "name", "amount"],
            "primary_key": "id"
        }
    
    def _is_safe_query(self, sql: str) -> bool:
        # SQL 안전성 검증
        sql_upper = sql.upper().strip()
        
        # SELECT만 허용
        if not sql_upper.startswith('SELECT'):
            return False
            
        # 금지된 키워드 검사 (단어 경계 사용)
        forbidden_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
            'TRUNCATE', 'REPLACE', 'MERGE', 'GRANT', 'REVOKE',
            'EXEC', 'EXECUTE', 'CALL', 'LOAD', 'OUTFILE', 'DUMPFILE'
        ]
        
        import re
        for keyword in forbidden_keywords:
            # 단어 경계를 사용하여 정확한 키워드만 매치
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, sql_upper):
                return False
                
        return True

class RealDatabaseConnection(DatabaseConnection):
    # SSH 터널을 통한 실제 MySQL 데이터베이스 연결
    
    def __init__(self, environment: str = "stage"):
        from config import config
        self.environment = environment
        self.ssh_config, self.db_config = config.database.get_current_configs() if environment == config.database.environment else self._get_env_configs(environment)
        self.tunnel = None
        self.connection = None
        
    def _get_env_configs(self, environment: str):
        """지정된 환경의 설정 반환"""
        from config import config
        if environment == 'stage':
            return config.database.ssh_config_stage, config.database.db_config_stage
        elif environment == 'prod':
            return config.database.ssh_config_prod, config.database.db_config_prod
        else:
            raise ValueError(f"지원하지 않는 환경입니다: {environment}")
    
    async def _ensure_connection(self):
        """SSH 터널 및 DB 연결 보장"""
        if self.tunnel is None or self.connection is None:
            await self._create_connection()
    
    async def _create_connection(self):
        """SSH 터널 및 DB 연결 생성"""
        try:
            from sshtunnel import SSHTunnelForwarder
            import pymysql
            import asyncio
            
            # 기존 연결 정리
            await self._cleanup_connection()
            
            # SSH 터널 생성
            self.tunnel = SSHTunnelForwarder(
                (self.ssh_config.host, self.ssh_config.port),
                ssh_username=self.ssh_config.username,
                ssh_pkey=self.ssh_config.key_file,
                remote_bind_address=(self.db_config.host, self.db_config.port),
                local_bind_address=('localhost', self.ssh_config.local_bind_port)
            )
            
            # SSH 터널 시작 (비동기적으로 처리)
            await asyncio.get_event_loop().run_in_executor(None, self.tunnel.start)
            
            # DB 연결
            self.connection = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: pymysql.connect(
                    host='localhost',
                    port=self.ssh_config.local_bind_port,
                    user=self.db_config.username,
                    password=self.db_config.password,
                    db=self.db_config.database,
                    charset='utf8mb4',
                    connect_timeout=30,
                    read_timeout=30,
                    write_timeout=30
                )
            )
            
        except Exception as e:
            await self._cleanup_connection()
            raise ConnectionError(f"DB 연결 실패 ({self.environment}): {str(e)}")
    
    async def _cleanup_connection(self):
        """연결 정리"""
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
            self.connection = None
            
        if self.tunnel:
            try:
                self.tunnel.stop()
            except:
                pass
            self.tunnel = None
    
    async def execute_query(self, sql: str, timeout: int = 30) -> Dict[str, Any]:
        """SQL 쿼리 실행"""
        start_time = time.time()
        
        try:
            # SQL 안전성 검증
            is_safe, errors = SQLValidator.validate_sql_safety(sql)
            if not is_safe:
                return {
                    "success": False,
                    "data": None,
                    "columns": None,
                    "row_count": 0,
                    "execution_time": time.time() - start_time,
                    "error": f"안전하지 않은 SQL: {', '.join(errors)}"
                }
            
            # 연결 보장
            await self._ensure_connection()
            
            # 쿼리 실행
            import asyncio
            result = await asyncio.get_event_loop().run_in_executor(
                None, 
                self._execute_sync_query, 
                sql, 
                timeout
            )
            
            result["execution_time"] = time.time() - start_time
            return result
            
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "columns": None,
                "row_count": 0,
                "execution_time": time.time() - start_time,
                "error": f"쿼리 실행 오류: {str(e)}"
            }
    
    def _execute_sync_query(self, sql: str, timeout: int) -> Dict[str, Any]:
        """동기 쿼리 실행 (executor에서 실행됨)"""
        try:
            import pymysql.cursors
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(sql)
                
                # 결과 가져오기
                rows = cursor.fetchall()
                
                # 컬럼 정보 추출
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                return {
                    "success": True,
                    "data": list(rows),
                    "columns": columns,
                    "row_count": len(rows),
                    "error": None
                }
                
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "columns": None,
                "row_count": 0,
                "error": str(e)
            }
    
    async def test_connection(self) -> bool:
        """연결 테스트"""
        try:
            await self._ensure_connection()
            
            # 간단한 테스트 쿼리 실행
            result = await self.execute_query("SELECT 1 as test;")
            return result["success"]
            
        except:
            return False
    
    async def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """테이블 정보 조회"""
        try:
            await self._ensure_connection()
            
            # 테이블 존재 여부 확인
            check_query = f"SHOW TABLES LIKE '{table_name}';"
            check_result = await self.execute_query(check_query)
            
            if not check_result["success"] or not check_result["data"]:
                return {
                    "exists": False,
                    "columns": [],
                    "primary_key": None,
                    "error": "테이블이 존재하지 않습니다."
                }
            
            # 컬럼 정보 조회
            desc_query = f"DESCRIBE {table_name};"
            desc_result = await self.execute_query(desc_query)
            
            if not desc_result["success"]:
                return {
                    "exists": True,
                    "columns": [],
                    "primary_key": None,
                    "error": f"테이블 구조 조회 실패: {desc_result['error']}"
                }
            
            # 결과 파싱
            columns = [col["Field"] for col in desc_result["data"]]
            primary_keys = [col["Field"] for col in desc_result["data"] if col["Key"] == "PRI"]
            primary_key = primary_keys[0] if primary_keys else None
            
            return {
                "exists": True,
                "columns": columns,
                "primary_key": primary_key,
                "column_info": desc_result["data"]
            }
            
        except Exception as e:
            return {
                "exists": False,
                "columns": [],
                "primary_key": None,
                "error": f"테이블 정보 조회 오류: {str(e)}"
            }
    
    async def close(self):
        """연결 종료"""
        await self._cleanup_connection()
        
    def __del__(self):
        """소멸자에서 연결 정리"""
        import asyncio
        try:
            if self.connection or self.tunnel:
                # 이벤트 루프가 있으면 비동기적으로 정리
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._cleanup_connection())
                else:
                    loop.run_until_complete(self._cleanup_connection())
        except:
            # 동기적으로 정리
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass
            if self.tunnel:
                try:
                    self.tunnel.stop()
                except:
                    pass

class SQLValidator:
    # SQL 쿼리 안전성 및 유효성 검증
    
    @staticmethod
    def validate_sql_safety(sql: str) -> Tuple[bool, List[str]]:
        """
        SQL 안전성 검증
        
        Returns:
            Tuple[bool, List[str]]: (안전여부, 오류목록)
        """
        errors = []
        sql_upper = sql.upper().strip()
        
        # 1. SELECT만 허용
        if not sql_upper.startswith('SELECT'):
            errors.append("SELECT 쿼리만 허용됩니다.")
            return False, errors
        
        # 2. 금지된 키워드 검사 (단어 경계 사용)
        forbidden_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
            'TRUNCATE', 'REPLACE', 'MERGE', 'GRANT', 'REVOKE',
            'EXEC', 'EXECUTE', 'CALL', 'LOAD', 'OUTFILE', 'DUMPFILE',
            'INTO OUTFILE', 'INTO DUMPFILE'
        ]
        
        import re
        for keyword in forbidden_keywords:
            # 단어 경계를 사용하여 정확한 키워드만 매치
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, sql_upper):
                errors.append(f"금지된 키워드가 포함되어 있습니다: {keyword}")
        
        # 3. 서브쿼리 내 금지 명령 검사
        subquery_pattern = r'\(([^)]+)\)'
        subqueries = re.findall(subquery_pattern, sql_upper)
        for subquery in subqueries:
            for keyword in forbidden_keywords:
                # 서브쿼리에서도 단어 경계 사용
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, subquery):
                    errors.append(f"서브쿼리에 금지된 키워드가 포함되어 있습니다: {keyword}")
        
        # 4. 주석을 통한 SQL 인젝션 방지
        if '--' in sql or '/*' in sql or '*/' in sql:
            errors.append("주석은 허용되지 않습니다.")
        
        # 5. 세미콜론 개수 제한 (다중 쿼리 방지)
        if sql.count(';') > 1:
            errors.append("다중 쿼리는 허용되지 않습니다.")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_result_expectation(result: Dict[str, Any], expected_type: str) -> Tuple[bool, List[str]]:
        """
        쿼리 결과가 기대와 일치하는지 검증
        
        Args:
            result: 쿼리 실행 결과
            expected_type: 기대하는 결과 타입 ("user_list", "aggregation", "count" 등)
            
        Returns:
            Tuple[bool, List[str]]: (유효여부, 검증메시지)
        """
        issues = []
        
        if not result["success"]:
            return False, ["쿼리 실행에 실패했습니다."]
        
        data = result["data"]
        row_count = result["row_count"]
        
        # 1. 결과 존재 여부 검증
        if row_count == 0:
            issues.append("결과가 0건입니다. 조건이 너무 제한적이거나 데이터가 없을 수 있습니다.")
        
        # 2. 결과 타입별 검증
        if expected_type == "user_list" and row_count > 0:
            # 사용자 목록 쿼리 검증
            columns = result["columns"]
            if not any("이름" in col or "name" in col.lower() for col in columns):
                issues.append("사용자 이름 컬럼이 없습니다.")
        
        elif expected_type == "aggregation" and row_count > 0:
            # 집계 쿼리 검증
            columns = result["columns"]
            if not any("총" in col or "합계" in col or "평균" in col for col in columns):
                issues.append("집계 결과 컬럼을 찾을 수 없습니다.")
        
        elif expected_type == "top_n" and row_count > 0:
            # TOP N 쿼리 검증
            if row_count > 100:  # TOP N 쿼리인데 너무 많은 결과
                issues.append(f"TOP N 쿼리 결과가 너무 많습니다 ({row_count}건). LIMIT 절을 확인해주세요.")
        
        # 3. 데이터 품질 검증
        if data and len(data) > 0:
            first_row = data[0]
            for col_name, value in first_row.items():
                if value is None:
                    issues.append(f"'{col_name}' 컬럼에 NULL 값이 있습니다.")
                elif isinstance(value, str) and value.strip() == "":
                    issues.append(f"'{col_name}' 컬럼에 빈 문자열이 있습니다.")
        
        return len(issues) == 0, issues