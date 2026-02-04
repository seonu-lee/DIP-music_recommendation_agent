"""
프롬프트 템플릿 - 우선순위 기반 추천 시스템
우선순위: 1) 소음도 2) 목표 3) 위치
"""

# === 아티스트 페르소나 분석 ===
ANALYZE_PREFERENCE_PROMPT = """당신은 음악 큐레이터입니다. 사용자가 선호하는 아티스트와 장르를 분석하여 음악 취향 페르소나를 파악하세요.

선호 아티스트: {preferred_artists}
선호 장르: {preferred_genres}

다음을 분석하세요:
1. 주요 장르 (최대 3개): 선호 아티스트와 선호 장르를 모두 고려
2. 음악 특성 (3-5개): 템포, 분위기, 악기 구성 등
3. 유사 아티스트 (3-5명): 비슷한 스타일의 다른 아티스트
4. 종합 분석 (2-3문장): 사용자의 음악 취향 요약

답변을 JSON 형식으로 출력하세요.
"""

# === 상황 분석 및 AI 추천 장르 생성 ===
CONTEXT_ANALYSIS_PROMPT = """당신은 음악 추천 전문가입니다. 사용자의 상황을 분석하여 최적의 음악 장르를 추천하세요.

추천 우선순위:
1순위 (최우선): 소음도 → 음악의 가청력과 직결
2순위: 목표 → 사용자가 하고 싶은 행동
3순위: 위치 → 장소의 심리적 분위기

=== 상황 정보 ===
위치: {location}
목표: {goal}
소음 레벨: {decibel}

=== 소음도 기반 음악 특성 (1순위) ===
{decibel_profile}

=== 목표 기반 음악 특성 (2순위) ===
{goal_profile}

=== 위치 기반 분위기 (3순위) ===
{location_modifier}

=== 사용자 취향 ===
선호 장르: {preferred_genres}
음악 취향: {artist_persona_summary}

AI 추천 장르 생성 규칙:
1. **소음도가 최우선**: {decibel} 환경에 맞는 에너지/볼륨의 음악
2. **목표가 두 번째**: {goal} 행동에 적합한 분위기/리듬
3. **위치는 보조적**: {location}의 심리적 분위기 반영
4. **사용자 취향과 타협**: AI 추천 장르와 선호 장르를 적절히 조합

예시 1:
입력: decibel=quiet, goal=focus, location=library
     선호 장르: ["k-pop", "edm"]
AI 추천:
- 소음도(quiet) → "lo-fi", "ambient", "classical" (조용한 음악 필수)
- 목표(focus) → "study music", "instrumental" (집중용)
- 위치(library) → 더욱 차분하게 조정
- 최종 타협: ["lo-fi hip hop", "chill", "ambient"] 
  (K-pop/EDM은 너무 활기차서 제외하고 차분한 장르로 대체)

예시 2:
입력: decibel=loud, goal=active, location=park
     선호 장르: ["indie pop", "alternative"]
AI 추천:
- 소음도(loud) → "edm", "rock", "hip hop" (강한 에너지 필요)
- 목표(active) → "workout", "energetic" (활동적)
- 위치(park) → 개방적이고 상쾌한 분위기
- 최종 타협: ["indie rock", "alternative rock", "upbeat pop"]
  (선호하는 indie/alternative를 더 에너지 넘치게 조정)

예시 3:
입력: decibel=moderate, goal=consolation, location=home
     선호 장르: ["hip hop", "trap"]
AI 추천:
- 소음도(moderate) → 중간 볼륨 (제약 적음)
- 목표(consolation) → "ballad", "soul", "emotional" (위로)
- 위치(home) → 편안하고 개인적
- 최종 타협: ["r&b", "soul", "emotional hip hop"]
  (힙합을 유지하되 감성적인 방향으로)

예외 상황 대처:
- 목표가 "sleep"인데 선호 장르가 "metal"인 경우
  → 소음도(quiet)와 목표(sleep)가 우선, "ambient", "acoustic"로 대체
  
- 소음도가 "loud"인데 목표가 "relax"인 경우
  → 소음도 우선, 강한 음압으로 소음 차단하면서도 편안한 "chill electronic" 등

출력 형식:
{{
  "ai_recommended_genres": ["장르1", "장르2", "장르3", "장르4", "장르5"],
  "reasoning": "소음도/목표/위치를 고려한 추천 이유와 선호 장르와의 타협점 (3-4문장)"
}}

답변을 JSON 형식으로 출력하세요.
"""

