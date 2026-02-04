"""
LangGraph 워크플로우 - 우선순위 기반 시스템
"""
from langgraph.graph import StateGraph, END
from models import AgentState

from nodes import (
    analyze_preference,
    context_analysis,  # 🆕 새 노드
    search_query_generator,  # 🆕 새 노드
    tools,
    preference_search,
    selection,
    remix_track_filter,
    quality_validator,
    generate_reason,
    should_continue
)


def create_recommendation_graph():
    """
    음악 추천 LangGraph 생성 (우선순위 기반)
    
    노드 흐름:
    1. analyze_preference: 선호 분석
    2. context_analysis: 🆕 상황 분석 & AI 장르 추천
    3. search_query_generator: 🆕 검색 쿼리 생성
    4. tools: Spotify 검색
    5. preference_search: 선호 아티스트 검색
    6. selection: 최종 선택 (20% 필수)
    7. remix_track_filter: 필터링
    8. quality_validator: 품질 검증
       - 통과 → generate_reason
       - 실패 → search_query_generator (재검색)
    9. generate_reason: 추천 이유
    """
    workflow = StateGraph(AgentState)
    
    # 노드 추가
    workflow.add_node("analyze_preference", analyze_preference)
    workflow.add_node("context_analysis", context_analysis)  # 🆕
    workflow.add_node("search_query_generator", search_query_generator)  # 🆕
    workflow.add_node("tools", tools)
    workflow.add_node("preference_search", preference_search)
    workflow.add_node("selection", selection)
    workflow.add_node("remix_track_filter", remix_track_filter)
    workflow.add_node("quality_validator", quality_validator)
    workflow.add_node("generate_reason", generate_reason)
    
    # 엣지 추가
    workflow.set_entry_point("analyze_preference")
    workflow.add_edge("analyze_preference", "context_analysis")  # 🆕
    workflow.add_edge("context_analysis", "search_query_generator")  # 🆕
    workflow.add_edge("search_query_generator", "tools")  # 🆕
    workflow.add_edge("tools", "preference_search")
    workflow.add_edge("preference_search", "selection")
    workflow.add_edge("selection", "remix_track_filter")
    workflow.add_edge("remix_track_filter", "quality_validator")
    
    # 조건부 엣지 (품질 검증)
    workflow.add_conditional_edges(
        "quality_validator",
        should_continue,
        {
            "continue": "generate_reason",
            "retry": "search_query_generator"  # 🆕 재검색
        }
    )
    
    workflow.add_edge("generate_reason", END)
    
    app = workflow.compile()
    return app


