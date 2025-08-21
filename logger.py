# 디버그 모드에서 사용자 질의와 응답을 로그 파일에 저장하는 모듈
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from config import config

class DebugLogger:
    # 디버그 로깅 전담 클래스
    
    def __init__(self, log_dir: str = "log"):
        self.log_dir = Path(log_dir)
        self.session_id = None
        self.current_log_file = None
        
        # 로그 디렉토리 생성
        if config.debug:
            self._ensure_log_directory()
    
    def _ensure_log_directory(self):
        # 로그 디렉토리 및 하위 구조 생성
        self.log_dir.mkdir(exist_ok=True)
        
        # 날짜별 하위 디렉토리
        today = datetime.now().strftime("%Y-%m-%d")
        self.daily_log_dir = self.log_dir / today
        self.daily_log_dir.mkdir(exist_ok=True)
    
    def start_session(self, user_query: str) -> str:
        # 새로운 세션 시작 및 로그 파일 생성
        if not config.debug:
            return ""
        
        # 세션 ID 생성 (타임스탬프 기반)
        timestamp = datetime.now()
        self.session_id = timestamp.strftime("%H%M%S_%f")[:-3]  # 밀리초까지
        
        # 로그 파일 경로 설정
        log_filename = f"session_{self.session_id}.json"
        self.current_log_file = self.daily_log_dir / log_filename
        
        # 초기 로그 데이터 구조
        initial_log = {
            "session_info": {
                "session_id": self.session_id,
                "start_time": timestamp.isoformat(),
                "user_query": user_query,
                "model_info": {
                    "provider": config.api.model_provider,
                    "model": config.api.model_name,
                    "temperature": config.api.temperature,
                    "max_tokens": config.api.max_tokens
                }
            },
            "agent_interactions": [],
            "processing_steps": [],
            "final_result": None,
            "performance_metrics": {
                "total_processing_time": None,
                "agent_call_count": 0,
                "tokens_used": {
                    "input": 0,
                    "output": 0
                }
            }
        }
        
        # 로그 파일 생성
        with open(self.current_log_file, 'w', encoding='utf-8') as f:
            json.dump(initial_log, f, ensure_ascii=False, indent=2)
        
        print(f"🗂️  세션 로그 시작: {self.current_log_file}")
        return self.session_id
    
    def log_agent_interaction(self, agent_name: str, input_data: str, output_data: str, processing_time: float = None):
        # 에이전트 상호작용 로깅
        if not config.debug or not self.current_log_file:
            return
        
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "input": input_data[:1000] + "..." if len(input_data) > 1000 else input_data,
            "output": output_data[:2000] + "..." if len(output_data) > 2000 else output_data,
            "processing_time": processing_time,
            "input_length": len(input_data),
            "output_length": len(output_data)
        }
        
        # 기존 로그 파일 읽기
        try:
            with open(self.current_log_file, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
        except:
            return  # 로그 파일 읽기 실패시 무시
        
        # 상호작용 추가
        log_data["agent_interactions"].append(interaction)
        log_data["performance_metrics"]["agent_call_count"] += 1
        
        # 로그 파일 업데이트
        with open(self.current_log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
    
    def log_processing_step(self, step: str, status: str = "완료"):
        # 처리 단계 로깅
        if not config.debug or not self.current_log_file:
            return
        
        step_info = {
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "status": status
        }
        
        # 기존 로그 파일 읽기 및 업데이트
        try:
            with open(self.current_log_file, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            
            log_data["processing_steps"].append(step_info)
            
            with open(self.current_log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
        except:
            pass  # 로그 업데이트 실패시 무시
    
    def log_final_result(self, success: bool, sql_query: str = None, error_message: str = None, 
                        processing_time: float = None, metadata: Dict = None):
        # 최종 결과 로깅
        if not config.debug or not self.current_log_file:
            return
        
        final_result = {
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "sql_query": sql_query,
            "error_message": error_message,
            "metadata": metadata or {}
        }
        
        # 기존 로그 파일 읽기 및 업데이트
        try:
            with open(self.current_log_file, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            
            log_data["final_result"] = final_result
            if processing_time:
                log_data["performance_metrics"]["total_processing_time"] = processing_time
            
            with open(self.current_log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 세션 로그 완료: {self.current_log_file}")
        except Exception as e:
            print(f"❌ 로그 저장 실패: {e}")
    
    def get_recent_logs(self, days: int = 7) -> list:
        # 최근 N일간의 로그 파일 목록 반환
        if not config.debug:
            return []
        
        from datetime import datetime, timedelta
        
        recent_logs = []
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            date_dir = self.log_dir / date_str
            
            if date_dir.exists():
                log_files = list(date_dir.glob("session_*.json"))
                for log_file in sorted(log_files):
                    recent_logs.append({
                        "date": date_str,
                        "file": log_file,
                        "size": log_file.stat().st_size
                    })
        
        return recent_logs
    
    def cleanup_old_logs(self, keep_days: int = 30):
        # 오래된 로그 파일 정리
        if not config.debug or not self.log_dir.exists():
            return
        
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        deleted_count = 0
        
        for date_dir in self.log_dir.iterdir():
            if date_dir.is_dir():
                try:
                    dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                    if dir_date < cutoff_date:
                        # 디렉토리 전체 삭제
                        import shutil
                        shutil.rmtree(date_dir)
                        deleted_count += 1
                except ValueError:
                    continue  # 날짜 형식이 아닌 디렉토리는 무시
        
        if deleted_count > 0:
            print(f"🗑️  {keep_days}일 이전 로그 정리: {deleted_count}개 디렉토리 삭제")

# 전역 디버그 로거 인스턴스
debug_logger = DebugLogger()