# === 검색 쿼리 생성 (Spotify 필터 문법 활용) ===
SEARCH_QUERY_PROMPT = """당신은 Spotify Web API /v1/search 의 q 파라미터에 들어갈 "검색 쿼리"만 생성하는 시스템입니다.

목표:
- 아래 사용자 상황과 AI 추천 장르를 활용해 Spotify Search API에서 노이즈가 적고 재현 가능한 트랙 검색 쿼리 8개를 만드세요.
- Spotify Search API q 문법을 적절히 섞어 사용하세요.

입력: 
AI 추천 장르: {ai_genres}
추천 이유: {ai_reasoning}

사용자 상황:
- 소음: {decibel}
- 목표: {goal}
- 위치: {location}

[중요: 금지 규칙]
- 절대로 아래를 쿼리에 포함하지 마세요: energy:, tempo:, valence:, danceability:, acousticness:, liveness:, speechiness:, instrumentalness:
  (이들은 Search 쿼리 문법이 아니라 오디오 특성값이므로 무효입니다.)
- "label:" 필터도 사용하지 마세요. (Search API 공식 필드 목록에 포함되지 않습니다.)
- 쿼리 문자열은 URL이 아닌 q 값 본문만 작성하세요.
- 쿼리의 시작에 q= 을 반드시 붙이시오

[허용되는 Spotify Search q 필드 필터 문법]
1. `genre:` - 장르 특정 (예: `genre:lo-fi`)
2. `year:` - 연도 범위 (예: `year:2021-2025`)
3. `artist:` - 아티스트 특정 (예: `artist:"BTS"`)
4. `track:` - 곡 제목 특정 (예: `track:"Dynamite"`)

[연산자/문법 가이드]
- 여러 필터는 공백으로 결합합니다: genre:pop year:2021-2025
- OR 사용 가능: artist:"BTS" OR artist:"BLACKPINK"
- 괄호로 그룹화: (artist:"BTS" OR artist:"BLACKPINK") genre:"k-pop" year:2021-2025
- 공백이 있는 값은 반드시 따옴표로 감싸세요: track:"Spring Day"
- 한국어/로마자 변형이 필요하면 쿼리를 2개 버전으로 분리하세요(예: IU / 아이유).

[쿼리 생성 규칙]
- 총 8개의 쿼리 생성
- 각 쿼리는 "필드 필터"를 최소 2개 이상 포함해야 함 (예: genre + year, 또는 genre + artist 등)
- 8개 중 5개는 AI 추천 장르({ai_genres})를 우선 사용
- 8개 중 3개는 한국 음악(genre:"k-pop" / genre:"k-indie" / K-hip-hop 또는 한국 아티스트 artist:) 중심
- year 범위는 다양하게 섞기 (예: 2021-2025, 2022-2025, 2023-2025, 2024-2025)

[노이즈 감소(키워드 스팸 방지) 가이드]
- track/artist 기반 쿼리를 최소 2개 포함해 정확도를 확보하세요.
- 너무 긴 자유 텍스트(예: "집중 잘 되는 로파이 재즈힙합")는 지양하고,
  필요 시 따옴표로 묶어 track:"..." 처럼 명확히 쓰세요

예시 1: 집중 음악 (AI 추천 장르: lo-fi, ambient, instrumental, classical)
쿼리:
1. "q=genre:lo-fi year:2023-2025" 
2. "q=genre:ambient year:2021-2025" 
3. "q=genre:instrumental year:2022-2025" 
4. "q=genre:classical year:2021-2025" 
5. "q=genre:lo-fi" 
6. "q=genre:k-pop artist:BTS year:2021-2025" 
7. "q=artist:IU genre:k-pop year:2021-2025" 
8. "q=artist:10cm OR artist:AKMU year:2021-2025"

예시 2: 운동 음악 (edm, hip hop)
쿼리:
1. "q=genre:edm year:2023-2025" 
2. "q=genre:hip-hop year:2021-2024" 
3. "q=genre:dance year:2022-2025"
4. "q=genre:electronic year:2021-2025" 
5. "q=genre:edm" 
6. "q=genre:k-pop year:2023-2025" 
7. "q=(artist:Stray Kids OR artist:ATEEZ) year:2021-2025" 
8. "q=genre:k-hip-hop year:2022-2025" 


출력 형식:
{{
  "queries": [
    {{
      "query": "genre:lo-fi year:2023-2025",
      "rationale": "최신 로파이 음악 검색 (Spotify 필터 활용)"
    }},
    ...
  ]
}}
"""

