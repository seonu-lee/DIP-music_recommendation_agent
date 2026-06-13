# 음악 추천 엔진 개발 문서 (summary.md)

---

## 프로젝트 한 줄 설명

사용자의 현재 상황(소음도·목표·위치)과 선호 아티스트를 입력받아 LangGraph 멀티노드 파이프라인으로 Spotify 트랙 10곡을 추천하는 상황 기반 음악 추천 API 서버.

---

## 전체 아키텍처

```
Client (HTTP POST /recommend)
        │
        ▼
server.py  ──── 입력 검증 (location / goal / decibel 열거형 체크)
        │
        ▼
graph.py :: run_recommendation()
        │         초기 AgentState 생성
        │
        ▼
LangGraph StateGraph (9개 노드 순환 포함)
        │
        ├─[1] analyze_preference  ─── OpenAI (gpt-4.1-mini) ─► ArtistPersona
        │
        ├─[2] context_analysis    ─── config 매트릭스 + OpenAI ─► AI 추천 장르 5개
        │
        ├─[3] search_query_generator ─ OpenAI ─► Spotify 검색 쿼리 8개
        │                             (재시도 시 FEEDBACK_SEARCH_PROMPT)
        │
        ├─[4] tools  ─────────────── SpotifyClient.parallel_search()
        │                            (ThreadPoolExecutor, 5 workers)
        │
        ├─[5] preference_search  ─── SpotifyClient (선호 아티스트 최신+인기 트랙)
        │
        ├─[6] selection  ─────────── 스팸 필터 + OpenAI → 10곡 선택
        │
        ├─[7] remix_track_filter ─── 키워드 기반 코드 필터 (remix/live 등)
        │
        ├─[8] quality_validator  ─── 코드 수동 계산 + OpenAI 검증
        │       │                    (한국곡/신곡/인기도/다양성)
        │       ├─ 통과 ─────────────────────────────────────────────┐
        │       └─ 실패 (< MAX_ITERATIONS=3) → [3] 재검색           │
        │                                                             │
        └─[9] generate_reason  ◄──────────────────────────────────────┘
                  │
                  ▼
        AgentState["final_tracks"] + ["recommendations"]
                  │
                  ▼
server.py  ──── RecommendationResponse 조립 & HTTP 200 응답
```

---

## 전체 실행 흐름

### 1단계: HTTP 진입 (server.py)

```
POST /recommend
  → request: RecommendationRequest 역직렬화
  → location / goal / decibel 열거형 검증 (LOCATIONS, GOALS, DECIBEL_LEVELS)
  → preferred_artists 최소 1개 검증
  → run_recommendation(location, goal, decibel, preferred_artists, preferred_genres) 호출
```

### 2단계: LangGraph 초기화 (graph.py)

```
run_recommendation()
  → initial_state: AgentState(TypedDict) 생성 (모든 필드 None / 빈 리스트)
  → create_recommendation_graph() 호출
      → StateGraph(AgentState) 생성
      → 9개 노드 add_node
      → 엣지/조건부엣지 add_edge
      → workflow.compile() → LangGraph app 객체
  → app.invoke(initial_state) 실행 (동기 블로킹)
```

### 3단계: 노드 순차 실행 (nodes.py)

**[Node 1] analyze_preference**
- 입력: `state["preferred_artists"]`, `state["preferred_genres"]`
- ANALYZE_PREFERENCE_PROMPT 포맷 → LLM 호출 (structured_output=ArtistPersona)
- 출력: `state["artist_persona"]` = ArtistPersona(dominant_genres, music_characteristics, similar_artists, summary)

**[Node 2] context_analysis**
- config에서 DECIBEL_MUSIC_PROFILES[decibel], GOAL_MUSIC_PROFILES[goal], LOCATION_MODIFIERS[location] 읽기
- 세 프로필을 텍스트로 변환 → CONTEXT_ANALYSIS_PROMPT 포맷
- LLM 호출 (structured_output=AIGenreRecommendation)
- 출력: `state["ai_recommended_genres"]` (5개), `state["ai_genre_reasoning"]`

**[Node 3] search_query_generator**
- `state.get("validation_feedback")` 유무로 프롬프트 분기:
  - 없음(첫 실행): SEARCH_QUERY_PROMPT (8개 쿼리, genre+year 필터 혼용)
  - 있음(재시도): FEEDBACK_SEARCH_PROMPT (피드백 반영, 한국곡/신곡 강화)
- LLM 호출 (structured_output=ContextSearchQueries)
- 출력: `state["search_queries"]` = List[SearchQuery]

**[Node 4] tools**
- `search_queries`에서 쿼리 문자열 추출
- `SpotifyClient.parallel_search(queries, limit_per_query=10)` 호출
  - ThreadPoolExecutor(max_workers=5)로 search_tracks 병렬 실행
  - 중복 track.id 제거
  - 최대 CANDIDATE_TRACKS_COUNT=50개 반환
- 출력: `state["candidate_tracks"]`

