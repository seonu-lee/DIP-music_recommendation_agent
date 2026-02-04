"""
LangGraph 노드 통합 최종 버전
주요 수정:
- 10곡 추천
- 한국 노래 50% (5곡)
- 키워드 스팸 필터링
- 인기도 분포 (높음4, 중간4, 낮음2)
- 신곡 4년 기준 (2021-2025)
"""
from typing import List
from datetime import datetime, timedelta
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from config import (
    OPENAI_MODEL,
    QUALITY_THRESHOLDS,
    MAX_ITERATIONS,
    DECIBEL_MUSIC_PROFILES,
    GOAL_MUSIC_PROFILES,
    LOCATION_MODIFIERS,
    PREFERRED_ARTIST_TRACK_RATIO,
    KOREAN_TRACK_RATIO,
    RECENT_TRACK_RATIO,
    RECENT_YEARS,
    SPAM_KEYWORDS,
    KOREAN_INDICATORS,
    POPULARITY_DISTRIBUTION,
)
from models import (
    AgentState,
    ArtistPersona,
    SearchQuery,
    ContextSearchQueries,
    FinalSelection,
    QualityValidation,
    PopularityDistribution,  # 🔧 추가
    FinalRecommendations,
    SpotifyTrack
)
from prompts import (
    ANALYZE_PREFERENCE_PROMPT,
    CONTEXT_ANALYSIS_PROMPT,
    SEARCH_QUERY_PROMPT,
    SELECTION_PROMPT,
    QUALITY_VALIDATOR_PROMPT,
    GENERATE_REASON_PROMPT,
    FEEDBACK_SEARCH_PROMPT,
    format_tracks_for_prompt
)
from spotify_client import get_spotify_client

llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0.7)


# === 유틸리티 함수 ===

def is_spam_title(title: str) -> bool:
    """키워드 스팸 제목 판별"""
    title_lower = title.lower()
    
    # 스팸 키워드 체크
    for keyword in SPAM_KEYWORDS:
        if keyword.lower() in title_lower:
            return True
    
    # 숫자+시간 패턴 체크 (1시간, 2 hours 등)
    if re.search(r'\d+\s*(시간|분|hour|min)', title_lower):
        return True
    
    return False


def is_korean_track(track: SpotifyTrack) -> bool:
    """한국 노래 판별"""
    # 1. 한글 포함 여부
    if re.search(r'[가-힣]', track.name):
        return True
    
    # 2. 한국 아티스트 키워드
    artist_names = track.get_artist_names()
    for indicator in KOREAN_INDICATORS:
        if indicator in artist_names:
            return True
    
    # 3. 아티스트 장르에 k-pop, k-indie 등 포함
    for artist in track.artists:
        for genre in artist.genres:
            if 'k-pop' in genre.lower() or 'k-indie' in genre.lower() or 'korean' in genre.lower():
                return True
    
    return False


def get_popularity_level(popularity: int) -> str:
    """인기도 레벨 반환"""
    if 80 <= popularity <= 100:
        return "high"
    elif 50 <= popularity < 80:
        return "medium"
    else:
        return "low"


# === 새로운 출력 모델: AI 추천 장르 ===
class AIGenreRecommendation(BaseModel):
    """AI가 상황 분석 후 추천한 장르"""
    ai_recommended_genres: List[str] = Field(
        description="AI가 추천한 장르 5개"
    )
    reasoning: str = Field(
        description="추천 이유와 선호 장르와의 타협점"
    )


# === 노드 1: 선호 아티스트 분석 ===
def analyze_preference(state: AgentState) -> AgentState:
    """사용자의 선호 아티스트와 장르 분석"""
    print("\n[1/8] 🎵 선호 아티스트 & 장르 분석 중...")
    
    preferred_artists = state["preferred_artists"]
    preferred_genres = state["preferred_genres"]
    
    prompt = ANALYZE_PREFERENCE_PROMPT.format(
        preferred_artists=", ".join(preferred_artists),
        preferred_genres=", ".join(preferred_genres) if preferred_genres else "지정 없음"
    )
    
    structured_llm = llm.with_structured_output(ArtistPersona)
    artist_persona = structured_llm.invoke([
        SystemMessage(content="당신은 전문 음악 큐레이터입니다."),
        HumanMessage(content=prompt)
    ])
    
    print(f"✓ 주요 장르: {', '.join(artist_persona.dominant_genres)}")
    print(f"✓ 선호 장르: {', '.join(preferred_genres) if preferred_genres else '없음'}")
    
    state["artist_persona"] = artist_persona
    return state


