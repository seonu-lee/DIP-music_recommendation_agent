"""
Spotify API 클라이언트 - 음악 검색 및 데이터 수집
"""
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from typing import List, Optional
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor

from config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    CANDIDATE_TRACKS_COUNT
)
from models import SpotifyTrack, SpotifyArtist


class SpotifyClient:
    """Spotify Web API 클라이언트"""
    
    def __init__(self):
        """Spotify 클라이언트 초기화"""
        auth_manager = SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET
        )
        self.sp = spotipy.Spotify(auth_manager=auth_manager)
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    def search_tracks(
        self,
        query: str,
        limit: int = 10
    ) -> List[SpotifyTrack]:
        """
        트랙 검색
        
        Args:
            query: 검색 쿼리
            limit: 결과 개수
        
        Returns:
            검색된 트랙 리스트
        """
        try:
            results = self.sp.search(q=query, type='track', limit=limit)
            tracks = []
            
            for item in results['tracks']['items']:
                track = self._parse_track(item)
                if track:
                    tracks.append(track)
            
            return tracks
        
        except Exception as e:
            print(f"검색 오류 ({query}): {str(e)}")
            return []
    
    def search_artist_tracks(
        self,
        artist_name: str,
        limit: int = 10
    ) -> List[SpotifyTrack]:
        """
        특정 아티스트의 인기 트랙 검색
        
        Args:
            artist_name: 아티스트 이름
            limit: 결과 개수
        
        Returns:
            아티스트의 인기 트랙 리스트
        """
        try:
            # 아티스트 검색
            artist_results = self.sp.search(
                q=f'artist:{artist_name}',
                type='artist',
                limit=1
            )
            
            if not artist_results['artists']['items']:
                print(f"아티스트를 찾을 수 없음: {artist_name}")
                return []
            
            artist_id = artist_results['artists']['items'][0]['id']
            
            # 아티스트의 상위 트랙 가져오기
            top_tracks = self.sp.artist_top_tracks(artist_id)
            tracks = []
            
            for item in top_tracks['tracks'][:limit]:
                track = self._parse_track(item)
                if track:
                    tracks.append(track)
            
            return tracks
        
        except Exception as e:
            print(f"아티스트 검색 오류 ({artist_name}): {str(e)}")
            return []
    
    def get_artist_recent_tracks(
        self,
        artist_name: str,
        months: int = 48  #(4년)
    ) -> List[SpotifyTrack]:
        """
        아티스트의 최신 트랙 검색 (특정 기간 내)
        
        Args:
            artist_name: 아티스트 이름
            months: 검색할 최근 개월 수 (기본 48개월 = 4년)
        
        Returns:
            최신 트랙 리스트
        """
        try:
            # 아티스트 검색
            artist_results = self.sp.search(
                q=f'artist:{artist_name}',
                type='artist',
                limit=1
            )
            
            if not artist_results['artists']['items']:
                return []
            
            artist_id = artist_results['artists']['items'][0]['id']
            
            # 아티스트 앨범 검색
            albums = self.sp.artist_albums(
                artist_id,
                album_type='album,single',
                limit=20
            )
            
            # 최근 발매 날짜 계산
            cutoff_date = datetime.now() - timedelta(days=months * 30)
            recent_tracks = []
            
            for album in albums['items']:
                release_date = album['release_date']
                
                # 날짜 형식 처리 (YYYY, YYYY-MM, YYYY-MM-DD)
                try:
                    if len(release_date) == 4:
                        album_date = datetime.strptime(release_date, "%Y")
                    elif len(release_date) == 7:
                        album_date = datetime.strptime(release_date, "%Y-%m")
                    else:
                        album_date = datetime.strptime(release_date, "%Y-%m-%d")
                    
                    if album_date >= cutoff_date:
                        # 앨범 트랙 가져오기
                        album_tracks = self.sp.album_tracks(album['id'])
                        
                        for item in album_tracks['items'][:5]:
                            # 전체 트랙 정보 가져오기
                            full_track = self.sp.track(item['id'])
                            track = self._parse_track(full_track)
                            if track:
                                recent_tracks.append(track)
                
                except ValueError:
                    continue
            
            return recent_tracks[:10]
        
        except Exception as e:
            print(f"최신 트랙 검색 오류 ({artist_name}): {str(e)}")
            return []
    
    
    # spotify_client.py 내의 parallel_search 함수를 아래 코드로 교체하세요
    def parallel_search(
        self,
        queries: List[str],
        limit_per_query: int = 10
    ) -> List[SpotifyTrack]:
        """
        병렬 검색 실행 (동기 방식 내에서 안전하게 실행)
        """
        import concurrent.futures

        # 새로운 루프를 만들지 않고 ThreadPoolExecutor만 사용하여 동기적으로 처리합니다.
        all_tracks = []
        seen_ids = set()

        # ThreadPool을 사용하여 search_tracks를 병렬로 실행
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # 여러 쿼리를 동시에 실행
            future_to_query = {
                executor.submit(self.search_tracks, query, limit_per_query): query 
                for query in queries
            }
        
            for future in concurrent.futures.as_completed(future_to_query):
                try:
                    track_list = future.result()
                    for track in track_list:
                        if track.id not in seen_ids:
                            all_tracks.append(track)
                            seen_ids.add(track.id)
                except Exception as e:
                    print(f"병렬 검색 중 개별 쿼리 오류: {str(e)}")

        return all_tracks[:CANDIDATE_TRACKS_COUNT]
    
    def _parse_track(self, track_data: dict) -> Optional[SpotifyTrack]:
        """
        Spotify API 응답을 SpotifyTrack 모델로 변환
        
        Args:
            track_data: Spotify API 트랙 데이터
        
        Returns:
            SpotifyTrack 객체 또는 None
        """
        try:
            artists = [
                SpotifyArtist(
                    id=artist['id'],
                    name=artist['name'],
                    genres=[]
                )
                for artist in track_data['artists']
            ]
            
            return SpotifyTrack(
                id=track_data['id'],
                name=track_data['name'],
                artists=artists,
                album_name=track_data['album']['name'],
                release_date=track_data['album']['release_date'],
                duration_ms=track_data['duration_ms'],
                popularity=track_data['popularity'],
                preview_url=track_data.get('preview_url'),
                external_url=track_data['external_urls']['spotify']
            )
        
        except Exception as e:
            print(f"트랙 파싱 오류: {str(e)}")
            return None
    
    def get_track_by_id(self, track_id: str) -> Optional[SpotifyTrack]:
        """
        트랙 ID로 상세 정보 조회
        
        Args:
            track_id: Spotify 트랙 ID
        
        Returns:
            SpotifyTrack 객체 또는 None
        """
        try:
            track_data = self.sp.track(track_id)
            return self._parse_track(track_data)
        except Exception as e:
            print(f"트랙 조회 오류 ({track_id}): {str(e)}")
            return None