**[Node 5] preference_search**
- preferred_artists 최대 5명에 대해:
  - `get_artist_recent_tracks(artist, months=48)` → 최신 앨범 트랙 최대 3개
  - `search_artist_tracks(artist, limit=3)` → 인기 트랙 3개
- track.id 기준 중복 제거
- 출력: `state["preference_tracks"]`

**[Node 6] selection**
- candidate_tracks + preference_tracks 각각 스팸 필터링 (is_spam_title)
- SELECTION_PROMPT 포맷 (필수비율 명시: 선호2곡, 한국5곡, 신곡2곡, 인기도분포)
- LLM 호출 (structured_output=FinalSelection) → 10개 track_id 반환
- track_id로 track 객체 조회 → `state["selected_tracks"]`

**[Node 7] remix_track_filter**
- filter_keywords = ["remix", "live", "acoustic", "unplugged", ...] 등 10개
- track.name.lower() 기준 키워드 포함 시 제거
- 10곡 미만 시 제거된 트랙에서 복구 (완화 기준)
- 출력: `state["selected_tracks"]` (최대 10개)

**[Node 8] quality_validator**
- **코드 수동 계산** (선신뢰):
  - unique_artists → diversity_score
  - preferred_count → preferred_ratio
  - is_korean_track() → korean_count
  - release_date 파싱 → recent_count
  - get_popularity_level() → popularity_dist
- **LLM 검증**: QUALITY_VALIDATOR_PROMPT → QualityValidation (structured_output)
- **코드가 LLM 결과를 덮어씀**: `validation.korean_tracks_count = korean_count`, `validation.popularity_distribution = PopularityDistribution(...)`
- **최종 통과 조건**: `validation.is_valid AND korean_count >= 4 AND recent_count >= 2`
- 통과 시: `state["final_tracks"] = selected_tracks`, `state["validation_feedback"] = None`
- 실패 시: `state["validation_feedback"] = feedback`, iteration_count 증가
- iteration_count >= MAX_ITERATIONS(3) 시: 강제 통과 처리

**[should_continue] 조건부 엣지**
- `validation.is_valid == True` → "continue" (generate_reason)
- `iteration_count >= MAX_ITERATIONS` → "continue"
- `state["validation_feedback"]` 존재 → "retry" (search_query_generator)
- 기본 → "continue"

> **주의**: `should_continue`는 `validation.is_valid`(LLM 판정)를 체크하지만, `final_tracks` 설정은 코드의 combined `is_valid`를 사용함. LLM이 valid 판정 + 코드가 invalid 판정 시 `final_tracks`가 빈 채로 generate_reason에 진입할 수 있음.

**[Node 9] generate_reason**
- GENERATE_REASON_PROMPT 포맷 (decibel/goal/location/ai_genres/artist_persona/tracks)
- LLM 호출 (structured_output=FinalRecommendations) → track_id별 reason
- 출력: `state["recommendations"]`

### 4단계: 응답 조립 (server.py)

```
final_state["final_tracks"] 순회
  → 각 track에서 is_preferred (preferred_artists 집합 교차) 판정
  → recommendations에서 track_id 매칭 → reason 추출
  → is_preferred 시 reason 앞에 "⭐ 선호 아티스트 | " 접두사 추가
  → TrackRecommendation 생성

QualityValidation → quality_scores dict 변환
  (PopularityDistribution 객체를 dict로 직렬화)

RecommendationResponse 반환
```

---

## 폴더 구조

```
music-recommendation-engine/
├── server.py           # FastAPI 앱 + HTTP 엔드포인트 (진입점)
├── graph.py            # LangGraph 워크플로우 정의 + run_recommendation()
├── nodes.py            # LangGraph 9개 노드 + 유틸리티 함수
├── prompts.py          # LLM 프롬프트 템플릿 6개 + format_tracks_for_prompt()
├── models.py           # Pydantic 데이터 모델 + TypedDict AgentState
├── config.py           # 상수/임계값/매트릭스 정의 + validate_config()
├── spotify_client.py   # SpotifyClient 클래스 + 싱글톤
├── requirements.txt    # 의존성 목록
└── test_client.py      # 대화형 CLI 테스트 클라이언트
```

### 각 파일 존재 이유

| 파일 | 역할 | 왜 분리했는가 |
|------|------|--------------|
| server.py | HTTP 진입점, 입력검증, 응답조립 | FastAPI 레이어와 비즈니스 로직 분리 |
| graph.py | LangGraph 워크플로우 구조 정의 | 노드 연결 관계만 담당, 로직과 분리 |
| nodes.py | 각 노드의 실제 실행 로직 | 노드별 독립 테스트 가능 |
| prompts.py | 프롬프트 문자열 외부화 | 코드 변경 없이 프롬프트 튜닝 가능 |
| models.py | 타입 정의, API 스키마 | 데이터 계약 단일 정의 위치 |
| config.py | 모든 상수/임계값 중앙화 | 수치 변경 시 한 곳만 수정 |
| spotify_client.py | Spotify API 추상화 | API 변경 시 이 파일만 수정 |
| test_client.py | E2E 수동 테스트 | 서버 실행 중 시나리오 검증용 |

---

## 핵심 클래스

