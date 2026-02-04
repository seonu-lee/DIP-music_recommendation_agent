이 레포지토리는 앞서 분석한 데이터를 바탕으로 **LLM 기반 에이전트가 어떻게 작동하는지** 보여주는 핵심 소스코드를 포함하고 있습니다.

---

# Soundscape_DIP: Context-Aware Music Recommendation Agent

본 레포지토리는 사용자의 다차원적인 상황 맥락(위치, 목적, 소음 수준)을 실시간으로 분석하여 최적의 음악을 추천하는 **LangGraph 및 GPT-4.1-mini 기반 추천 에이전트의 핵심 엔진** 구현 코드를 담고 있습니다.

---

## 핵심 차별점 (Core Features)

1. 
**우선순위 기반 상황 분석**: 상황 요소를 단순히 결합하는 것이 아니라, 음악의 가청성과 직결되는 **소음도(1순위)**를 최우선으로 고려하여 에너지를 결정하고, **목표(2순위)**와 **위치(3순위)** 순으로 정교하게 보정합니다. 


2. 
**AI 주도 장르 타협**: GPT-4.1-mini가 현재 상황에 최적인 장르를 제안하며, 사용자의 선호 장르와 지능적으로 타협하여 '개인화'와 '상황 적합성'의 균형을 맞춥니다. 


3. **엄격한 품질 보장 (Constraint-based Selection)**:
* 
**선호 아티스트 보장**: 추천 곡의 20%는 반드시 사용자의 선호 아티스트 곡으로 구성합니다. 


* 
**다양성 및 지역성**: 한국 노래 50%, 신곡 20% 비율을 유지하며, 인기도 분포(고/중/저)를 균형 있게 구성합니다. 


* 
**스팸 필터링**: SEO 최적화용 키워드 스팸 제목을 가진 트랙을 자동으로 제외합니다. 




4. 
**자가 교정 워크플로우**: 품질 검증 지표를 충족하지 못할 경우, 최대 3회까지 자동으로 검색 쿼리를 수정하여 재시도합니다. 



---

## 시스템 아키텍처 (Architecture)

### 기술 스택

* 
**Workflow Engine**: LangGraph (복잡한 9개 노드 상태 관리 및 조건부 라우팅) 


* 
**Language Model**: GPT-4.1-mini (OpenAI Structured Output 활용) 


* 
**Music Data**: Spotify Web API (Spotipy) 


* 
**Framework**: FastAPI (REST API 기반 엔드포인트) 



### 워크플로우 (9-Step Node)

1. 
**analyze_preference**: 사용자 선호 아티스트/장르 분석 및 페르소나 생성 


2. 
**context_analysis**: 소음/목표/위치 기반 AI 장르 추천 및 타협 


3. 
**search_query_generator**: Spotify 전용 검색 쿼리(8개) 생성 


4. 
**tools & preference_search**: Spotify API 병렬 검색 및 후보군 수집 


5. 
**selection**: 10곡 최종 선택 (제약 조건 준수 확인) 


6. 
**remix_track_filter**: 리믹스/라이브 버전 필터링 


7. 
**quality_validator**: 품질 검증 및 실패 시 재시도(Retry) 루프 


8. 
**generate_reason**: 사용자 맞춤형 추천 사유 생성 



---

## 주요 설정 및 기준 (Configuration)

| 항목 | 목표치 | 설명 |
| --- | --- | --- |
| **선호 아티스트 비율** | 20% (2곡) | 10곡 중 최소 2곡 보장 

 |
| **한국 노래 비율** | 50% (5곡) | 최소 40% 이상 유지 

 |
| **신곡 비율** | 20% (2곡) | 최근 4년 이내(2021-2025) 발매곡 

 |
| **인기도 분포** | 4:4:2 | 고(80-100), 중(50-79), 저(10-49) 분포 

 |
| **최대 재시도** | 3회 | 품질 미달 시 자동 재시도 횟수 

 |

---

## 실행 방법 (Usage)

### API 엔드포인트 예시

```http
POST /recommend
{
  "location": "library",
  "goal": "focus",
  "decibel": "quiet",
  "preferred_artists": ["IU", "Day6"],
  "preferred_genres": ["K-pop", "Ballad"]
}

```


## 성능 분석 결과 요약

* 
**Persona-Genre Accuracy**: 100.00% (사용자 취향 완벽 이해) 


* 
**Context-Sentiment Accuracy**: 81.17% (상황 맥락 정확히 이해) 


* 
**Deep Link Conversion**: 85.15% (실제 청취로 이어지는 높은 수용도) 


