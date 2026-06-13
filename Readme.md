# 상황 기반 음악 추천 엔진

> 지금 내가 어디서, 무엇을 하고, 얼마나 시끄러운 환경인지 알려주면 AI가 딱 맞는 음악 10곡을 추천해줍니다.

---

## 프로젝트 소개

이 프로젝트는 **상황(Context) 기반 음악 추천 API**입니다.

기존 추천 시스템은 "당신이 평소에 좋아하는 음악"을 추천합니다.  
이 엔진은 **"지금 이 순간에 맞는 음악"** 을 추천합니다.

도서관에서 집중하는 중인지, 헬스장에서 운동 중인지, 지하철 안에서 기분 전환이 필요한지—  
같은 아티스트를 좋아하더라도 상황에 따라 완전히 다른 곡이 필요합니다.

LangGraph와 OpenAI, Spotify API를 결합해 9단계 AI 파이프라인으로 음악을 선별합니다.

---

## 해결하려는 문제

### 기존 음악 추천의 한계

| 기존 방식 | 한계 |
|-----------|------|
| 청취 이력 기반 | "지금 상황"을 모름 |
| 장르/아티스트 기반 | 에너지 레벨이 상황과 안 맞을 수 있음 |
| 플레이리스트 | 내 선호 아티스트가 없을 수도 있음 |

### LLM 기반 접근의 이유

- 규칙 기반으로는 표현하기 어려운 **맥락적 판단** 처리 (예: "metal을 좋아하는데 조용한 도서관 → 차분한 인스트루멘탈 제안")
- 소음도·목표·위치를 **우선순위에 따라 가중 조합**하는 복잡한 규칙을 자연어 프롬프트로 처리
- 상황에 어울리는 장르를 **창의적으로 타협**하는 능력

---

## 핵심 아이디어

```
사용자 입력
  소음도 (시끄러운 정도)  ← 1순위
  목표 (집중/운동/수면...)  ← 2순위
  위치 (도서관/헬스장/카페...)  ← 3순위
  선호 아티스트
  선호 장르
         │
         ▼
  상황 매트릭스 (config)
  + Prompt Engineering
         │
         ▼
    OpenAI LLM
  (장르 추천 & 타협)
         │
         ▼
  Spotify 검색
  (병렬 8개 쿼리)
         │
         ▼
  품질 검증 & 필터링
  (코드 + LLM 이중 검증)
         │
         ▼
  음악 10곡 추천
  (이유 포함)
```

**핵심 원칙**: 사용자가 원하는 장르와 상황에 맞는 장르가 충돌할 때, AI가 자동으로 타협점을 찾습니다.

---

## 주요 기능

- **상황 우선순위 분석**: 소음도 → 목표 → 위치 순서로 최적 장르 결정
- **선호 아티스트 20% 보장**: 추천 10곡 중 2곡은 반드시 선호 아티스트 곡
- **한국 음악 50% 포함**: 한국 사용자 경험을 위해 10곡 중 5곡은 한국 노래
- **스팸 트랙 자동 제거**: "집중 잘 되는 로파이 1시간" 같은 컬렉션성 트랙 필터링
- **품질 검증 자동 재시도**: 기준 미달 시 쿼리 전략 바꿔 최대 3회 재검색
- **인기도 균형 분포**: 메가히트(40%) + 중간(40%) + 숨겨진 명곡(20%)
- **추천 이유 생성**: 각 곡이 왜 지금 상황에 어울리는지 설명

---

## 시스템 구조

```
┌─────────────────────────────────────────────────────┐
│                   FastAPI 서버                       │
│  POST /recommend  │  GET /contexts  │  GET /genres  │
└────────────────────────────┬────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   LangGraph     │
                    │   워크플로우    │
                    └────────┬────────┘
           ┌─────────────────┼─────────────────┐
           │                 │                 │
    ┌──────▼──────┐  ┌───────▼──────┐  ┌──────▼──────┐
    │  OpenAI     │  │  Spotify     │  │  Config     │
    │  gpt-4.1-mini│  │  Web API    │  │  매트릭스   │
    └─────────────┘  └─────────────┘  └─────────────┘
```

---

## 추천 과정

**1. 선호 분석** — 좋아하는 아티스트들의 공통 음악 특성 파악 (LLM)

**2. 상황 분석** — 소음도·목표·위치 매트릭스를 읽어 최적 장르 5개 결정 (매트릭스 + LLM)

**3. 검색 쿼리 생성** — Spotify 필터 문법(`genre:lo-fi year:2023-2025`)으로 정밀 쿼리 8개 생성 (LLM)

**4. 병렬 검색** — 8개 쿼리 동시 실행 → 후보 최대 50곡 수집 + 선호 아티스트 트랙 별도 수집

**5. 선택 & 필터링** — 스팸 제목 제거 → LLM이 비율 맞춰 10곡 선택 → 리믹스/라이브 필터

**6. 품질 검증** — 코드(한국곡/신곡/인기도) + LLM(다양성/비율) 이중 검증 → 실패 시 재시도

**7. 추천 이유 생성** — 각 곡별 상황 맞춤 설명 생성 (LLM)

---

## 프로젝트 구조

```
music-recommendation-engine/
├── server.py           # FastAPI 서버 (진입점)
├── graph.py            # LangGraph 워크플로우 정의
├── nodes.py            # 9개 노드 실행 로직
├── prompts.py          # LLM 프롬프트 템플릿 6종
├── models.py           # 데이터 모델 (Pydantic + TypedDict)
├── config.py           # 상황 매트릭스 & 설정 상수
├── spotify_client.py   # Spotify API 클라이언트
├── requirements.txt    # 의존성
└── test_client.py      # 대화형 테스트 CLI
```

---

## 사용 기술

| 기술 | 용도 |
|------|------|
| Python 3.13 | 언어 |
| FastAPI | REST API 서버 |
| LangGraph 0.2 | 멀티노드 AI 워크플로우 |
| LangChain 0.3 | LLM 연동 |
| OpenAI gpt-4.1-mini | 장르 추천, 트랙 선택, 이유 생성 |
| Spotipy 2.24 | Spotify Web API 클라이언트 |
| Pydantic v2 | 데이터 검증 & LLM 구조화 출력 |
| ThreadPoolExecutor | Spotify 병렬 검색 |
| python-dotenv | 환경 변수 관리 |

---

## 실행 방법

### 1. 사전 준비