### `SpotifyClient` (spotify_client.py)

| 항목 | 내용 |
|------|------|
| 역할 | Spotify Web API 호출 래퍼 |
| 초기화 | SpotifyClientCredentials(client_id, client_secret) → spotipy.Spotify |
| 주요 메서드 | search_tracks, search_artist_tracks, get_artist_recent_tracks, parallel_search, _parse_track |
| 사용 위치 | nodes.py tools(), preference_search() |
| 특이사항 | 모듈 레벨 `_spotify_client` 싱글톤, `get_spotify_client()` 팩토리 |

### `AgentState` (models.py)

| 항목 | 내용 |
|------|------|
| 역할 | LangGraph 노드 간 공유 상태 |
| 타입 | TypedDict (Pydantic 아님) |
| 주요 필드 | location/goal/decibel, artist_persona, ai_recommended_genres, candidate_tracks(50개), preference_tracks, selected_tracks, final_tracks(10개), recommendations, iteration_count, validation_feedback |
| 사용 위치 | 모든 노드 함수의 입력/출력 |

### `AIGenreRecommendation` (nodes.py)

| 항목 | 내용 |
|------|------|
| 역할 | context_analysis 노드의 LLM 구조화 출력 |
| 필드 | ai_recommended_genres(List[str], 5개), reasoning(str) |
| 특이사항 | nodes.py 내부에 정의 (models.py 아님) - 해당 노드 전용 |

### `QualityValidation` (models.py)

| 항목 | 내용 |
|------|------|
| 역할 | 품질 검증 결과 저장 |
| 필드 | is_valid, diversity_score, preferred_artist_ratio, recent_tracks_count, korean_tracks_count, popularity_distribution(PopularityDistribution), feedback |
| 특이사항 | LLM이 생성하지만 코드가 korean_tracks_count, popularity_distribution 덮어씀 |

---

## 핵심 함수

### `analyze_preference(state)` — nodes.py:119

- **역할**: 선호 아티스트/장르 → 음악 취향 페르소나 생성
- **입력**: state["preferred_artists"], state["preferred_genres"]
- **반환값**: state (state["artist_persona"] 업데이트)
- **호출위치**: LangGraph 노드 1 (진입점)
- **중요 로직**: `llm.with_structured_output(ArtistPersona)` — Pydantic 스키마로 LLM 출력 강제 파싱

### `context_analysis(state)` — nodes.py:145

- **역할**: 소음/목표/위치 우선순위 매트릭스를 읽어 AI 추천 장르 5개 생성
- **입력**: state["decibel"], state["goal"], state["location"], state["artist_persona"]
- **반환값**: state (ai_recommended_genres, ai_genre_reasoning 업데이트)
- **호출위치**: LangGraph 노드 2
- **중요 로직**: config.py의 세 매트릭스(DECIBEL_MUSIC_PROFILES, GOAL_MUSIC_PROFILES, LOCATION_MODIFIERS)를 텍스트로 변환해 프롬프트에 삽입

### `search_query_generator(state)` — nodes.py:219

- **역할**: Spotify Search API용 쿼리 8개 생성 (재시도 시 다른 프롬프트)
- **입력**: state["ai_recommended_genres"], state["validation_feedback"] (있으면 재시도)
- **반환값**: state["search_queries"]
- **호출위치**: LangGraph 노드 3 (품질 실패 시 재진입)
- **중요 로직**: `validation_feedback` 존재 여부로 초기/재시도 프롬프트 분기

### `parallel_search(queries, limit_per_query)` — spotify_client.py:178

- **역할**: 여러 Spotify 쿼리를 동시 실행해 중복 없는 후보 트랙 반환
- **입력**: List[str] 쿼리, limit_per_query=10
- **반환값**: List[SpotifyTrack] (최대 CANDIDATE_TRACKS_COUNT=50)
- **호출위치**: tools() 노드
- **중요 로직**: `ThreadPoolExecutor(max_workers=5)` + `as_completed()`, seen_ids set으로 중복 제거

### `is_spam_title(title)` — nodes.py:60

- **역할**: SEO 목적 컬렉션/플레이리스트 트랙 제목 필터링
- **입력**: track.name (str)
- **반환값**: bool
- **호출위치**: selection() 전처리, selection 프롬프트 필터 보조
- **중요 로직**: SPAM_KEYWORDS 대소문자 무시 포함 체크 + 정규식 `r'\d+\s*(시간|분|hour|min)'` 패턴 매칭

### `is_korean_track(track)` — nodes.py:76

- **역할**: 한국 노래 여부 3단계 판별
- **입력**: SpotifyTrack
- **반환값**: bool
- **중요 로직**:
  1. `re.search(r'[가-힣]', track.name)` — 제목에 한글 포함
  2. 아티스트 이름에 KOREAN_INDICATORS 키워드 포함 (BTS, IU 등)
  3. 아티스트 genres 필드에 'k-pop', 'k-indie', 'korean' 포함
  > **주의**: `_parse_track`에서 `SpotifyArtist.genres=[]`로 초기화하므로 3번 조건은 실제로 동작 안 함

