"""
FastAPI REST API 서버 - 우선순위 기반 시스템
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import (
    validate_config,
    LOCATIONS,
    GOALS,
    DECIBEL_LEVELS,
    AVAILABLE_GENRES,
    SCENARIO_PRESETS,
    PREFERRED_ARTIST_TRACK_RATIO
)
from models import (
    RecommendationRequest,
    RecommendationResponse,
    TrackRecommendation
)
from graph import run_recommendation

app = FastAPI(
    title="상황 기반 음악 추천 API",
    description="우선순위: 1)소음도 2)목표 3)위치 | 선호 아티스트 20% 필수",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    try:
        validate_config()
        print("✅ 서버 시작 완료")
        print(f"🎯 우선순위: 1)소음 2)목표 3)위치")
        print(f"⭐ 선호 아티스트: {PREFERRED_ARTIST_TRACK_RATIO*100}% 필수")
    except Exception as e:
        print(f"❌ 설정 오류: {str(e)}")
        raise


@app.get("/")
async def root():
    return {
        "message": "상황 기반 음악 추천 API",
        "version": "2.0.0",
        "priority_system": {
            "1st": "소음도 (noise_db)",
            "2nd": "목표 (behavior)",
            "3rd": "위치 (location)"
        },
        "features": [
            "AI 추천 장르 생성",
            "사용자 선호 장르와 타협",
            "선호 아티스트 20% 필수 포함",
            "예외 상황 대처"
        ],
        "endpoints": {
            "POST /recommend": "음악 추천",
            "GET /contexts": "컨텍스트 조회",
            "GET /genres": "장르 목록",
            "GET /scenarios": "시나리오 프리셋"
        }
    }


@app.get("/contexts")
async def get_contexts():
    """컨텍스트 옵션 조회"""
    return {
        "locations": LOCATIONS,
        "goals": GOALS,
        "decibel_levels": DECIBEL_LEVELS,
        "available_genres": AVAILABLE_GENRES,
        "priority": {
            "1st": "decibel (소음도) - 가장 중요",
            "2nd": "goal (목표)",
            "3rd": "location (위치)"
        },
        "examples": [
            {
                "name": "도서관 집중",
                "location": "library",
                "goal": "focus",
                "decibel": "quiet",
                "preferred_artists": ["Yiruma", "Ludovico Einaudi"],
                "preferred_genres": ["classical", "ambient"]
            },
            {
                "name": "공원 운동",
                "location": "park",
                "goal": "active",
                "decibel": "moderate",
                "preferred_artists": ["BTS", "Stray Kids"],
                "preferred_genres": ["k-pop", "edm"]
            },
            {
                "name": "이동 중 스트레스 해소",
                "location": "moving",
                "goal": "neutral",
                "decibel": "loud",
                "preferred_artists": ["Taylor Swift", "Ariana Grande"],
                "preferred_genres": ["pop", "upbeat"]
            }
        ]
    }


@app.get("/genres")
async def get_genres():
    """장르 목록"""
    return {
        "genres": AVAILABLE_GENRES,
        "total_count": len(AVAILABLE_GENRES),
        "note": "AI가 상황을 분석하여 최적 장르를 추천하고, 사용자 선호 장르와 타협합니다."
    }


@app.get("/scenarios")
async def get_scenarios():
    """일반적인 시나리오 프리셋"""
    return {
        "scenarios": SCENARIO_PRESETS,
        "note": "일반적인 상황별 최적 설정입니다. 예외 상황도 자동으로 처리됩니다."
    }


@app.post("/recommend", response_model=RecommendationResponse)
async def recommend_music(request: RecommendationRequest):
    """
    음악 추천 실행
    
    우선순위:
    1. 소음도 (decibel) - 가청력과 직결
    2. 목표 (goal) - 행동 결정
    3. 위치 (location) - 분위기 보정
    """
    try:
        # 입력 검증
        if request.location not in LOCATIONS:
            raise HTTPException(
                status_code=400,
                detail=f"유효하지 않은 장소입니다. 가능: {LOCATIONS}"
            )
        
        if request.goal not in GOALS:
            raise HTTPException(
                status_code=400,
                detail=f"유효하지 않은 목표입니다. 가능: {GOALS}"
            )
        
        if request.decibel not in DECIBEL_LEVELS:
            raise HTTPException(
                status_code=400,
                detail=f"유효하지 않은 소음 레벨입니다. 가능: {DECIBEL_LEVELS}"
            )
        
        if len(request.preferred_artists) < 1:
            raise HTTPException(
                status_code=400,
                detail="최소 1명의 선호 아티스트가 필요합니다."
            )
        
        # 추천 실행
        print(f"\n{'='*60}")
        print(f"📋 추천 요청")
        print(f"   소음(1순위): {request.decibel}")
        print(f"   목표(2순위): {request.goal}")
        print(f"   위치(3순위): {request.location}")
        print(f"{'='*60}")
        
        result = run_recommendation(
            location=request.location,
            goal=request.goal,
            decibel=request.decibel,
            preferred_artists=request.preferred_artists,
            preferred_genres=request.preferred_genres
        )
        
        # 응답 생성
        recommendations = []
        preferred_set = set(request.preferred_artists)
        
        for track in result["final_tracks"]:
            is_preferred = any(
                artist.name in preferred_set
                for artist in track.artists
            )
            
            reason = ""
            if result["recommendations"]:
                for rec in result["recommendations"].recommendations:
                    if rec.track_id == track.id:
                        reason = rec.reason
                        if is_preferred:
                            reason = f"⭐ 선호 아티스트 | {reason}"
                        break
            
            recommendations.append(
                TrackRecommendation(
                    track_id=track.id,
                    track_name=track.name,
                    artists=track.get_artist_names(),
                    album_name=track.album_name,
                    release_date=track.release_date,
                    spotify_url=track.external_url,
                    preview_url=track.preview_url,
                    reason=reason
                )
            )
        
        # 품질 점수
        quality_scores = {}
        if result["quality_validation"]:
            qv = result["quality_validation"]
            pop_dist = qv.popularity_distribution
            quality_scores = {
                "diversity_score": qv.diversity_score,
                "preferred_artist_ratio": qv.preferred_artist_ratio,
                "recent_tracks_count": qv.recent_tracks_count,
                "is_valid": qv.is_valid,
                "korean_tracks_count": qv.korean_tracks_count,  # 🔧 추가
                "popularity_distribution": {  # 🔧 dict로 변환
                    "high": pop_dist.high,
                    "medium": pop_dist.medium,
                    "low": pop_dist.low
                }
            }
        
        # 컨텍스트 요약
        context_summary = (
            f"🔊 소음: {request.decibel} | "
            f"🎯 목표: {request.goal} | "
            f"📍 위치: {request.location}"
        )
        
        return RecommendationResponse(
            recommendations=recommendations,
            context_summary=context_summary,
            ai_recommended_genres=result["ai_recommended_genres"],
            iteration_count=result["iteration_count"],
            quality_scores=quality_scores
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 추천 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"추천 중 오류가 발생했습니다: {str(e)}"
        )


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "system": "priority-based recommendation",
        "priority": ["decibel", "goal", "location"],
        "preferred_artist_ratio": f"{PREFERRED_ARTIST_TRACK_RATIO*100}%"
    }


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 상황 기반 음악 추천 API 서버")
    print("=" * 60)
    print("우선순위: 1)소음 2)목표 3)위치")
    print(f"선호 아티스트: {PREFERRED_ARTIST_TRACK_RATIO*100}% 필수")
    print("=" * 60)
    print("URL: http://localhost:8000")
    print("문서: http://localhost:8000/docs")
    print("시나리오: http://localhost:8000/scenarios")
    print("=" * 60)
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )