"""
설정 파일 - 상황 기반 우선순위 시스템
우선순위: 1) 소음도 2) 목표 3) 위치
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 현재 config.py 파일이 있는 폴더의 .env 파일을 찾습니다.
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# API 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4.1-mini"
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# 추천 엔진 설정
MAX_ITERATIONS = 3
CANDIDATE_TRACKS_COUNT = 50  
FINAL_RECOMMENDATIONS_COUNT = 10  
PREFERRED_ARTIST_TRACK_RATIO = 0.2  # 선호 아티스트 곡 비율 20% (10곡 중 2곡)
KOREAN_TRACK_RATIO = 0.5  # 한국 노래 비율 50% (10곡 중 5곡)
RECENT_TRACK_RATIO = 0.2  # 신곡 비율 20% (10곡 중 2곡)
RECENT_YEARS = 4  # 신곡 기준 4년 이내 (2021-2025)

# === 상황 컨텍스트 (새로운 정의) ===
LOCATIONS = [
    "home", "gym", "co-working", "library", 
    "cafe", "moving", "park"
]

GOALS = [
    "focus", "relax", "active", "sleep",
    "anger", "consolation", "stabilization", "neutral"
]

DECIBEL_LEVELS = ["quiet", "moderate", "loud"]

# === 우선순위별 상황 매트릭스 ===
# 1순위: 소음도에 따른 음악 특성
DECIBEL_MUSIC_PROFILES = {
    "quiet": {
        "energy_range": (0.1, 0.4),  # 매우 낮은 에너지
        "volume_keywords": ["soft", "gentle", "quiet", "whisper", "calm"],
        "avoid_keywords": ["loud", "aggressive", "heavy", "intense"],
        "tempo_range": (60, 100),  # BPM
        "vocal_preference": "minimal or instrumental"
    },
    "moderate": {
        "energy_range": (0.3, 0.7),  # 중간 에너지
        "volume_keywords": ["moderate", "balanced", "comfortable", "easy listening"],
        "avoid_keywords": ["extreme", "overwhelming"],
        "tempo_range": (90, 130),
        "vocal_preference": "vocal or instrumental"
    },
    "loud": {
        "energy_range": (0.6, 1.0),  # 높은 에너지
        "volume_keywords": ["powerful", "energetic", "intense", "dynamic", "strong"],
        "avoid_keywords": ["quiet", "soft", "gentle"],
        "tempo_range": (120, 180),
        "vocal_preference": "powerful vocals or heavy instrumental"
    }
}

# 2순위: 목표(Behavior)에 따른 음악 특성
GOAL_MUSIC_PROFILES = {
    "focus": {
        "description": "집중력 향상을 위한 음악",
        "mood": ["focused", "concentrated", "productive", "clear"],
        "characteristics": ["minimal vocals", "steady rhythm", "non-distracting", "ambient"],
        "suggested_genres": ["lo-fi", "ambient", "classical", "instrumental", "study music"],
        "energy_level": "low-to-medium",
        "avoid": ["lyrics-heavy", "sudden changes", "aggressive"]
    },
    "relax": {
        "description": "편안한 휴식을 위한 음악",
        "mood": ["peaceful", "calm", "soothing", "comfortable"],
        "characteristics": ["slow tempo", "smooth", "gentle", "warm"],
        "suggested_genres": ["acoustic", "chill", "ambient", "jazz", "soft pop"],
        "energy_level": "very-low",
        "avoid": ["high energy", "aggressive", "fast tempo"]
    },
    "active": {
        "description": "활동적인 행동을 위한 음악",
        "mood": ["energetic", "motivating", "uplifting", "powerful"],
        "characteristics": ["high energy", "strong beat", "driving rhythm", "upbeat"],
        "suggested_genres": ["edm", "pop", "rock", "hip hop", "workout music"],
        "energy_level": "high",
        "avoid": ["slow", "depressing", "low energy"]
    },
    "sleep": {
        "description": "수면 유도를 위한 음악",
        "mood": ["sleepy", "dreamy", "tranquil", "serene"],
        "characteristics": ["very slow tempo", "minimal percussion", "soft", "acoustic"],
        "suggested_genres": ["ambient", "acoustic", "classical", "lullaby", "meditation"],
        "energy_level": "very-low",
        "avoid": ["vocals", "percussion", "anything stimulating"]
    },
    "anger": {
        "description": "분노 감정 해소를 위한 음악",
        "mood": ["cathartic", "releasing", "powerful", "intense"],
        "characteristics": ["strong rhythm", "powerful", "expressive", "dynamic"],
        "suggested_genres": ["rock", "metal", "hip hop", "aggressive electronic"],
        "energy_level": "high",
        "avoid": ["too calm", "boring"]
    },
    "consolation": {
        "description": "감정적 위로를 위한 음악",
        "mood": ["comforting", "empathetic", "warm", "hopeful"],
        "characteristics": ["emotional vocals", "gradual build-up", "uplifting progression"],
        "suggested_genres": ["ballad", "soul", "indie", "emotional pop"],
        "energy_level": "low-to-medium",
        "progression": "starts calm, gradually brightens"
    },
    "stabilization": {
        "description": "감정 안정화를 위한 음악",
        "mood": ["balanced", "stable", "grounding", "centered"],
        "characteristics": ["steady rhythm", "consistent", "reassuring", "predictable"],
        "suggested_genres": ["ambient", "soft rock", "acoustic", "chill"],
        "energy_level": "medium",
        "avoid": ["chaotic", "unpredictable"]
    },
    "neutral": {
        "description": "일반적인 음악 감상",
        "mood": ["enjoyable", "pleasant", "popular", "diverse"],
        "characteristics": ["catchy", "well-produced", "mainstream appeal"],
        "suggested_genres": ["pop", "indie", "r&b", "alternative"],
        "energy_level": "medium",
        "focus": "popularity and quality over specific mood"
    }
}

# 3순위: 위치에 따른 분위기 보정
LOCATION_MODIFIERS = {
    "home": {
        "atmosphere": "comfortable and personal",
        "modifier": "더 편안하고 개인적인",
        "adjust_energy": 0.0  # 에너지 조정 없음
    },
    "gym": {
        "atmosphere": "motivating and energetic",
        "modifier": "더 강렬하고 동기부여되는",
        "adjust_energy": +0.2  # 에너지 20% 상승
    },
    "co-working": {
        "atmosphere": "productive and professional",
        "modifier": "더 집중되고 전문적인",
        "adjust_energy": -0.1  # 약간 차분하게
    },
    "library": {
        "atmosphere": "quiet and focused",
        "modifier": "더 조용하고 집중적인",
        "adjust_energy": -0.2  # 에너지 20% 감소
    },
    "cafe": {
        "atmosphere": "cozy and social",
        "modifier": "더 아늑하고 사교적인",
        "adjust_energy": 0.0
    },
    "moving": {
        "atmosphere": "dynamic and changing",
        "modifier": "더 역동적이고 변화하는",
        "adjust_energy": +0.1  # 약간 활기있게
    },
    "park": {
        "atmosphere": "open and refreshing",
        "modifier": "더 개방적이고 상쾌한",
        "adjust_energy": +0.1
    }
}

# === 시나리오 프리셋 (일반적인 상황) ===
SCENARIO_PRESETS = {
    "library_focus_quiet": {
        "location": "library",
        "goal": "focus",
        "decibel": "quiet",
        "description": "도서관에서 학습/업무 집중",
        "optimal_genres": ["lo-fi", "classical", "ambient", "instrumental"]
    },
    "park_active_moderate": {
        "location": "park",
        "goal": "active",
        "decibel": "moderate",
        "description": "공원에서 운동이나 활동",
        "optimal_genres": ["pop", "rock", "edm", "indie"]
    },
    "home_relax_quiet": {
        "location": "home",
        "goal": "relax",
        "decibel": "quiet",
        "description": "집에서 편안하게 휴식",
        "optimal_genres": ["acoustic", "chill", "jazz", "soft pop"]
    },
    "moving_neutral_loud": {
        "location": "moving",
        "goal": "neutral",
        "decibel": "loud",
        "description": "교통 환경에서 기분 전환",
        "optimal_genres": ["pop", "hip hop", "electronic", "upbeat"]
    },
    "home_sleep_quiet": {
        "location": "home",
        "goal": "sleep",
        "decibel": "quiet",
        "description": "집에서 수면 준비",
        "optimal_genres": ["ambient", "acoustic", "classical", "meditation"]
    },
    "any_consolation_any": {
        "location": "any",
        "goal": "consolation",
        "decibel": "any",
        "description": "감정적 위로가 필요한 상황",
        "optimal_genres": ["ballad", "soul", "indie", "emotional"]
    },
    "any_neutral_moderate": {
        "location": "any",
        "goal": "neutral",
        "decibel": "moderate",
        "description": "일반적인 음악 감상",
        "optimal_genres": ["pop", "indie", "alternative", "r&b"]
    }
}

# 장르 목록
AVAILABLE_GENRES = [
    # 집중/공부
    "lo-fi", "lo-fi hip hop", "study music", "ambient", "classical", "instrumental",
    
    # 팝/메인스트림
    "pop", "k-pop", "indie pop", "synth-pop", "electropop",
    
    # 록
    "rock", "indie rock", "alternative rock", "punk rock", "pop rock", "metal",
    
    # 일렉트로닉
    "electronic", "edm", "house", "techno", "dubstep", "drum and bass",
    
    # 힙합/알앤비
    "hip hop", "rap", "r&b", "trap",
    
    # 재즈/블루스
    "jazz", "blues", "soul", "funk",
    
    # 차분한 음악
    "acoustic", "folk", "ballad", "chill", "meditation",
    
    # 기타
    "reggae", "latin", "world music", "country", "workout music"
]

# 품질 검증 기준
QUALITY_THRESHOLDS = {
    "min_diversity": 0.6,
    "min_preferred_ratio": 0.15,  # 20% 목표이지만 최소 15% (10곡 중 1.5곡)
    "min_recent_tracks": 2,  #  최소 신곡 2곡 (20%)
    "min_korean_tracks": 4,  #  최소 한국 노래 4곡 (40%)
}

# 인기도 분포 기준
POPULARITY_DISTRIBUTION = {
    "high": {"range": (80, 100), "ratio": 0.4, "count": 4},  # 10-8점대: 40%
    "medium": {"range": (50, 79), "ratio": 0.4, "count": 4},  # 7-5점대: 40%
    "low": {"range": (10, 49), "ratio": 0.2, "count": 2},  # 4-1점대: 20%
}

#  키워드 스팸 필터 (SEO형 제목 차단)
SPAM_KEYWORDS = [
    # 검색 유입용 키워드
    "집중 잘 되는", "공부할 때", "업무할 때", "일할 때",
    "잠 잘 때", "수면", "명상", "요가", "힐링",
    
    # 괄호 안 설명
    "(Lofi)", "(Lo-fi)", "(Study)", "(Relax)", "(Chill)",
    "(Sleep)", "(Work)", "(Focus)", "(Meditation)",
    
    # 모음/컬렉션
    "모음곡", "베스트", "BEST", "모음", "컬렉션",
    "playlist", "Playlist", "PLAYLIST",
    
    # 시간 표시
    "1시간", "2시간", "3시간", "10분", "30분",
    "1 hour", "2 hours", "3 hours",
    
    # 용도 명시
    "공부용", "작업용", "수면용", "명상용", "운동용",
    "for study", "for work", "for sleep", "for meditation",
]

#  한국 노래 판별 키워드
KOREAN_INDICATORS = [
    # 한국 레이블
    "YG", "SM", "JYP", "HYBE", "Kakao", "Genie",
    
    # 한국 아티스트 (일부)
    "BTS", "BLACKPINK", "아이유", "IU", "NewJeans",
    "Stray Kids", "TWICE", "EXO", "Red Velvet",
    "세븐틴", "SEVENTEEN", "NCT", "aespa",
    
    # 한글 포함 여부는 코드에서 별도 체크
]

# API 요청 설정
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
LOG_LEVEL = "INFO"

def validate_config():
    """설정 검증"""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise ValueError("Spotify API 키가 설정되지 않았습니다.")
    print("✓ 설정 검증 완료 (우선순위 기반 시스템)")

if __name__ == "__main__":
    validate_config()
    print(f"\n=== 상황 기반 추천 시스템 v2.0 ===")
    print(f"우선순위: 1) 소음도 2) 목표 3) 위치")
    print(f"\n장소 ({len(LOCATIONS)}개): {', '.join(LOCATIONS)}")
    print(f"목표 ({len(GOALS)}개): {', '.join(GOALS)}")
    print(f"소음 ({len(DECIBEL_LEVELS)}개): {', '.join(DECIBEL_LEVELS)}")
    print(f"\n추천 설정:")
    print(f"  - 총 추천 곡: {FINAL_RECOMMENDATIONS_COUNT}곡")
    print(f"  - 선호 아티스트: {PREFERRED_ARTIST_TRACK_RATIO*100}% (2곡)")
    print(f"  - 한국 노래: {KOREAN_TRACK_RATIO*100}% (5곡)")
    print(f"  - 신곡 (최근 {RECENT_YEARS}년): {RECENT_TRACK_RATIO*100}% (2곡)")
    print(f"\n인기도 분포:")
    for level, config in POPULARITY_DISTRIBUTION.items():
        print(f"  - {level}: {config['ratio']*100}% ({config['count']}곡)")