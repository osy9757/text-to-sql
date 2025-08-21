# 멀티에이전트 Text-to-SQL 시스템

한국어 자연어 질의를 MySQL SQL 쿼리로 변환하는 LangGraph 기반 멀티에이전트 시스템입니다.

## 🏗️ 시스템 아키텍처

### 4개 전문 에이전트

| 에이전트명 | 핵심 역할 | 주요 기능 |
|-----------|----------|----------|
| **Schema Analyst** | MySQL 스키마 분석 및 선별 | - MySQL 메타데이터 추출<br>- 질의 관련 테이블/컬럼 식별<br>- 외래키 관계 매핑 |
| **Query Planner** | SQL 실행 계획 수립 | - 복잡 질의 단계별 분해<br>- JOIN 전략 수립<br>- 서브쿼리 구조 설계 |
| **SQL Developer** | MySQL SQL 코드 생성 | - MySQL 문법 준수 SQL 생성<br>- 성능 최적화된 쿼리 작성<br>- 비개발자 친화적 결과 구조 |
| **Quality Validator** | 품질 검증 및 오류 수정 | - MySQL 구문 검증<br>- 실행 오류 분석 및 수정<br>- 결과 검증 및 최종 승인 |

### LangGraph 워크플로우
```
사용자 질의 → Schema Analyst → Query Planner → SQL Developer → Quality Validator → 최종 SQL
```

## 🚀 빠른 시작

### 1. 설치

```bash
pip install -r requirements.txt
```

### 2. API 키 설정

`private/.env.example`을 복사하여 `private/.env` 파일을 만들고 API 키를 설정하세요:

```bash
cp private/.env.example private/.env
```

#### OpenAI 사용 시:
```env
OPENAI_API_KEY=your_openai_api_key_here
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o
```

#### Claude 사용 시:
```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here  
MODEL_PROVIDER=anthropic
MODEL_NAME=claude-3-5-sonnet-20241022
```

### 3. 실행

#### 대화형 모드:
```bash
python main.py
```

#### 명령행 모드:
```bash
python main.py "사용자가 많이 거래한 통화는 무엇인가요?"
```

## 💡 사용 예시

### 대화형 모드
```
🤖 멀티에이전트 Text-to-SQL 시스템
==================================================
한국어 질의를 입력하시면 MySQL 쿼리로 변환해드립니다.

💬 질의: 최근 1개월 동안 가장 많이 거래된 통화 TOP 5를 보여주세요

🚀 처리 중...

✅ 변환 성공 (처리시간: 3.45초)

📝 생성된 SQL:
----------------------------------------
SELECT 
    cc.code AS 통화코드,
    COUNT(*) AS 거래횟수,
    SUM(oh.amount) AS 총거래금액
FROM tb_orderHistory oh
INNER JOIN tb_currencyCode cc ON oh.currencyCode1 = cc.code  
WHERE oh.orderedAt >= DATE_SUB(NOW(), INTERVAL 1 MONTH)
GROUP BY cc.code
ORDER BY 거래횟수 DESC
LIMIT 5;
----------------------------------------
```

### 프로그래밍 방식 사용
```python
import asyncio
from main import TextToSQLApp

async def example():
    app = TextToSQLApp()
    
    response = await app.convert(
        "쿠폰을 사용한 사용자들의 평균 거래 금액을 알려주세요",
        language="korean",
        include_explanation=True
    )
    
    if response.success:
        print("SQL:", response.sql_query)
        print("설명:", response.explanation)
    else:
        print("오류:", response.error_message)

asyncio.run(example())
```

## 🔧 설정 옵션

### 환경 변수

| 변수명 | 설명 | 기본값 |
|-------|------|--------|
| `MODEL_PROVIDER` | AI 모델 제공자 (`openai` 또는 `anthropic`) | `openai` |
| `MODEL_NAME` | 사용할 모델명 | `gpt-4o` |
| `TEMPERATURE` | 모델 생성 온도 | `0.1` |
| `MAX_TOKENS` | 최대 토큰 수 | `4000` |
| `DEBUG` | 디버그 모드 활성화 | `false` |

### 지원 모델

#### OpenAI:
- `gpt-4o`
- `gpt-4o-mini`
- `gpt-4-turbo`

#### Anthropic:
- `claude-3-5-sonnet-20241022`
- `claude-3-5-haiku-20241022`
- `claude-3-opus-20240229`

## 📊 시스템 특징

### 🎯 **정확성**
- 한국어-SQL 매핑을 위한 온톨로지 기반 스키마
- 4단계 검증 과정으로 오류 최소화
- MySQL 문법 완벽 준수

### ⚡ **성능**
- 인덱스 활용 최적화된 쿼리 생성
- JOIN 전략 자동 최적화
- 불필요한 테이블 자동 제외

### 🛡️ **안정성**
- 구문 오류 자동 수정
- 논리적 오류 탐지 및 경고
- 실행 가능한 SQL 보장

### 👥 **사용자 친화성**
- 한국어 컬럼 별칭 자동 생성
- 상세한 실행 설명 제공
- 직관적인 결과 구조

## 🗂️ 프로젝트 구조

```
text-to-sql/
├── agents/
│   ├── __init__.py
│   ├── base_agent.py           # 기본 에이전트 클래스
│   ├── schema_analyst.py       # 스키마 분석 에이전트
│   ├── query_planner.py        # 쿼리 계획 에이전트
│   ├── sql_developer.py        # SQL 개발 에이전트
│   └── quality_validator.py    # 품질 검증 에이전트
├── private/
│   └── schema_ontology.json    # 데이터베이스 스키마 온톨로지
├── config.py                   # 설정 관리
├── models.py                   # 데이터 모델 정의
├── orchestrator.py             # LangGraph 오케스트레이터
├── main.py                     # 메인 애플리케이션
├── requirements.txt            # 종속성
├── private/
│   ├── schema_ontology.json    # 데이터베이스 스키마 온톨로지
│   └── .env.example           # 환경변수 예시
└── README.md                  # 프로젝트 문서
```

## 🔍 디버그 모드

디버그 정보를 보려면 환경변수 또는 설정에서 `DEBUG=true`로 설정하세요:

```bash
DEBUG=true python main.py
```

디버그 모드에서는 다음 정보를 확인할 수 있습니다:
- 각 에이전트별 처리 과정
- LLM 호출 및 응답 로그  
- 에이전트 간 상태 전이
- 성능 메트릭

## ⚠️ 주의사항

1. **API 키 보안**: API 키를 코드에 직접 하드코딩하지 마세요.
2. **스키마 파일**: `private/schema_ontology.json` 파일이 반드시 존재해야 합니다.
3. **네트워크**: OpenAI/Anthropic API 호출을 위한 인터넷 연결이 필요합니다.
4. **토큰 한도**: 복잡한 쿼리는 더 많은 토큰을 소비할 수 있습니다.

## 🤝 기여하기

1. 이슈를 먼저 확인해주세요
2. 새로운 기능은 별도 브랜치에서 개발
3. 테스트 코드 포함 권장
4. 코드 스타일 일관성 유지

## 📜 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.