def run_recommendation(
    location: str,
    goal: str,
    decibel: str,
    preferred_artists: list,
    preferred_genres: list = None
) -> dict:
    """
    음악 추천 실행 (우선순위 기반)
    
    우선순위: 1) 소음도 2) 목표 3) 위치
    """
    print("=" * 60)
    print("🎵 음악 추천 엔진 (우선순위 기반)")
    print("=" * 60)
    print(f"📍 위치: {location} (3순위)")
    print(f"🎯 목표: {goal} (2순위)")
    print(f"🔊 소음: {decibel} (1순위 - 최우선)")
    print(f"⭐ 선호 아티스트: {', '.join(preferred_artists)} (20% 필수)")
    
    if preferred_genres:
        print(f"🎼 선호 장르: {', '.join(preferred_genres)}")
    
    print("=" * 60)
    
    # 초기 상태
    initial_state = {
        "location": location,
        "goal": goal,
        "decibel": decibel,
        "preferred_artists": preferred_artists,
        "preferred_genres": preferred_genres or [],
        "artist_persona": None,
        "ai_recommended_genres": None,  # 🆕
        "ai_genre_reasoning": None,  # 🆕
        "search_queries": None,
        "candidate_tracks": [],
        "preference_tracks": [],
        "selected_tracks": [],
        "final_tracks": [],
        "recommendations": None,
        "iteration_count": 0,
        "validation_feedback": None,
        "quality_validation": None
    }
    
    # 그래프 실행
    app = create_recommendation_graph()
    
    try:
        final_state = app.invoke(initial_state)
        
        print("\n" + "=" * 60)
        print("✅ 추천 완료!")
        print("=" * 60)
        
        result = {
            "final_tracks": final_state["final_tracks"],
            "recommendations": final_state["recommendations"],
            "ai_recommended_genres": final_state["ai_recommended_genres"],  # 🆕
            "iteration_count": final_state["iteration_count"],
            "quality_validation": final_state["quality_validation"],
            "artist_persona": final_state["artist_persona"]
        }
        
        # 결과 출력
        print(f"\n🤖 AI 추천 장르: {', '.join(result['ai_recommended_genres'])}")
        print(f"🔄 반복 횟수: {result['iteration_count']}")
        
        if result['quality_validation']:
            qv = result['quality_validation']
            print(f"\n⭐ 품질 점수:")
            print(f"   - 다양성: {qv.diversity_score:.2f}")
            print(f"   - 선호 아티스트: {qv.preferred_artist_ratio:.2%} (목표: 20%)")
            print(f"   - 한국 노래: {qv.korean_tracks_count}곡 (목표: 5곡)")
            print(f"   - 신곡 수: {qv.recent_tracks_count}곡 (기준: 2곡)")
            pop_dist = qv.popularity_distribution
            print(f"   - 인기도 분포: 높음 {pop_dist.high}, 중간 {pop_dist.medium}, 낮음 {pop_dist.low}")
        
        print(f"\n🎵 추천 곡 (10곡):")  # 🔧 5곡 → 10곡
        preferred_set = set(preferred_artists)
        for i, track in enumerate(result['final_tracks'], 1):
            is_preferred = any(
                artist.name in preferred_set 
                for artist in track.artists
            )
            prefix = "⭐" if is_preferred else "  "
            
            print(f"\n{i}. {prefix} {track.name}")
            print(f"     아티스트: {track.get_artist_names()}")
            print(f"     앨범: {track.album_name}")
            print(f"     발매: {track.release_date}")
            
            if result['recommendations']:
                for rec in result['recommendations'].recommendations:
                    if rec.track_id == track.id:
                        print(f"     💡 {rec.reason}")
                        break
        
        return result
    
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        raise


def visualize_graph():
    """그래프 구조 시각화"""
    graph_structure = """
    우선순위 기반 추천 시스템:
    
    START
      ↓
    [1] analyze_preference (선호 분석)
      ↓
    [2] context_analysis (상황 분석 & AI 장르 추천) 🆕
      ↓                        ↑
    [3] search_query_generator (검색 쿼리) 🆕  │
      ↓                                      │
    [4] tools (Spotify 검색)                 │
      ↓                                      │
    [5] preference_search (선호 아티스트)      │
      ↓                                      │
    [6] selection (5곡 선택 - 20% 필수)       │
      ↓                                      │
    [7] remix_track_filter (필터링)          │
      ↓                                      │
    [8] quality_validator (품질 검증)         │
      ├─ 통과 ─→ [9] generate_reason ─→ END │
      └─ 실패 ─→ 피드백 ─────────────────────┘
    
    우선순위:
    1순위: 소음도 (가청력과 직결)
    2순위: 목표 (행동 결정)
    3순위: 위치 (분위기 보정)
    
    특징:
    - AI가 상황 분석 후 장르 추천
    - 사용자 선호 장르와 타협
    - 선호 아티스트 20% 필수 포함
    """
    print(graph_structure)


if __name__ == "__main__":
    visualize_graph()
    
    print("\n=== 테스트 실행 ===")
    test_result = run_recommendation(
        location="library",
        goal="focus",
        decibel="quiet",
        preferred_artists=["BTS", "Stray Kids"],
        preferred_genres=["k-pop", "hip hop"]
    )
    
    print("\n✅ 테스트 완료!")