### `quality_validator(state)` — nodes.py:421

- **역할**: 추천 결과 품질 수치 계산 + LLM 교차검증
- **입력**: state["selected_tracks"], state["preferred_artists"]
- **반환값**: state (quality_validation, final_tracks, validation_feedback, iteration_count 업데이트)
- **중요 로직**:
  - 코드 수동 계산 후 LLM 검증 → 코드가 일부 LLM 결과 덮어씀
  - `is_valid = validation.is_valid AND korean_count >= 4 AND recent_count >= 2`
  - `state["final_tracks"]`는 `is_valid` 시에만 설정 (should_continue는 `validation.is_valid` 체크 — 불일치 가능)

### `should_continue(state)` — nodes.py:566

- **역할**: 품질 검증 결과에 따라 다음 노드 결정 (LangGraph 조건부 엣지)
- **입력**: state
- **반환값**: "continue" 또는 "retry"
- **중요 로직**: `validation.is_valid` (LLM 판정) 기준 — 코드의 combined is_valid와 다를 수 있음

### `_parse_track(track_data)` — spotify_client.py:212

- **역할**: Spotify API dict → SpotifyTrack Pydantic 모델 변환
- **입력**: Spotify API 응답 dict
- **반환값**: SpotifyTrack | None
- **중요 로직**: SpotifyArtist 생성 시 genres=[] 고정 → is_korean_track의 장르 기반 판별 비활성화 (실질적 버그)

---

## 추천 프로세스

```
① 사용자 입력
   location="library", goal="focus", decibel="quiet"
   preferred_artists=["BTS", "Stray Kids"]
   preferred_genres=["k-pop"]
   
② 선호 아티스트 분석 (LLM)
   → ArtistPersona: dominant_genres=["k-pop", "hip-hop"], similar_artists=[...]
   
③ 상황 분석 (매트릭스 + LLM)
   DECIBEL_MUSIC_PROFILES["quiet"] → energy_range=(0.1,0.4), tempo 60-100 BPM
   GOAL_MUSIC_PROFILES["focus"] → suggested_genres=["lo-fi", "ambient", ...]
   LOCATION_MODIFIERS["library"] → adjust_energy=-0.2
   → LLM: ai_recommended_genres=["lo-fi hip hop", "chill", "ambient", "instrumental", "k-indie"]
     reasoning: "k-pop은 너무 활기차므로 조용한 환경에 맞는 lo-fi로 타협..."
   
④ 검색 쿼리 생성 (LLM)
   → 8개 쿼리:
     "q=genre:lo-fi year:2023-2025"
     "q=genre:ambient year:2021-2025"
     "q=genre:k-pop artist:BTS year:2021-2025"
     "q=artist:Stray Kids genre:k-pop year:2022-2025"
     ... (5개 AI장르 기반 + 3개 한국 음악)
   
⑤ Spotify 병렬 검색 (코드)
   → 8개 쿼리 동시 실행 (ThreadPoolExecutor, 5 workers)
   → 중복 제거 후 최대 50개 candidate_tracks
   
⑥ 선호 아티스트 직접 검색 (코드)
   → BTS: 최신 앨범 트랙 3개 + 인기 트랙 3개
   → Stray Kids: 최신 앨범 트랙 3개 + 인기 트랙 3개
   → 중복 제거 → preference_tracks
   
⑦ 10곡 선택 (스팸 필터 + LLM)
   - "집중 잘 되는 로파이 1시간" 같은 스팸 제목 제거
   - LLM이 필수 비율 맞춰 10곡 선택:
     선호아티스트 2곡 + 한국곡 5곡 + 인기도 분포(4/4/2) + 신곡 2곡
   
⑧ 리믹스 필터 (코드)
   - "BTS - Dynamite (Remix)" → 제거 (10곡 유지 위해 복구 가능)
   
⑨ 품질 검증 (코드 + LLM)
   - 코드: korean_count=5 OK, recent_count=3 OK
   - LLM: is_valid=True, diversity_score=0.9
   - 통과 → final_tracks 확정
   
⑩ 추천 이유 생성 (LLM)
   → 각 트랙별 2-3문장 한국어 설명
   → "도서관의 조용한 환경에서 집중력을 방해하지 않는 lo-fi 비트..."
   
⑪ 응답 조립 (코드)
   → RecommendationResponse (10개 TrackRecommendation + quality_scores + ai_genres)
```

---

## Prompt Engineering

### 1. ANALYZE_PREFERENCE_PROMPT

- **목적**: 선호 아티스트/장르 → 음악 취향 객관화
- **설계 이유**: 이후 노드들이 사용자 취향의 "요약"을 사용하도록 페르소나 중간 표현 생성
- **Context 삽입**: preferred_artists (쉼표 연결), preferred_genres
- **출력 형식**: ArtistPersona (dominant_genres 3개, music_characteristics, similar_artists, summary)

### 2. CONTEXT_ANALYSIS_PROMPT

