"""
데이터 모델 - 우선순위 기반 시스템
AI 추천 장르 필드 추가
"""
from typing import List, Optional, TypedDict
from pydantic import BaseModel, Field


# === Spotify 데이터 모델 ===
class SpotifyArtist(BaseModel):
    id: str
    name: str
    genres: List[str] = []

class SpotifyTrack(BaseModel):
    id: str
    name: str
    artists: List[SpotifyArtist]
    album_name: str
    release_date: str
    duration_ms: int
    popularity: int
    preview_url: Optional[str] = None
    external_url: str
    
    def get_artist_names(self) -> str:
        return ", ".join([artist.name for artist in self.artists])


# === LLM 출력 모델 ===
class ArtistPersona(BaseModel):
    dominant_genres: List[str] = Field(description="주요 장르 (최대 3개)")
    music_characteristics: List[str] = Field(description="음악 특성")
    similar_artists: List[str] = Field(description="유사 아티스트")
    summary: str = Field(description="종합 분석")

class SearchQuery(BaseModel):
    query: str = Field(description="Spotify 검색 쿼리")
    rationale: str = Field(description="검색 의도")

class ContextSearchQueries(BaseModel):
    queries: List[SearchQuery] = Field(description="8개의 검색 쿼리")  # 🔧 5개 → 8개

class TrackSelection(BaseModel):
    track_id: str = Field(description="Spotify 트랙 ID")
    selection_reason: str = Field(description="선택 이유")

class FinalSelection(BaseModel):
    selected_tracks: List[TrackSelection] = Field(description="선택된 10개 트랙")  # 🔧 5개 → 10개

class PopularityDistribution(BaseModel):
    """인기도 분포"""
    high: int = Field(default=0, description="높은 인기도 (80-100)")
    medium: int = Field(default=0, description="중간 인기도 (50-79)")
    low: int = Field(default=0, description="낮은 인기도 (10-49)")

class QualityValidation(BaseModel):
    is_valid: bool = Field(description="검증 통과 여부")
    diversity_score: float = Field(description="다양성 점수")
    preferred_artist_ratio: float = Field(description="선호 아티스트 비율")
    recent_tracks_count: int = Field(description="신곡 개수")
    korean_tracks_count: int = Field(default=0, description="한국 노래 개수")
    popularity_distribution: PopularityDistribution = Field(
        default_factory=PopularityDistribution,
        description="인기도 분포"
    )  # 🔧 dict → PopularityDistribution
    feedback: Optional[str] = Field(default=None, description="개선 피드백")

class RecommendationReason(BaseModel):
    track_id: str
    reason: str = Field(description="추천 이유")

class FinalRecommendations(BaseModel):
    recommendations: List[RecommendationReason]


# === LangGraph State ===
class AgentState(TypedDict):
    # 사용자 입력
    location: str
    goal: str
    decibel: str
    preferred_artists: List[str]
    preferred_genres: List[str]
    
    # 분석 결과
    artist_persona: Optional[ArtistPersona]
    ai_recommended_genres: Optional[List[str]]  # 🆕 AI 추천 장르
    ai_genre_reasoning: Optional[str]  # 🆕 AI 추천 이유
    search_queries: Optional[List[SearchQuery]]
    
    # 트랙 데이터
    candidate_tracks: List[SpotifyTrack]
    preference_tracks: List[SpotifyTrack]
    selected_tracks: List[SpotifyTrack]
    final_tracks: List[SpotifyTrack]
    
    # 추천 이유
    recommendations: Optional[FinalRecommendations]
    
    # 순환 제어
    iteration_count: int
    validation_feedback: Optional[str]
    quality_validation: Optional[QualityValidation]


# === API 요청/응답 모델 ===
class RecommendationRequest(BaseModel):
    location: str = Field(
        description="장소",
        examples=["home", "gym", "cafe"]
    )
    goal: str = Field(
        description="목표",
        examples=["focus", "relax", "active"]
    )
    decibel: str = Field(
        description="소음 레벨",
        examples=["quiet", "moderate", "loud"]
    )
    preferred_artists: List[str] = Field(
        description="선호 아티스트 (3-5개 권장)",
        min_length=1,
        max_length=10
    )
    preferred_genres: List[str] = Field(
        description="선호 장르 (3개 권장)",
        default=[],
        max_length=5
    )

class TrackRecommendation(BaseModel):
    track_id: str
    track_name: str
    artists: str
    album_name: str
    release_date: str
    spotify_url: str
    preview_url: Optional[str]
    reason: str

class RecommendationResponse(BaseModel):
    recommendations: List[TrackRecommendation]
    context_summary: str = Field(description="추천 상황 요약")
    ai_recommended_genres: List[str] = Field(description="AI 추천 장르")  # 🆕
    iteration_count: int = Field(description="반복 횟수")
    quality_scores: dict = Field(description="품질 지표")


if __name__ == "__main__":
    request = RecommendationRequest(
        location="library",
        goal="focus",
        decibel="quiet",
        preferred_artists=["BTS", "Stray Kids"],
        preferred_genres=["k-pop", "hip hop"]
    )
    print(f"상황: {request.location} / {request.goal} / {request.decibel}")
    print(f"선호: {request.preferred_artists}")
    print(f"장르: {request.preferred_genres}")