# === 노드 2: 상황 분석 및 AI 장르 추천 ===
def context_analysis(state: AgentState) -> AgentState:
    """
    상황 분석 및 AI 추천 장르 생성
    우선순위: 1) 소음도 2) 목표 3) 위치
    사용자 선호 장르와 AI 추천 장르 타협
    """
    print("\n[2/8] 🎯 상황 분석 & AI 장르 추천 중...")
    print(f"   우선순위: 1)소음({state['decibel']}) 2)목표({state['goal']}) 3)위치({state['location']})")
    
    # 1순위: 소음도 프로필
    decibel = state["decibel"]
    decibel_profile = DECIBEL_MUSIC_PROFILES[decibel]
    decibel_text = f"""
에너지 범위: {decibel_profile['energy_range']}
볼륨 키워드: {', '.join(decibel_profile['volume_keywords'])}
피해야 할: {', '.join(decibel_profile['avoid_keywords'])}
템포 범위: {decibel_profile['tempo_range']} BPM
보컬 선호: {decibel_profile['vocal_preference']}
"""
    
    # 2순위: 목표 프로필
    goal = state["goal"]
    goal_profile = GOAL_MUSIC_PROFILES[goal]
    goal_text = f"""
설명: {goal_profile['description']}
분위기: {', '.join(goal_profile['mood'])}
특성: {', '.join(goal_profile['characteristics'])}
추천 장르: {', '.join(goal_profile['suggested_genres'])}
에너지 레벨: {goal_profile['energy_level']}
피해야 할: {', '.join(goal_profile.get('avoid', []))}
"""
    
    # 3순위: 위치 보정
    location = state["location"]
    location_mod = LOCATION_MODIFIERS[location]
    location_text = f"""
분위기: {location_mod['atmosphere']}
보정: {location_mod['modifier']}
에너지 조정: {location_mod['adjust_energy']:+.1f}
"""
    
    # 프롬프트 생성
    artist_persona = state["artist_persona"]
    preferred_genres = state["preferred_genres"]
    
    prompt = CONTEXT_ANALYSIS_PROMPT.format(
        location=location,
        goal=goal,
        decibel=decibel,
        decibel_profile=decibel_text,
        goal_profile=goal_text,
        location_modifier=location_text,
        preferred_genres=", ".join(preferred_genres) if preferred_genres else "지정 없음",
        artist_persona_summary=artist_persona.summary
    )
    
    # LLM 호출 - AI 추천 장르 생성
    structured_llm = llm.with_structured_output(AIGenreRecommendation)
    ai_genre_rec = structured_llm.invoke([
        SystemMessage(content="당신은 상황 기반 음악 추천 전문가입니다."),
        HumanMessage(content=prompt)
    ])
    
    print(f"✓ AI 추천 장르: {', '.join(ai_genre_rec.ai_recommended_genres)}")
    print(f"✓ 추천 이유: {ai_genre_rec.reasoning[:100]}...")
    
    # 상태에 저장
    state["ai_recommended_genres"] = ai_genre_rec.ai_recommended_genres
    state["ai_genre_reasoning"] = ai_genre_rec.reasoning
    
    return state


# === 노드 3: 검색 쿼리 생성 (Spotify 필터 문법 활용) ===
def search_query_generator(state: AgentState) -> AgentState:
    """Spotify 필터 문법을 활용한 고도화된 검색 쿼리 생성"""
    print("\n[3/8] 🔍 고도화된 검색 쿼리 생성 중...")
    
    ai_genres = state["ai_recommended_genres"]
    ai_reasoning = state["ai_genre_reasoning"]
    validation_feedback = state.get("validation_feedback")
    
    if validation_feedback:
        print("⚠ 품질 검증 피드백 반영 중...")
        prompt = FEEDBACK_SEARCH_PROMPT.format(
            validation_feedback=validation_feedback,
            ai_genres=", ".join(ai_genres),
            preferred_artists=", ".join(state["preferred_artists"])
        )
    else:
        prompt = SEARCH_QUERY_PROMPT.format(
            ai_genres=", ".join(ai_genres),
            ai_reasoning=ai_reasoning,
            decibel=state["decibel"],
            goal=state["goal"],
            location=state["location"]
        )
    
    structured_llm = llm.with_structured_output(ContextSearchQueries)
    queries_result = structured_llm.invoke([
        SystemMessage(content="당신은 Spotify 검색 전문가입니다. 필터 문법을 활용하세요."),
        HumanMessage(content=prompt)
    ])
    
    print(f"✓ 생성된 쿼리 {len(queries_result.queries)}개:")
    for i, q in enumerate(queries_result.queries, 1):
        print(f"  {i}. {q.query}")
    
    state["search_queries"] = queries_result.queries
    return state


