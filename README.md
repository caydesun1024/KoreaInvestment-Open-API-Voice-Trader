# V-HTS 2.0 — Voice Hybrid Trading System

> 음성 명령 한 마디로 주식을 거래하는 AI 기반 금융 에이전트 프로토타입

---

## 목차

- [개요](#개요)
- [현재 구현 기능](#현재-구현-기능)
- [시스템 아키텍처](#시스템-아키텍처)
- [하이브리드 의도 분석 파이프라인](#하이브리드-의도-분석-파이프라인)
- [기술 스택](#기술-스택)
- [프로젝트 구조](#프로젝트-구조)
- [환경 변수 설정](#환경-변수-설정)
- [실행 방법](#실행-방법)
- [로드맵](#로드맵)

---

## 개요

**V-HTS 2.0**은 자연어 음성 명령을 분석하여 한국투자증권(KIS) Open API로 실제 매매를 수행하는 AI 트레이딩 에이전트입니다.

단순 명령어 기반이 아닌, **파인튜닝된 LLM(Qwen-2.5-7B)**을 활용하여 "SK하이닉스 좀 사줘", "삼성전자 지금 얼마야?" 같은 자연스러운 표현을 그대로 처리합니다.

---

## 현재 구현 기능

| 기능 | 상태 | 비고 |
|------|:----:|------|
| 음성 입력 (마이크 녹음) | ✅ | 웹 UI에서 직접 녹음 |
| STT 변환 | ✅ | RTZR VITO API |
| 텍스트 직접 입력 | ✅ | `/ask` 엔드포인트 |
| 종목명 퍼지 매칭 | ✅ | RapidFuzz, 2500+ 종목 |
| 의도 분석 (3단계 하이브리드) | ✅ | Regex → RapidFuzz → Qwen |
| 주가 조회 | ✅ | KIS REST API (모의/실전) |
| 시장가 매수 주문 | ✅ | KIS REST API |
| 웹 대시보드 UI | ✅ | FastAPI + Jinja2 |
| 매도 주문 | ❌ | 로드맵 |
| 체결 통보 (실시간) | ❌ | 로드맵 |
| 잔고 / 포트폴리오 조회 | ❌ | 로드맵 |
| TTS 피드백 | ❌ | 로드맵 |

---

## 시스템 아키텍처

```
[사용자 음성]
      │
      ▼
[RTZR VITO STT]  ◄─────────────────────────────┐
      │                                         │
      ▼                                   [웹 UI]
[3단계 의도 분석]  ◄── 텍스트 직접 입력도 가능 ──┘
      │
      ├── action: inquiry ──► [KIS REST API 시세 조회]
      │                              │
      └── action: buy ──────► [KIS REST API 매수 주문]
                                      │
                              [JSON 응답 → 웹 UI 표시]
```

### 인증 플로우

```
.env (appkey / secretkey)
      │
      ▼
[KIS OAuth 토큰 발급]  ──►  REST API 호출에 사용
      │
      ▼
[WebSocket approval_key 발급]  ──►  실시간 시세/체결 구독에 사용 (로드맵)
```

---

## 하이브리드 의도 분석 파이프라인

단순 LLM 호출이 아닌 **3단계 레이어**로 속도와 정확도를 동시에 확보합니다.

```
입력 텍스트: "SK하이닉스 지금 얼마야?"
      │
      ├─ [Level 1] Regex 패턴 매칭          < 0.01s
      │       패턴에 맞으면 즉시 반환
      │
      ├─ [Level 2] RapidFuzz 종목명 매칭    < 0.1s
      │       2500개 종목 대상 퍼지 매칭 (threshold=70)
      │       오타·약어 처리 ("삼전" → "삼성전자")
      │
      └─ [Level 3] Qwen-2.5-7B LoRA        ~ 1.0s
              복잡한 자연어, 복합 의도 처리
              Fine-tuning: LoRA r=16, checkpoint-300
              출력: {"action": "inquiry", "name": "SK하이닉스"}
```

---

## 기술 스택

| 분야 | 기술 |
|------|------|
| **Backend** | Python 3.13, FastAPI, asyncio |
| **AI 모델** | Qwen-2.5-7B-Instruct + LoRA (PEFT) |
| **모델 최적화** | BitsAndBytes 4-bit 양자화, bfloat16 |
| **STT** | RTZR VITO API |
| **증권 API** | 한국투자증권(KIS) Open API |
| **종목 매칭** | RapidFuzz |
| **GPU** | NVIDIA RTX 3080 |
| **프론트엔드** | HTML/CSS, Jinja2 템플릿 |

---

## 프로젝트 구조

```
voice-trader/
├── main.py                          # FastAPI 서버 진입점
├── mock-buy-test.py                 # WebSocket 체결통보 테스트
├── pyproject.toml
├── .env                             # API 키 (gitignore)
│
├── src/
│   ├── api/
│   │   ├── kis_auth.py              # KIS 인증 + WebSocket 클라이언트
│   │   ├── vito_stt.py              # RTZR VITO STT
│   │   └── domestic_stock_functions.py  # KIS REST API 함수 모음
│   ├── ai/
│   │   └── analyzer.py             # Qwen 추론, 의도 분석
│   ├── services/
│   │   └── trading_service.py      # 3단계 파이프라인 오케스트레이션
│   └── utils/
│       └── mapper.py               # 종목명 → 코드 매핑 (RapidFuzz)
│
├── qwen2.5-7b-fine-tuning/
│   ├── main.py                      # 학습 오케스트레이션
│   ├── config.py                    # LoRA r=16, lr=2e-4, epoch=3
│   ├── model.py                     # 4-bit 양자화 + LoRA 적용
│   ├── trainer.py                   # 커스텀 콜백 (샘플 예측 출력)
│   ├── inference.py                 # 검증 데이터 평가
│   ├── data.py                      # 데이터 로드 및 분할 (80/20)
│   └── Qwen_singleGPU-v1/
│       └── checkpoint-300/          # 최종 사용 체크포인트
│
├── stock_info/
│   └── stock_list.csv               # 2500+ 종목 코드+이름
├── static/
│   └── style.css
└── templates/
    └── index.html
```

---

## 환경 변수 설정

`.env` 파일을 프로젝트 루트에 생성하세요.

```env
# KIS 모의투자
KIS_MOCK_APP_KEY=your_mock_app_key
KIS_MOCK_APP_SECRET=your_mock_app_secret
KIS_MOCK_ACCOUNT=your_account_number

# KIS 실전투자 (선택)
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret

# 공통
KIS_HTS_ID=your_hts_id_12digits

# RTZR VITO STT
RZ_CLIENT_ID=your_client_id
RZ_CLIENT_SECRET=your_client_secret
```

---

## 실행 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
# 또는
uv sync
```

### 2. 서버 실행

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

> **주의**: 서버 시작 시 Qwen 모델 로딩(~30초)과 KIS 토큰 발급이 자동으로 진행됩니다.

### 3. 웹 UI 접속

```
http://localhost:8000
```

마이크 버튼으로 음성 입력하거나, 텍스트를 직접 입력할 수 있습니다.

---

## 로드맵

### Phase 1 — 트레이딩 기능 완성

- [ ] 매도 주문 ("삼성전자 10주 팔아")
- [ ] 지정가 주문 ("삼성전자 60000원에 10주 사줘")
- [ ] 잔고 및 보유 종목 조회 ("내 잔고 얼마야")
- [ ] 체결통보 WebSocket 연동 (H0STCNI9 → 실시간 피드백)

### Phase 2 — 안전성 및 사용성

- [ ] TTS 체결 피드백 ("삼성전자 10주 매수 완료")
- [ ] 주문 전 확인 단계 ("정말 살까요?" → "응")
- [ ] 리스크 게이트 (1회 최대 주문액, 일일 손실 한도)
- [ ] PostgreSQL 거래 로그 (명령 → 체결 전 과정 기록)

### Phase 3 — 아키텍처 고도화

- [ ] Qwen 추론 서버 분리 (API 서버 startup 블록 해소)
- [ ] Redis Pub/Sub 이벤트 버스 도입
- [ ] 실시간 시세 스트리밍 대시보드 (H0STCNT0)
- [ ] MSA 전환 및 Docker Compose 컨테이너화