# 싱글톤 인스턴스
_spotify_client = None

def get_spotify_client() -> SpotifyClient:
    """Spotify 클라이언트 싱글톤 인스턴스 반환"""
    global _spotify_client
    if _spotify_client is None:
        _spotify_client = SpotifyClient()
    return _spotify_client


if __name__ == "__main__":
    # 테스트 코드
    client = get_spotify_client()
    
    # 단일 검색 테스트
    print("=== 단일 검색 테스트 ===")
    tracks = client.search_tracks("lo-fi study", limit=3)
    for track in tracks:
        print(f"{track.name} - {track.get_artist_names()}")
    
    # 아티스트 검색 테스트
    print("\n=== 아티스트 검색 테스트 ===")
    artist_tracks = client.search_artist_tracks("BTS", limit=3)
    for track in artist_tracks:
        print(f"{track.name} - {track.get_artist_names()}")
    
    # 최신 곡 검색 테스트
    print("\n=== 최신 곡 검색 테스트 ===")
    recent_tracks = client.get_artist_recent_tracks("Lauv", months=12)
    print(f"Lauv 최신 곡 {len(recent_tracks)}개")
    for track in recent_tracks[:3]:
        print(f"{track.name} ({track.release_date})")
    
    # 병렬 검색 테스트
    print("\n=== 병렬 검색 테스트 ===")
    queries = ["lo-fi focus", "ambient study", "chill concentration"]
    parallel_results = client.parallel_search(queries, limit_per_query=2)
    print(f"총 {len(parallel_results)}개 트랙 검색됨")
    for track in parallel_results[:5]:
        print(f"{track.name} - {track.get_artist_names()}")