# === 노드 4, 5: Spotify 검색 ===
def tools(state: AgentState) -> AgentState:
    """생성된 검색 쿼리로 Spotify API 병렬 검색"""
    print("\n[4/8] 🎧 Spotify 검색 실행 중...")
    
    search_queries = state["search_queries"]
    spotify_client = get_spotify_client()
    
    queries = [q.query for q in search_queries]
    candidate_tracks = spotify_client.parallel_search(
        queries=queries,
        limit_per_query=10
    )
    
    print(f"✓ 후보 트랙 {len(candidate_tracks)}곡 검색 완료")
    
    state["candidate_tracks"] = candidate_tracks
    return state


def preference_search(state: AgentState) -> AgentState:
    """선호 아티스트의 곡 검색 (20% 포함용)"""
    print("\n[5/8] ⭐ 선호 아티스트 곡 검색 중 (20% 포함용)...")
    
    preferred_artists = state["preferred_artists"]
    spotify_client = get_spotify_client()
    
    preference_tracks = []
    
    for artist in preferred_artists[:5]:
        # 최신 곡 (4년)
        recent_tracks = spotify_client.get_artist_recent_tracks(
            artist_name=artist,
            months=48
        )
        preference_tracks.extend(recent_tracks[:3])
        
        # 인기 곡
        top_tracks = spotify_client.search_artist_tracks(
            artist_name=artist,
            limit=3
        )
        preference_tracks.extend(top_tracks)
    
    # 중복 제거
    unique_tracks = []
    seen_ids = set()
    for track in preference_tracks:
        if track.id not in seen_ids:
            unique_tracks.append(track)
            seen_ids.add(track.id)
    
    print(f"✓ 선호 아티스트 곡 {len(unique_tracks)}곡 검색 완료")
    print(f"   (이 중 2곡은 최종 추천에 반드시 포함됨)")
    
    state["preference_tracks"] = unique_tracks
    return state


# === 노드 6: 최종 트랙 선택 (10곡, 필터링 포함) ===
def selection(state: AgentState) -> AgentState:
    """
    최종 10곡 선택
    - 선호 아티스트 20% (2곡)
    - 한국 노래 50% (5곡)
    - 키워드 스팸 필터링
    - 인기도 분포
    """
    print("\n[6/8] 🎯 최종 10곡 선택 중...")
    
    candidate_tracks = state["candidate_tracks"]
    preference_tracks = state["preference_tracks"]
    
    # 🆕 키워드 스팸 필터링
    filtered_candidates = [t for t in candidate_tracks if not is_spam_title(t.name)]
    filtered_preference = [t for t in preference_tracks if not is_spam_title(t.name)]
    
    spam_count = (len(candidate_tracks) - len(filtered_candidates)) + (len(preference_tracks) - len(filtered_preference))
    if spam_count > 0:
        print(f"✓ 키워드 스팸 {spam_count}곡 필터링됨")
    
    ai_genres = state["ai_recommended_genres"]
    
    prompt = SELECTION_PROMPT.format(
        decibel=state["decibel"],
        goal=state["goal"],
        location=state["location"],
        ai_genres=", ".join(ai_genres),
        preferred_artists=", ".join(state["preferred_artists"]),
        num_candidates=len(filtered_candidates),
        candidate_tracks_info=format_tracks_for_prompt(filtered_candidates),
        num_preference=len(filtered_preference),
        preference_tracks_info=format_tracks_for_prompt(filtered_preference)
    )
    
    structured_llm = llm.with_structured_output(FinalSelection)
    selection_result = structured_llm.invoke([
        SystemMessage(content="당신은 상황 기반 음악 큐레이터입니다. 10곡을 선택하세요."),
        HumanMessage(content=prompt)
    ])
    
    # 선택된 트랙 객체 찾기
    all_tracks = filtered_candidates + filtered_preference
    track_dict = {track.id: track for track in all_tracks}
    
    selected_tracks = []
    for selection in selection_result.selected_tracks[:10]:  # 최대 10곡
        if selection.track_id in track_dict:
            selected_tracks.append(track_dict[selection.track_id])
    
    # 통계 출력
    preferred_count = sum(1 for t in selected_tracks if any(a.name in state["preferred_artists"] for a in t.artists))
    korean_count = sum(1 for t in selected_tracks if is_korean_track(t))
    
    print(f"✓ {len(selected_tracks)}곡 선택 완료")
    print(f"✓ 선호 아티스트: {preferred_count}곡 ({preferred_count/10*100:.0f}%)")
    print(f"✓ 한국 노래: {korean_count}곡 ({korean_count/10*100:.0f}%)")
    
    state["selected_tracks"] = selected_tracks
    return state


# === 노드 7: 리믹스 필터링 (10곡 대응) ===
def remix_track_filter(state: AgentState) -> AgentState:
    """리믹스, 라이브 버전 필터링"""
    print("\n[7/8] 🎼 리믹스/라이브 버전 필터링 중...")
    
    selected_tracks = state["selected_tracks"]
    
    filter_keywords = [
        "remix", "live", "acoustic", "unplugged",
        "radio edit", "extended", "instrumental",
        "karaoke", "cover", "version"
    ]
    
    filtered_tracks = []
    removed_tracks = []
    
    for track in selected_tracks:
        track_name_lower = track.name.lower()
        should_filter = any(keyword in track_name_lower for keyword in filter_keywords)
        
        if not should_filter:
            filtered_tracks.append(track)
        else:
            removed_tracks.append(track)
    
    # 10곡이 안 되면 복구
    if len(filtered_tracks) < 10 and removed_tracks:
        needed = 10 - len(filtered_tracks)
        filtered_tracks.extend(removed_tracks[:needed])
        print(f"⚠ 필터링 기준 완화: {needed}곡 복구")
    
    if len(filtered_tracks) < 10:
        filtered_tracks = selected_tracks
    
    if removed_tracks and len(filtered_tracks) == 10:
        print(f"✓ {len(removed_tracks)}곡 필터링됨")
    
    state["selected_tracks"] = filtered_tracks[:10]
    return state


