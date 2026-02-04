"""
API 테스트 클라이언트 - 우선순위 기반 시스템
"""
import requests
import json
from typing import Dict, List

API_URL = "http://localhost:8000"


def print_section(title: str):
    """섹션 구분선 출력"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def get_contexts():
    """사용 가능한 컨텍스트 조회"""
    print_section("📋 사용 가능한 컨텍스트")
    
    response = requests.get(f"{API_URL}/contexts")
    data = response.json()
    
    print("\n🎯 우선순위:")
    priority = data.get('priority', {})
    print(f"  1순위: {priority.get('1st', 'N/A')}")
    print(f"  2순위: {priority.get('2nd', 'N/A')}")
    print(f"  3순위: {priority.get('3rd', 'N/A')}")
    
    print("\n📍 위치 옵션:")
    print(f"  {', '.join(data['locations'])}")
    
    print("\n🎯 목표 옵션:")
    print(f"  {', '.join(data['goals'])}")
    
    print("\n🔊 소음 레벨 옵션:")
    print(f"  {', '.join(data['decibel_levels'])}")
    
    print("\n💡 예시:")
    for i, example in enumerate(data['examples'], 1):
        print(f"\n{i}. {example['name']}")
        print(f"   📍 {example['location']} | 🎯 {example['goal']} | 🔊 {example['decibel']}")
        print(f"   ⭐ 아티스트: {', '.join(example['preferred_artists'])}")
        print(f"   🎼 장르: {', '.join(example.get('preferred_genres', []))}")


def get_scenarios():
    """시나리오 프리셋 조회"""
    print_section("🎬 시나리오 프리셋")
    
    response = requests.get(f"{API_URL}/scenarios")
    data = response.json()
    
    print(f"\n{data.get('note', '')}\n")
    
    scenarios = data.get('scenarios', {})
    for i, (key, scenario) in enumerate(scenarios.items(), 1):
        print(f"{i}. {scenario['description']}")
        print(f"   📍 {scenario['location']} | 🎯 {scenario['goal']} | 🔊 {scenario['decibel']}")
        print(f"   🎼 최적 장르: {', '.join(scenario['optimal_genres'])}")
        print()


def recommend_music(
    location: str,
    goal: str,
    decibel: str,
    preferred_artists: List[str],
    preferred_genres: List[str] = None
) -> Dict:
    """음악 추천 요청"""
    print_section(f"🎵 음악 추천 요청")
    
    print(f"\n🔊 소음: {decibel} (1순위 - 최우선)")
    print(f"🎯 목표: {goal} (2순위)")
    print(f"📍 위치: {location} (3순위)")
    print(f"⭐ 선호 아티스트: {', '.join(preferred_artists)} (20% 필수)")
    
    if preferred_genres:
        print(f"🎼 선호 장르: {', '.join(preferred_genres)}")
    else:
        print(f"🎼 선호 장르: 지정 없음 (AI가 추천)")
    
    payload = {
        "location": location,
        "goal": goal,
        "decibel": decibel,
        "preferred_artists": preferred_artists,
        "preferred_genres": preferred_genres or []
    }
    
    print("\n⏳ AI가 상황을 분석하고 최적 장르를 추천 중...")
    print("   (30-60초 소요)")
    
    try:
        response = requests.post(
            f"{API_URL}/recommend",
            json=payload,
            timeout=120
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"\n❌ 오류: {response.status_code}")
            print(response.json())
            return None
    except requests.exceptions.Timeout:
        print("\n❌ 타임아웃: 서버 응답이 너무 오래 걸립니다.")
        return None
    except Exception as e:
        print(f"\n❌ 오류: {str(e)}")
        return None


def display_recommendations(result: Dict):
    """추천 결과 출력"""
    if not result:
        return
    
    print_section("✅ 추천 결과")
    
    # 컨텍스트 요약
    print(f"\n📝 {result['context_summary']}")
    
    # AI 추천 장르
    print(f"\n🤖 AI 추천 장르:")
    ai_genres = result.get('ai_recommended_genres', [])
    for i, genre in enumerate(ai_genres, 1):
        print(f"  {i}. {genre}")
    
    # 품질 점수
    if result.get('quality_scores'):
        scores = result['quality_scores']
        print(f"\n⭐ 품질 점수:")
        print(f"  - 다양성: {scores.get('diversity_score', 0):.2f}")
        print(f"  - 선호 아티스트: {scores.get('preferred_artist_ratio', 0):.1%} (목표: 20%)")
        print(f"  - 한국 노래: {scores.get('korean_tracks_count', 0)}곡 (목표: 5곡)")  # 🆕
        print(f"  - 신곡 수: {scores.get('recent_tracks_count', 0)}곡 (기준: 2곡)")
        
        # 🆕 인기도 분포
        pop_dist = scores.get('popularity_distribution', {})
        if pop_dist:
            print(f"  - 인기도 분포: 높음 {pop_dist.get('high', 0)}, 중간 {pop_dist.get('medium', 0)}, 낮음 {pop_dist.get('low', 0)}")
        
        print(f"  - 검증: {'통과 ✓' if scores.get('is_valid') else '미통과 ✗'}")
    
    print(f"\n🔄 반복 횟수: {result.get('iteration_count', 0)}")
    
    # 추천 곡
    recommendations = result.get('recommendations', [])
    print(f"\n🎵 추천 곡 {len(recommendations)}곡:\n")  # 🔧 동적으로 표시
    
    for i, rec in enumerate(recommendations, 1):
        # 선호 아티스트 표시
        is_preferred = rec['reason'].startswith('⭐')
        prefix = "⭐" if is_preferred else "  "
        
        print(f"{prefix} {i}. {rec['track_name']}")
        print(f"     🎤 {rec['artists']}")
        print(f"     💿 {rec['album_name']} ({rec['release_date']})")
        print(f"     🔗 {rec['spotify_url']}")
        print(f"     💡 {rec['reason']}")
        print()


# === 시나리오 테스트 함수들 ===

def test_scenario_focus():
    """시나리오 1: 도서관에서 집중"""
    print_section("📚 시나리오 1: 도서관에서 집중")
    print("조용한 환경에서 학습/업무에 집중")
    print("보컬이 적고 차분한 음악으로 집중력 향상")
    
    result = recommend_music(
        location="library",
        goal="focus",
        decibel="quiet",
        preferred_artists=["Yiruma", "Ludovico Einaudi", "Max Richter"],
        preferred_genres=["classical", "piano", "ambient"]
    )
    display_recommendations(result)


def test_scenario_active():
    """시나리오 2: 공원에서 운동"""
    print_section("🏃 시나리오 2: 공원에서 활동")
    print("야외에서 운동이나 활동적인 행동")
    print("높은 에너지와 리듬감으로 동기부여")
    
    result = recommend_music(
        location="park",
        goal="active",
        decibel="moderate",
        preferred_artists=["BTS", "Stray Kids", "SEVENTEEN"],
        preferred_genres=["k-pop", "edm", "pop"]
    )
    display_recommendations(result)


def test_scenario_relax():
    """시나리오 3: 집에서 휴식"""
    print_section("🛋️ 시나리오 3: 집에서 휴식")
    print("가장 낮은 에너지의 차분한 음악")
    
    result = recommend_music(
        location="home",
        goal="relax",
        decibel="quiet",
        preferred_artists=["Billie Eilish", "Clairo", "Lauv"],
        preferred_genres=["indie pop", "chill", "acoustic"]
    )
    display_recommendations(result)


def test_scenario_relief():
    """시나리오 4: 이동 중 스트레스 해소"""
    print_section("🚇 시나리오 4: 이동 중 스트레스 해소")
    print("높은 소음 속에서 기분 전환 필요")
    print("밝은 분위기와 높은 음압으로 소음 차단")
    
    result = recommend_music(
        location="moving",
        goal="neutral",
        decibel="loud",
        preferred_artists=["Taylor Swift", "Ariana Grande", "Dua Lipa"],
        preferred_genres=["pop", "dance pop", "upbeat"]
    )
    display_recommendations(result)


def test_scenario_sleep():
    """시나리오 5: 집에서 수면"""
    print_section("😴 시나리오 5: 집에서 수면 준비")
    print("어쿠스틱하고 부드러운 음악으로 수면 유도")
    
    result = recommend_music(
        location="home",
        goal="sleep",
        decibel="quiet",
        preferred_artists=["Norah Jones", "Ed Sheeran", "John Mayer"],
        preferred_genres=["acoustic", "soft pop", "folk"]
    )
    display_recommendations(result)


def test_scenario_consolation():
    """시나리오 6: 감정적 위로"""
    print_section("💙 시나리오 6: 감정적 위로")
    print("장소 무관, 감정적 위로가 필요한 상황")
    print("점차 밝아지는 분위기로 감정 회복")
    
    result = recommend_music(
        location="home",
        goal="consolation",
        decibel="moderate",
        preferred_artists=["Adele", "Sam Smith", "Lewis Capaldi"],
        preferred_genres=["ballad", "soul", "emotional"]
    )
    display_recommendations(result)


def test_scenario_gym():
    """시나리오 7: 헬스장에서 운동"""
    print_section("💪 시나리오 7: 헬스장에서 운동")
    print("높은 에너지와 강렬한 비트")
    
    result = recommend_music(
        location="gym",
        goal="active",
        decibel="loud",
        preferred_artists=["Travis Scott", "Future", "21 Savage"],
        preferred_genres=["hip hop", "trap", "workout"]
    )
    display_recommendations(result)


def test_exception_case():
    """예외 상황 테스트: 충돌하는 요구사항"""
    print_section("⚠️ 예외 상황: 조용한 환경 + 메탈 선호")
    print("AI가 어떻게 타협하는지 확인")
    
    result = recommend_music(
        location="library",
        goal="focus",
        decibel="quiet",
        preferred_artists=["Metallica", "Iron Maiden", "Slipknot"],
        preferred_genres=["metal", "rock", "hard rock"]
    )
    
    print("\n🤔 AI 타협 전략:")
    print("   - 소음도(quiet)가 1순위 → metal/rock 제외")
    print("   - 대안 제시: 차분한 장르로 대체")
    print("   - 선호 아티스트: 발라드/어쿠스틱 버전 찾기")
    
    display_recommendations(result)


def test_custom_scenario():
    """사용자 정의 시나리오"""
    print_section("🎨 사용자 정의 추천")
    
    print("\n📋 사용 가능한 옵션:")
    print("위치: home, gym, co-working, library, cafe, moving, park")
    print("목표: focus, relax, active, sleep, anger, consolation, stabilization, neutral")
    print("소음: quiet, moderate, loud")
    
    print("\n💡 입력 예시:")
    print('  위치: cafe')
    print('  목표: focus')
    print('  소음: moderate')
    print('  아티스트: Lauv, LANY, The 1975')
    print('  장르: indie pop, alternative, electronic')
    
    try:
        location = input("\n📍 위치: ").strip()
        goal = input("🎯 목표: ").strip()
        decibel = input("🔊 소음: ").strip()
        artists_str = input("⭐ 선호 아티스트 (쉼표로 구분): ").strip()
        genres_str = input("🎼 선호 장르 (쉼표로 구분, Enter로 건너뛰기): ").strip()
        
        if not all([location, goal, decibel, artists_str]):
            print("\n❌ 필수 항목을 모두 입력해주세요.")
            return
        
        preferred_artists = [a.strip() for a in artists_str.split(",")]
        preferred_genres = [g.strip() for g in genres_str.split(",")] if genres_str else []
        
        result = recommend_music(
            location,
            goal,
            decibel,
            preferred_artists,
            preferred_genres
        )
        display_recommendations(result)
    
    except KeyboardInterrupt:
        print("\n\n❌ 취소되었습니다.")


def main():
    """메인 테스트 실행"""
    print_section("🎵 상황 기반 음악 추천 API 테스트")
    print("\n🎯 우선순위: 1)소음 2)목표 3)위치")
    print("⭐ 선호 아티스트 20% 필수 포함")
    print("🤖 AI가 상황 분석 후 최적 장르 추천")
    
    while True:
        print("\n" + "=" * 70)
        print("테스트 메뉴:")
        print("=" * 70)
        print("  [일반 시나리오]")
        print("  1. 📚 도서관에서 집중 (Focus)")
        print("  2. 🏃 공원에서 활동 (Active)")
        print("  3. 🛋️  집에서 휴식 (Relax)")
        print("  4. 🚇 이동 중 스트레스 해소 (Relief)")
        print("  5. 😴 집에서 수면 (Sleep)")
        print("  6. 💙 감정적 위로 (Consolation)")
        print("  7. 💪 헬스장 운동 (Gym)")
        print("\n  [시스템 정보]")
        print("  8. 📋 사용 가능한 컨텍스트")
        print("  9. 🎬 시나리오 프리셋 조회")
        print("\n  [고급 테스트]")
        print("  10. ⚠️  예외 상황 테스트")
        print("  11. 🎨 사용자 정의 추천")
        print("\n  0. 👋 종료")
        print("=" * 70)
        
        choice = input("\n선택: ").strip()
        
        if choice == "0":
            print("\n👋 테스트 종료")
            break
        elif choice == "1":
            test_scenario_focus()
        elif choice == "2":
            test_scenario_active()
        elif choice == "3":
            test_scenario_relax()
        elif choice == "4":
            test_scenario_relief()
        elif choice == "5":
            test_scenario_sleep()
        elif choice == "6":
            test_scenario_consolation()
        elif choice == "7":
            test_scenario_gym()
        elif choice == "8":
            get_contexts()
        elif choice == "9":
            get_scenarios()
        elif choice == "10":
            test_exception_case()
        elif choice == "11":
            test_custom_scenario()
        else:
            print("\n❌ 유효하지 않은 선택입니다.")
        
        input("\n⏎ 계속하려면 Enter를 누르세요...")


if __name__ == "__main__":
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print("\n" + "=" * 70)
            print("✅ API 서버 연결 성공")
            print("=" * 70)
            print(f"버전: {health['version']}")
            print(f"시스템: {health['system']}")
            print(f"우선순위: {' > '.join(health['priority'])}")
            print(f"선호 아티스트 비율: {health['preferred_artist_ratio']}")
            print("=" * 70)
            main()
        else:
            print("❌ API 서버 연결 실패")
    except requests.exceptions.ConnectionError:
        print("\n❌ API 서버에 연결할 수 없습니다.")
        print("   다음을 확인하세요:")
        print("   1. 서버가 실행 중인지: python server.py")
        print("   2. 포트가 8000인지 확인")
        print("   3. 방화벽 설정 확인")
    except Exception as e:
        print(f"\n❌ 오류: {str(e)}")