- **목적**: 상황 우선순위(소음>목표>위치) + 사용자 취향 타협 → AI 추천 장르 5개
- **설계 이유**: 사용자가 "metal 좋아하는데 조용한 도서관" 같은 충돌 상황을 AI가 자동 조율
- **Context 삽입**: 세 매트릭스를 텍스트로 변환 + preferred_genres + artist_persona.summary
- **제약조건**: 소음도 우선, 사용자 취향과 타협
- **출력 형식**: AIGenreRecommendation (ai_recommended_genres 5개 + reasoning)
- **예시 3개 포함**: few-shot 방식으로 타협 방향 명시

### 3. SEARCH_QUERY_PROMPT

- **목적**: Spotify Search API의 `q` 파라미터 형식에 맞는 쿼리 8개 생성
- **설계 이유**: 자유텍스트 검색은 컬렉션/스팸 결과가 많아 필터 문법 강제
- **Context 삽입**: ai_genres 5개, ai_reasoning, decibel/goal/location
- **제약조건**:
  - `energy:`, `tempo:` 등 오디오 특성 필드 금지 (Search API 미지원)
  - `label:` 금지
  - 최소 필드 필터 2개 이상
  - 8개 중 5개는 AI 추천 장르, 3개는 한국 음악
- **출력 형식**: ContextSearchQueries (query + rationale 8쌍)

### 4. SELECTION_PROMPT

- **목적**: 50개 후보 + 선호 아티스트 트랙 중 10곡 선택
- **설계 이유**: 필수 비율을 LLM에 명시적으로 요구해 단순 인기도순 선택 방지
- **Context 삽입**: 전체 후보 트랙 목록 (format_tracks_for_prompt 형식)
- **제약조건**: 선호2/한국5/신곡2/인기도4-4-2 필수, 스팸 제목 금지
- **출력 형식**: FinalSelection (10개 track_id + selection_reason)

### 5. QUALITY_VALIDATOR_PROMPT

- **목적**: 선택된 10곡의 품질 검증
- **설계 이유**: 코드 계산값과 LLM 판단 교차검증으로 오류 탐지
- **Context 삽입**: selected_tracks_info, preferred_artists, 임계값들
- **출력 형식**: QualityValidation (is_valid + 수치들 + feedback)

### 6. GENERATE_REASON_PROMPT

- **목적**: 각 트랙별 추천 이유 한국어 생성
- **설계 이유**: 사용자가 왜 이 곡이 추천됐는지 납득할 수 있는 UX 제공
- **Context 삽입**: decibel/goal/location, ai_genres, artist_persona.summary, 전체 트랙 목록
- **출력 형식**: FinalRecommendations (track_id + reason 쌍)

### 7. FEEDBACK_SEARCH_PROMPT (재시도 전용)

- **목적**: 품질 검증 실패 원인에 맞는 개선 쿼리 생성
- **설계 이유**: 한국곡 부족/신곡 부족/선호아티스트 부족 각각 다른 전략 명시
- **Context 삽입**: validation_feedback 문자열, ai_genres, preferred_artists

---

## Context 처리 방식

### 상황 매트릭스 (config.py)

```python
# 소음도 → 음악 특성 매핑
DECIBEL_MUSIC_PROFILES = {
    "quiet": {"energy_range": (0.1, 0.4), "tempo_range": (60, 100), ...},
    "moderate": {"energy_range": (0.3, 0.7), "tempo_range": (90, 130), ...},
    "loud": {"energy_range": (0.6, 1.0), "tempo_range": (120, 180), ...}
}

# 목표 → 장르/분위기 매핑
GOAL_MUSIC_PROFILES = {
    "focus": {"suggested_genres": ["lo-fi", "ambient", "classical", ...], ...},
    "sleep": {"suggested_genres": ["ambient", "acoustic", "meditation", ...], ...},
    ...
}

# 위치 → 에너지 보정값
LOCATION_MODIFIERS = {
    "gym": {"adjust_energy": +0.2},
    "library": {"adjust_energy": -0.2},
    "home": {"adjust_energy": 0.0},
    ...
}
```

### 프롬프트 반영 방식

- 세 매트릭스를 각각 텍스트 블록으로 직렬화
- CONTEXT_ANALYSIS_PROMPT에 `{decibel_profile}`, `{goal_profile}`, `{location_modifier}` 형태로 삽입
- LLM이 우선순위(소음 1순위)를 읽고 타협점 판단

### 예외 상황 처리

- 프롬프트 내 few-shot 예시 3개 (조용한 환경+k-pop, 시끄러운+active, consolation+hip-hop)
- 소음도 vs 목표 충돌 사례 명시 ("sleep인데 metal" → ambient로 대체)
- FEEDBACK_SEARCH_PROMPT에서 실패 종류별 전략 명시

---

## 추천 로직

### LLM이 담당하는 부분

| 역할 | 노드 | 이유 |
|------|------|------|
| 사용자 취향 페르소나 추출 | analyze_preference | 아티스트 간 관계, 숨겨진 공통 특성 파악 |
| 상황-장르 타협 | context_analysis | 규칙 기반으로 불가능한 문맥적 판단 |
| Spotify 쿼리 최적화 | search_query_generator | 필터 문법 조합의 창의적 활용 |
| 비율/다양성 기준 선택 | selection | 50개 후보 중 조건 충족 최적 조합 |
| 품질 검증 | quality_validator | 다양성 같은 주관적 요소 판단 |
| 추천 이유 생성 | generate_reason | 자연어 설명 |