# === 노드 8: 품질 검증 (한국 노래, 인기도 분포) ===
def quality_validator(state: AgentState) -> AgentState:
    """
    품질 검증 - 10곡 기준
    - 다양성
    - 선호 아티스트 20%
    - 한국 노래 50%
    - 신곡 20% (4년 이내)
    - 인기도 분포
    """
    print("\n[8/8] ✅ 품질 검증 중...")
    
    selected_tracks = state["selected_tracks"]
    preferred_artists = state["preferred_artists"]
    
    # 수동 검증
    unique_artists = set()
    preferred_count = 0
    korean_count = 0
    recent_count = 0
    popularity_dist = {"high": 0, "medium": 0, "low": 0}
    
    cutoff_date = datetime.now() - timedelta(days=RECENT_YEARS * 365)
    
    for track in selected_tracks:
        # 아티스트
        for artist in track.artists:
            unique_artists.add(artist.name)
            if artist.name in preferred_artists:
                preferred_count += 1
        
        # 한국 노래
        if is_korean_track(track):
            korean_count += 1
        
        # 최신성 (4년)
        try:
            release_date_str = track.release_date
            if len(release_date_str) == 4:
                release_date = datetime.strptime(release_date_str, "%Y")
            elif len(release_date_str) == 7:
                release_date = datetime.strptime(release_date_str, "%Y-%m")
            else:
                release_date = datetime.strptime(release_date_str, "%Y-%m-%d")
            
            if release_date >= cutoff_date:
                recent_count += 1
        except:
            pass
        
        # 인기도 분포
        pop_level = get_popularity_level(track.popularity)
        popularity_dist[pop_level] += 1
    
    diversity_score = len(unique_artists) / len(selected_tracks)
    preferred_ratio = preferred_count / len(selected_tracks)
    korean_ratio = korean_count / len(selected_tracks)
    
    print(f"  다양성: {diversity_score:.2f} (기준: {QUALITY_THRESHOLDS['min_diversity']})")
    print(f"  선호 아티스트: {preferred_ratio:.2%} (목표: 20%)")
    print(f"  한국 노래: {korean_ratio:.2%} (목표: 50%)")
    print(f"  신곡 수: {recent_count}곡 (기준: {QUALITY_THRESHOLDS['min_recent_tracks']})")
    print(f"  인기도 분포: 높음 {popularity_dist['high']}, 중간 {popularity_dist['medium']}, 낮음 {popularity_dist['low']}")
    
    # LLM 검증
    prompt = QUALITY_VALIDATOR_PROMPT.format(
        selected_tracks_info=format_tracks_for_prompt(selected_tracks),
        preferred_artists=", ".join(preferred_artists),
        min_diversity=QUALITY_THRESHOLDS["min_diversity"],
        min_preferred_ratio=QUALITY_THRESHOLDS["min_preferred_ratio"],
        min_recent_tracks=QUALITY_THRESHOLDS["min_recent_tracks"]
    )
    
    structured_llm = llm.with_structured_output(QualityValidation)
    validation = structured_llm.invoke([
        SystemMessage(content="당신은 음악 추천 품질 검증 전문가입니다."),
        HumanMessage(content=prompt)
    ])
    
    # 수동 검증 결과 덮어쓰기
    validation.korean_tracks_count = korean_count
    validation.popularity_distribution = PopularityDistribution(
        high=popularity_dist["high"],
        medium=popularity_dist["medium"],
        low=popularity_dist["low"]
    )  # 🔧 dict → PopularityDistribution 객체
    
    current_iteration = state.get("iteration_count", 0) + 1
    
    # 검증
    is_valid = (
        validation.is_valid and
        korean_count >= QUALITY_THRESHOLDS["min_korean_tracks"] and
        recent_count >= QUALITY_THRESHOLDS["min_recent_tracks"]
    )
    
    if is_valid:
        print("✅ 품질 검증 통과!")
        state["final_tracks"] = selected_tracks
        state["validation_feedback"] = None
    else:
        print(f"❌ 품질 검증 실패 (반복 {current_iteration}/{MAX_ITERATIONS})")
        
        if current_iteration >= MAX_ITERATIONS:
            print("⚠ 최대 반복 횟수 도달 - 현재 결과로 진행")
            state["final_tracks"] = selected_tracks
            state["validation_feedback"] = None
        else:
            state["validation_feedback"] = validation.feedback or f"한국 노래 {korean_count}/5, 신곡 {recent_count}/2 부족"
    
    state["quality_validation"] = validation
    state["iteration_count"] = current_iteration
    return state


# === 노드 9: 추천 이유 생성 (변경 없음) ===
def generate_reason(state: AgentState) -> AgentState:
    """추천 이유 생성"""
    print("\n[9/9] 💬 추천 이유 생성 중...")
    
    final_tracks = state["final_tracks"]
    ai_genres = state["ai_recommended_genres"]
    artist_persona = state["artist_persona"]
    
    prompt = GENERATE_REASON_PROMPT.format(
        decibel=state["decibel"],
        goal=state["goal"],
        location=state["location"],
        ai_genres=", ".join(ai_genres),
        artist_persona_summary=artist_persona.summary,
        selected_tracks_info=format_tracks_for_prompt(final_tracks)
    )
    
    structured_llm = llm.with_structured_output(FinalRecommendations)
    recommendations = structured_llm.invoke([
        SystemMessage(content="당신은 친근한 음악 큐레이터입니다."),
        HumanMessage(content=prompt)
    ])
    
    print("✓ 추천 이유 생성 완료")
    
    state["recommendations"] = recommendations
    return state


# === 조건부 엣지 (변경 없음) ===
def should_continue(state: AgentState) -> str:
    """품질 검증 결과에 따라 다음 노드 결정"""
    validation = state.get("quality_validation")
    iteration_count = state.get("iteration_count", 0)
    
    if validation and validation.is_valid:
        return "continue"
    
    if iteration_count >= MAX_ITERATIONS:
        return "continue"
    
    if state.get("validation_feedback"):
        return "retry"
    
    return "continue"