- OpenAI API Key
- Spotify Developer 계정의 Client ID / Client Secret ([dashboard.spotify.com](https://developer.spotify.com/dashboard))

### 2. 설치 및 실행

```bash
# 저장소 클론 후 엔진 폴더로 이동
cd music-recommendation-engine

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cat > .env << EOF
OPENAI_API_KEY=sk-your-key-here
SPOTIFY_CLIENT_ID=your-spotify-client-id
SPOTIFY_CLIENT_SECRET=your-spotify-client-secret
EOF

# 서버 실행
python server.py
```

서버가 실행되면:
- API 서버: `http://localhost:8000`
- Swagger 문서: `http://localhost:8000/docs`

### 3. 추천 요청

```bash
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "location": "library",
    "goal": "focus",
    "decibel": "quiet",
    "preferred_artists": ["BTS", "IU"],
    "preferred_genres": ["k-pop", "indie"]
  }'
```

### 4. 대화형 테스트 (별도 터미널)

```bash
python test_client.py
```

---

## 입력 / 출력 예시

### 입력

```json
{
  "location": "library",
  "goal": "focus",
  "decibel": "quiet",
  "preferred_artists": ["BTS", "Stray Kids"],
  "preferred_genres": ["k-pop", "hip-hop"]
}
```

**입력 옵션**

| 파라미터 | 선택지 |
|----------|--------|
| location | `home` `gym` `co-working` `library` `cafe` `moving` `park` |
| goal | `focus` `relax` `active` `sleep` `anger` `consolation` `stabilization` `neutral` |
| decibel | `quiet` `moderate` `loud` |

### 출력

```json
{
  "recommendations": [
    {
      "track_name": "Still With You",
      "artists": "BTS",
      "album_name": "...",
      "release_date": "2020-06-04",
      "spotify_url": "https://open.spotify.com/track/...",
      "reason": "⭐ 선호 아티스트 | 조용한 도서관 환경에서 집중을 방해하지 않는 잔잔한 피아노 선율이 특징입니다..."
    },
    ...
  ],
  "context_summary": "🔊 소음: quiet | 🎯 목표: focus | 📍 위치: library",
  "ai_recommended_genres": ["lo-fi hip hop", "chill", "ambient", "k-indie", "instrumental"],
  "iteration_count": 1,
  "quality_scores": {
    "diversity_score": 0.9,
    "preferred_artist_ratio": 0.2,
    "korean_tracks_count": 5,
    "recent_tracks_count": 3,
    "is_valid": true,
    "popularity_distribution": {"high": 4, "medium": 4, "low": 2}
  }
}
```

**AI 타협 예시 (예외 상황)**

| 입력 | AI 판단 | 결과 |
|------|---------|------|
| 도서관 + 집중 + metal 선호 | quiet 1순위 → metal 에너지와 충돌 | lo-fi, ambient로 대체 |
| 이동 중 + loud + classical 선호 | loud 환경 → 볼륨 있는 곡 필요 | orchestral, cinematic으로 조정 |
| 수면 + EDM 선호 | sleep 목표 → 자극적 음악 부적합 | acoustic, ambient로 대체 |

---

## 구현 포인트

### 1. LangGraph 상태 기계

9개 노드가 `AgentState` TypedDict 하나를 공유하며 순차 실행. 품질 실패 시 3번 노드로 돌아가는 조건부 엣지로 재시도 루프 구현.

### 2. 구조화된 LLM 출력 (Structured Output)

모든 LLM 호출에 `llm.with_structured_output(Pydantic 모델)` 사용. JSON 파싱 오류 없이 타입-세이프한 객체 반환.

### 3. 우선순위 매트릭스

`DECIBEL_MUSIC_PROFILES` / `GOAL_MUSIC_PROFILES` / `LOCATION_MODIFIERS` 세 딕셔너리를 config.py에 정의. 텍스트로 직렬화해 프롬프트에 삽입 → 규칙 기반 + LLM 하이브리드 판단.

### 4. Spotify 쿼리 엔지니어링

`genre:lo-fi year:2023-2025` 형태의 필터 문법 강제로 스팸 트랙 사전 차단. 8개 쿼리 중 5개는 AI 추천 장르, 3개는 한국 음악 고정 비율.

### 5. 이중 품질 검증

코드가 한국곡 수·신곡 수·인기도 분포를 수치 계산, LLM이 다양성·선호 비율 판단. 각자 잘하는 영역을 나눠 담당하고 코드가 일부 LLM 결과를 override.

### 6. 피드백 기반 적응적 재검색

품질 실패 원인(`validation_feedback`)을 재시도 프롬프트에 전달. "한국곡 3/5 부족" → 다음 쿼리에 `genre:k-pop` 비중 자동 증가.

---

## 프로젝트 회고

**배운 점:**

- LangGraph의 상태 기계 구조가 멀티스텝 AI 파이프라인에 매우 적합함. 각 노드를 독립적으로 테스트하고 조건부 엣지로 재시도 로직을 구현하는 방식이 단순 함수 체인보다 명확함.

- LLM에게 모든 것을 맡기지 않고 코드로 처리할 수 있는 부분(수치 계산, 키워드 필터)은 코드로, 맥락적 판단은 LLM으로 역할을 명확히 나누는 것이 품질과 신뢰성 모두에 중요함.

- Spotify Search API의 필터 문법을 LLM이 올바르게 사용하도록 프롬프트에서 허용/금지 필드를 명시적으로 구분하는 쿼리 엔지니어링이 결과 품질에 큰 영향을 미침.