### 코드가 담당하는 부분

| 역할 | 위치 | 이유 |
|------|------|------|
| 스팸 제목 필터링 | nodes.py:is_spam_title | 규칙 기반, 정확도 보장 |
| 한국 노래 판별 | nodes.py:is_korean_track | 한글 정규식 필요 |
| 리믹스/라이브 필터 | nodes.py:remix_track_filter | 단순 키워드 매칭 |
| 인기도 레벨 분류 | nodes.py:get_popularity_level | 수치 기준 분류 |
| 신곡 날짜 파싱 | nodes.py:quality_validator | YYYY/YYYY-MM/YYYY-MM-DD 세 형식 처리 |
| 병렬 검색 | spotify_client.py:parallel_search | I/O 바운드 병렬화 |
| 입력 검증 | server.py | 열거형 체크 |

---

## 데이터 구조

### AgentState (TypedDict)

```python
class AgentState(TypedDict):
    # 입력
    location: str                           # "library"
    goal: str                               # "focus"
    decibel: str                            # "quiet"
    preferred_artists: List[str]            # ["BTS", "IU"]
    preferred_genres: List[str]             # ["k-pop"]
    
    # 분석 결과
    artist_persona: Optional[ArtistPersona] # LLM 구조화 출력
    ai_recommended_genres: Optional[List[str]]  # ["lo-fi", "ambient", ...]
    ai_genre_reasoning: Optional[str]           # 추천 이유 문자열
    search_queries: Optional[List[SearchQuery]] # Spotify 쿼리 8개
    
    # 트랙 데이터
    candidate_tracks: List[SpotifyTrack]    # 최대 50개 (Spotify 검색 결과)
    preference_tracks: List[SpotifyTrack]   # 선호 아티스트 트랙
    selected_tracks: List[SpotifyTrack]     # LLM 선택 10개 (필터 후)
    final_tracks: List[SpotifyTrack]        # 품질 통과 최종 10개
    
    # 추천 이유
    recommendations: Optional[FinalRecommendations]  # track_id → reason
    
    # 순환 제어
    iteration_count: int                    # 현재 반복 횟수
    validation_feedback: Optional[str]      # 실패 시 피드백 (재시도 트리거)
    quality_validation: Optional[QualityValidation]  # 검증 결과 전체
```

### SpotifyTrack (Pydantic)

```python
class SpotifyTrack(BaseModel):
    id: str              # Spotify 트랙 ID
    name: str            # 트랙 제목
    artists: List[SpotifyArtist]  # genres=[] 항상 빈 리스트
    album_name: str
    release_date: str    # "YYYY" / "YYYY-MM" / "YYYY-MM-DD" 세 형식 가능
    duration_ms: int
    popularity: int      # 0-100
    preview_url: Optional[str]
    external_url: str    # "https://open.spotify.com/track/..."
```

### QualityValidation (Pydantic)

```python
class QualityValidation(BaseModel):
    is_valid: bool                          # LLM 판정 (코드 combined is_valid와 다를 수 있음)
    diversity_score: float                  # LLM 계산
    preferred_artist_ratio: float           # LLM 계산
    recent_tracks_count: int                # LLM 계산
    korean_tracks_count: int                # 코드가 덮어씀
    popularity_distribution: PopularityDistribution  # 코드가 덮어씀
    feedback: Optional[str]                 # 실패 시 개선 방향
```

---

## 주요 알고리즘

### 스팸 필터 (is_spam_title)

```python
def is_spam_title(title: str) -> bool:
    title_lower = title.lower()
    # 1. 고정 키워드 목록 (대소문자 무시)
    for keyword in SPAM_KEYWORDS:
        if keyword.lower() in title_lower:
            return True
    # 2. 숫자+시간 단위 정규식
    if re.search(r'\d+\s*(시간|분|hour|min)', title_lower):
        return True
    return False
```

- **목적**: "집중에 좋은 로파이 1시간", "(Lofi Study)" 같은 SEO 최적화 컬렉션 제목 제거
- **선택 이유**: Spotify 검색 결과에 실제 곡이 아닌 컴필레이션이 다수 포함되는 문제 해결

### 한국 곡 판별 (is_korean_track)

```python
def is_korean_track(track: SpotifyTrack) -> bool:
    # 1순위: 제목에 한글 포함
    if re.search(r'[가-힣]', track.name):
        return True
    # 2순위: 아티스트명에 한국 지시어 포함
    artist_names = track.get_artist_names()
    for indicator in KOREAN_INDICATORS:  # "BTS", "IU", "아이유", "BLACKPINK" ...
        if indicator in artist_names:
            return True
    # 3순위: 아티스트 장르 (실제로는 genres=[] 이므로 작동 안 함)
    for artist in track.artists:
        for genre in artist.genres:
            if 'k-pop' in genre.lower() or ...:
                return True
    return False
```