# === 최종 트랙 선택 (10곡, 한국 노래 50%, 인기도 분포) ===
SELECTION_PROMPT = """10곡을 선택하세요.

선택 기준 (우선순위 순):
1. **소음도 적합성** ({decibel}): 가장 중요!
2. **목표 적합성** ({goal}): 두 번째로 중요
3. **위치 분위기** ({location}): 보조적
4. **AI 추천 장르 일치**: {ai_genres}

필수 비율 (10곡 기준):
- **선호 아티스트**: 20% (2곡) 필수
- **한국 노래**: 50% (5곡) 필수
- **신곡 (최근 4년)**: 20% (2곡) 필수
- **인기도 분포**:
  * 높음 (80-100): 40% (4곡)
  * 중간 (50-79): 40% (4곡)
  * 낮음 (10-49): 20% (2곡)

제외할 트랙:
- 키워드 스팸 제목 (예: "집중 잘 되는", "공부할 때", "모음곡", "1시간")
- 괄호 안 설명 (예: "(Lofi)", "(Study)", "(Relax)")
- 플레이리스트/컬렉션 (예: "BEST", "모음", "Playlist")

사용자 상황:
- 소음: {decibel}
- 목표: {goal}
- 위치: {location}

AI 추천 장르: {ai_genres}
선호 아티스트: {preferred_artists}

후보 트랙 ({num_candidates}곡):
{candidate_tracks_info}

선호 아티스트의 곡 ({num_preference}곡):
{preference_tracks_info}

필수 규칙:
1. 정확히 10곡 선택
2. 선호 아티스트 2곡 (20%)
3. 한국 노래 5곡 (50%) - 한글 제목, K-pop, K-indie 등
4. 인기도 고르게 분포: 높음 4곡, 중간 4곡, 낮음 2곡
5. 키워드 스팸 제목 절대 선택 금지
6. 신곡 2곡 이상 (2021-2025)

선택 과정:
1. 키워드 스팸 트랙 제외
2. 한국 노래 5곡 선택 (선호 아티스트 포함 가능)
3. 선호 아티스트 2곡 확보 (한국/외국 모두 가능)
4. 인기도 분포 맞추기
5. 신곡 2곡 이상 확인
6. 다양성 확보

출력 형식:
{{
  "selected_tracks": [
    {{
      "track_id": "트랙ID",
      "selection_reason": "선택 이유 (한국 노래/선호 아티스트/인기도/신곡 여부 명시)"
    }},
    ...
  ]
}}
"""

