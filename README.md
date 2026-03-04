
# 🚀 Voice-Trader 2.0: AI 기반 실시간 지능형 주식 주문 시스템

본 프로젝트는 자연어 음성 명령을 분석하여 **한국투자증권(KIS) API**를 통해 실제 매매를 수행하고, **실시간 웹소켓(WebSocket)**으로 체결 결과를 즉시 피드백받는 금융 에이전트 시스템입니다. 

## 🛠️ 1. 시스템 아키텍처 (Detailed Data Flow)

정환님의 요청에 따라 설계된 **데이터 파이프라인 중심**의 아키텍처입니다.

```text
[ 정환님 음성 (Voice) ] -> [ RTZR STT (텍스트화) ]
           ↓
[ 3080 Server (Qwen-2.5-7B 의도 파악) ] -> [ Intent JSON 생성 ]
           ↓
[ Trade Manager (REST API) ] ↔ [ Cloud DB (PostgreSQL 로그) ]
           ↓ (주문 전송 및 감시 시작)
[ KIS API Server (WebSocket) ] 
           [cite_start]↓ (암호화된 데이터 수신: H0STCNI9) [cite: 60]
[cite_start][ AES256 Decryptor (데이터 복호화) ] -> [ Key/IV 활용 ] [cite: 60]
           ↓
[ 실시간 체결 알림 (Voice/Terminal UI) ]

```

## 🏗️ 2. 하이브리드 주문 처리 계층 (Hybrid Logic)

| 계층 | 기술 스택 | 역할 | 처리 속도 |
| --- | --- | --- | --- |
| **Level 1** | **Regex** | 정형화된 패턴 즉시 처리 | < 0.01s |
| **Level 2** | **Rapidfuzz** | 종목명 약어/오타 마스터 파일 대조 및 Ticker 확정 | < 0.1s |
| **Level 3** | **Fine-tuned LLM** | 비정형 문맥 파악 및 복잡한 의도 JSON 구조화 | ~1.0s |
| **Level 4** | **WS Listener** | 실시간 시세 및 체결 통보 감시 (H0STCNI9) 

 | Real-time |

## 📊 3. KIS API 연동 및 보안 명세

* 
**인증 파이프라인**: `appkey`와 `secretkey`를 사용하여 웹소켓 전용 `approval_key`를 발급받아 세션을 유지합니다. 


* 
**실시간 시세 (`H0STCNT0`)**: 종목코드(`tr_key`)를 기반으로 현재가 데이터를 수신합니다. 


* 
**실시간 체결통보 (`H0STCNI9`)**: 모의투자 환경에서 **HTS ID**를 `tr_key`로 사용하여 본인의 주문 상태(접수/체결)를 실시간 감시합니다. 


* 
**보안 복호화**: 수신된 암호화 데이터는 구독 성공 시 발급받은 **AES256 Key/IV**를 통해 복호화 프로세스를 거칩니다. 



## 📈 4. 학습 및 성능 지표

* **GPU**: RTX 3080 (VRAM 효율화를 위해 `paged_adamw_8bit` 적용)
* **Learning Rate**: 초기 $5 \times 10^{-8}$에서 **$2 \times 10^{-4}$**로 최적화하여 수렴 속도 개선
* **Loss Convergence**: Train Loss 3.0에서 **0.5 미만**으로 급격히 수렴 (약 60 Steps)
* **데이터 증강**: `kospi_code.mst`와 AI Hub 금융 데이터를 합성하여 도메인 지식 확장

## 🚀 5. 향후 로드맵 (Updated)

1. 
**AES256 Decryptor 구현**: 웹소켓으로 수신되는 실시간 체결 데이터의 완전한 복호화 모듈 연동 


2. **PostgreSQL 통합**: 모든 음성 명령과 체결 결과를 DB에 기록하여 매매 복기 시스템 구축
3. **Voice Feedback 고도화**: 체결 완료 시 TTS를 통해 "정환님, 삼성전자 1주 체결되었습니다" 알림 구현
4. **Multi-Target Mapping**: 우선주 및 거래 정지 종목에 대한 예외 처리 로직 강화