- **실질적 판별 방법**: 한글 제목 + KOREAN_INDICATORS 키워드 매칭 (장르 기반은 비활성)

### 품질 검증 복합 판정

```python
is_valid = (
    validation.is_valid           # LLM: 다양성/선호아티스트 비율
    and korean_count >= 4         # 코드: 한국곡 최소 4개
    and recent_count >= 2         # 코드: 신곡 최소 2개
)
```

- **AND 조건**: 하나라도 실패 시 재시도
- **우선도**: 코드 계산값이 LLM 판정 일부를 override

### 재시도 루프

```
search_query_generator
       ↓
    tools
       ↓
 preference_search
       ↓
   selection
       ↓
remix_track_filter
       ↓
quality_validator ──실패 (< iteration 3)──► search_query_generator (피드백 반영)
       │
    통과 또는 iteration >= 3
       ↓
 generate_reason
```

- MAX_ITERATIONS=3: 3회 이상 실패 시 강제 진행
- 재시도마다 `validation_feedback`이 프롬프트에 포함되어 쿼리 전략 변경

---

## 예외 처리

### 서버 레벨 (server.py)

- 입력 값이 LOCATIONS/GOALS/DECIBEL_LEVELS에 없으면 HTTP 400 (명시적 메시지)
- preferred_artists 0개면 HTTP 400
- LangGraph 실행 중 예외 → HTTP 500 + traceback 출력

### Spotify API 레벨 (spotify_client.py)

- `search_tracks`: try/except → 빈 리스트 반환 (검색 실패해도 전체 흐름 지속)
- `_parse_track`: try/except → None 반환 (단건 파싱 실패 무시)
- `get_artist_recent_tracks`: 날짜 파싱 실패 시 해당 앨범 건너뜀 (ValueError continue)
- `parallel_search`: future 개별 실패 시 해당 쿼리만 제외하고 계속

### 품질 검증 레벨 (nodes.py)

- release_date 파싱 실패: bare `except: pass` (날짜 형식 불일치 무시)
- 품질 실패: MAX_ITERATIONS 도달 시 현재 결과로 강제 진행 (서비스 가용성 우선)
- remix_track_filter: 필터링 후 10곡 미만 시 필터 제거 트랙 복구

### 서버 시작 레벨 (server.py startup)

- `validate_config()` 실패 시 서버 시작 중단 (API 키 미설정)

---

## 실행 방법

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. .env 파일 생성 (music-recommendation-engine/ 폴더)
OPENAI_API_KEY=sk-...
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...

# 3. 서버 실행
python server.py
# 또는
uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# 4. API 문서 확인
# http://localhost:8000/docs

# 5. 테스트 클라이언트 실행 (별도 터미널)
python test_client.py

# 6. curl 테스트
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "location": "library",
    "goal": "focus",
    "decibel": "quiet",
    "preferred_artists": ["BTS", "IU"],
    "preferred_genres": ["k-pop"]
  }'