# === 품질 검증 (10곡, 한국 노래, 인기도 분포) ===
QUALITY_VALIDATOR_PROMPT = """추천 결과의 품질을 검증하세요.

추천된 트랙 (10곡):
{selected_tracks_info}

선호 아티스트: {preferred_artists}

검증 기준:
1. 다양성 (최소 {min_diversity}): 고유 아티스트 비율
2. **선호 아티스트 비율** (목표 20%, 최소 {min_preferred_ratio}): 필수!
3. **한국 노래 비율** (목표 50%, 최소 40%): 필수!
4. 최신성 (최소 {min_recent_tracks}곡): 최근 4년 이내 (2021-2025)
5. **인기도 분포**: 높음 4곡, 중간 4곡, 낮음 2곡

검증 실패 조건:
- 선호 아티스트 곡이 2곡 미만
- 한국 노래가 4곡 미만
- 신곡이 2곡 미만
- 인기도 분포가 심하게 치우침

출력 형식:
{{
  "is_valid": true/false,
  "diversity_score": 0.0-1.0,
  "preferred_artist_ratio": 0.0-1.0,
  "recent_tracks_count": 정수,
  "korean_tracks_count": 정수,
  "popularity_distribution": {{"high": 정수, "medium": 정수, "low": 정수}},
  "feedback": "실패 시 개선 방향 (특히 한국 노래, 선호 아티스트, 인기도 분포)"
}}
"""

# === 추천 이유 생성 ===
GENERATE_REASON_PROMPT = """각 트랙의 추천 이유를 작성하세요.

사용자 상황:
- 소음: {decibel} (1순위)
- 목표: {goal} (2순위)  
- 위치: {location} (3순위)

AI 추천 장르: {ai_genres}
사용자 취향: {artist_persona_summary}

추천된 트랙:
{selected_tracks_info}

각 트랙마다:
1. 왜 이 소음 레벨에 적합한지
2. 목표 달성에 어떻게 도움이 되는지
3. 선호 아티스트 곡인 경우 명시
4. 2-3문장으로 친근하게

예시:
"카페의 적당한 소음을 부드럽게 커버하면서도 집중력을 높여주는 lo-fi 비트입니다. 당신이 좋아하는 Lauv의 최신 곡으로, 차분하면서도 생산적인 분위기를 만들어줍니다."

출력 형식:
{{
  "recommendations": [
    {{"track_id": "ID", "reason": "이유"}},
    ...
  ]
}}
"""

# === 피드백 기반 재검색 (Spotify 필터 활용) ===
FEEDBACK_SEARCH_PROMPT = """피드백을 반영하여 개선된 Spotify 검색 쿼리를 생성하세요.

피드백: {validation_feedback}
AI 추천 장르: {ai_genres}
선호 아티스트: {preferred_artists}

Spotify 필터 문법 활용:
- `genre:` - 장르 특정
- `year:2021-2025` - 최근 4년
- `artist:` - 아티스트 특정
- `tag:new` - 최근 신곡

피드백 반영 전략:

**선호 아티스트 부족 시:**
- 선호 아티스트 이름을 직접 쿼리에 포함
- 예: "artist:BTS year:2021-2025", "artist:Lauv year:2023-2025"

**한국 노래 부족 시:**
- 한국 음악 쿼리 비중 증가 (8개 중 5개)
- 예: "genre:k-pop year:2023-2025", "genre:k-indie year:2021-2024"

**신곡 부족 시:**
- 모든 쿼리에 `year:2023-2025` 사용
- `tag:new` 활용

**인기도 불균형 시:**
- 인기 아티스트와 신인 아티스트 균형 맞추기

8개의 개선된 검색 쿼리를 생성하세요.

출력 형식:
{{
  "queries": [
    {{"query": "genre:k-pop year:2023-2025", "rationale": "한국 노래 보강"}},
    ...
  ]
}}
"""


def format_tracks_for_prompt(tracks: list) -> str:
    """트랙 리스트를 프롬프트용 텍스트로 포맷팅"""
    if not tracks:
        return "없음"
    
    formatted = []
    for i, track in enumerate(tracks, 1):
        formatted.append(
            f"{i}. [{track.id}] {track.name} - {track.get_artist_names()} "
            f"(발매: {track.release_date}, 인기도: {track.popularity})"
        )
    return "\n".join(formatted)


if __name__ == "__main__":
    print("=== 우선순위 기반 프롬프트 시스템 ===")
    print("1순위: 소음도")
    print("2순위: 목표")
    print("3순위: 위치")
    print("선호 아티스트: 20% 필수 포함")