```

---

## 개선 가능성

### 1. SpotifyArtist.genres 미수집 버그

`_parse_track`에서 `genres=[]`로 고정. 실제 아티스트 장르를 가져오려면 `sp.artist(artist_id)` 별도 호출 필요. `is_korean_track`의 장르 기반 판별(3단계)이 현재 완전히 비활성화 상태.

### 2. should_continue와 quality_validator의 is_valid 불일치

`quality_validator`의 코드 combined `is_valid`는 `state["final_tracks"]` 설정 여부에 영향. `should_continue`는 `validation.is_valid`(LLM 판정)만 보므로, LLM이 valid + 코드가 invalid인 경우 `final_tracks=[]`인 채로 `generate_reason`에 진입할 수 있음.

**해결**: `validation.is_valid = is_valid` 로 LLM 결과를 코드 결과로 덮어쓰거나, `should_continue`가 `state.get("final_tracks")` 존재 여부를 추가 확인.

### 3. get_artist_recent_tracks의 N+1 API 호출

앨범 목록 → 각 트랙 `sp.track(item['id'])` 개별 호출. 앨범 1개당 최대 5번 API 호출. 배치 API(`sp.tracks([ids])`)로 교체하면 호출 횟수 대폭 감소.

### 4. selection 노드의 트랙 ID 매칭 실패 미처리

LLM이 존재하지 않는 track_id를 반환하면 조용히 건너뜀. 최종 selected_tracks가 10개 미만이 될 수 있음. 부족분을 candidate_tracks에서 자동 보충하는 로직 필요.

### 5. 한국 곡 비율 고정 설계 (50%)

KOREAN_TRACK_RATIO=0.5가 상수로 고정. 외국 사용자에게는 맞지 않음. 사용자 국가 기반 동적 조정 또는 API 파라미터로 노출 필요.

### 6. 모델 설정 하드코딩

`OPENAI_MODEL = "gpt-4.1-mini"` 상수 고정. 6번의 LLM 호출 모두 같은 모델. analyze_preference 같은 단순 작업은 더 작은 모델, generate_reason은 더 큰 모델로 분리하면 비용/품질 균형 가능.

### 7. 프롬프트 버전 관리 부재

prompts.py가 단순 문자열. 프롬프트 변경 시 A/B 비교 불가. 버전 관리 또는 프롬프트 레지스트리 도입 고려.

---

## 코드 리뷰

### 좋은 구조

1. **단방향 데이터 흐름**: AgentState TypedDict가 모든 노드를 관통 → 노드 간 결합도 낮음
2. **구조화된 LLM 출력**: `with_structured_output(Pydantic)` 일관 사용 → JSON 파싱 오류 방지
3. **설정 중앙화**: config.py에 모든 수치 집중 → 튜닝 시 단일 파일 수정
4. **스팸 필터 2단계**: 코드 전처리 + LLM 프롬프트 양쪽에 스팸 방지 명시 (이중 안전장치)
5. **싱글톤 Spotify 클라이언트**: 요청마다 재인증 방지
6. **병렬 Spotify 검색**: I/O 바운드 작업 ThreadPoolExecutor로 병렬화

### 아쉬운 구조

1. **bare except 사용**: `quality_validator`의 날짜 파싱에서 `except: pass` → 오류 원인 파악 불가
2. **nodes.py의 AIGenreRecommendation**: models.py가 아닌 nodes.py에 정의 → 모델 위치 일관성 없음
3. **mixed validation 로직**: quality_validator에서 코드 계산 + LLM 호출 + 코드 override가 뒤섞임 → 의도 파악 어려움
4. **should_continue의 is_valid 불일치**: 앞서 설명한 잠재적 버그
5. **test_client.py가 입력 받는 interactive 방식**: CI/CD에서 자동 테스트 불가
6. **preference_search의 최대 5명 하드코딩**: `preferred_artists[:5]` → API 파라미터로 노출 고려

### 리팩토링 포인트

1. `quality_validator`를 `_compute_quality_metrics(tracks)` + `_llm_validate(tracks, metrics)` + `_merge_validations(llm, code)` 세 함수로 분리
2. `should_continue`에서 `state.get("final_tracks")` 존재 여부 추가 체크
3. `_parse_track`에 아티스트 genres 수집 옵션 추가 (배치 API 활용)
4. `is_valid` 최종값을 `validation.is_valid`에 write-back

---

## 면접에서 설명하면 좋을 구현 포인트

### 1. LangGraph 상태 기계 설계

"9개 노드가 TypedDict 하나를 공유하는 단방향 상태 기계. 품질 실패 시 노드 3번으로 돌아가는 조건부 엣지를 통해 재시도 루프를 구현했습니다. 이 구조 덕분에 각 노드는 독립적으로 테스트 가능하고, 상태 변화 추적이 명확합니다."

### 2. 우선순위 기반 컨텍스트 처리

"소음도(1순위) → 목표(2순위) → 위치(3순위) 매트릭스를 config.py에 정의하고, context_analysis 노드에서 이를 텍스트로 직렬화해 LLM 프롬프트에 삽입합니다. 규칙 기반(매트릭스)과 LLM의 창의적 타협 능력을 결합한 하이브리드 방식입니다."

### 3. 구조화된 LLM 출력 (Structured Output)

"모든 LLM 호출에 `with_structured_output(Pydantic 모델)`을 사용합니다. 이렇게 하면 LLM이 JSON 파싱 오류 없이 타입-세이프한 객체를 반환하며, 스키마 자체가 프롬프트에 암묵적으로 포함되어 출력 형식을 강제합니다."

### 4. 이중 검증 전략 (코드 + LLM)

"품질 검증을 코드(한국곡 수, 신곡 수, 인기도 분포 수치 계산)와 LLM(다양성, 선호 아티스트 비율 판단)으로 이중 검증합니다. 수치 계산은 코드가 더 정확하므로 LLM 결과를 override하고, 주관적 판단은 LLM에 위임하는 역할 분리를 구현했습니다."

### 5. 피드백 루프와 적응적 재검색

"quality_validator에서 실패 원인을 피드백 문자열로 저장하면, search_query_generator가 재진입 시 FEEDBACK_SEARCH_PROMPT를 사용해 '한국 곡 부족 → genre:k-pop 쿼리 비중 증가'처럼 실패 원인에 맞는 쿼리 전략으로 자동 전환됩니다."

### 6. Spotify 쿼리 엔지니어링

"단순 텍스트 검색이 아닌 `genre:lo-fi year:2023-2025` 형태의 필터 문법을 강제해 컴필레이션 앨범, SEO 스팸 트랙을 사전 차단합니다. 또한 ThreadPoolExecutor로 8개 쿼리를 병렬 실행해 검색 지연을 최소화했습니다."

### 7. 20% 선호 아티스트 보장 메커니즘

"선호 아티스트 트랙을 일반 검색과 별도 파이프라인(preference_search)으로 수집 후 후보풀에 합산합니다. selection 프롬프트에 '2곡 필수' 규칙을 명시하고, quality_validator에서도 preferred_artist_ratio를 검증해 이중으로 보장합니다."
