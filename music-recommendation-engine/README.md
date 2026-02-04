#안드로이드 앱 버전으로 사용하려면 코드를 변경해야하는지/ 현재는 웹 전용인지/그냥 로컬용인지
#tag:new는 트랙말고 앨범 서치만 가능함
#전부 4년이내 곡 아니여도 됨, 70%정도만 4년이내 곡
#선호아티스트가 모두 외국가수인경우 한국노래 50%를 만족하기 어려운 상황발생, 한국노래를 30%로 줄이고, 노드5 선호 아티스트 곡 검색 단계 처럼, 한국 노래 곡 검색 노드를 따로 만들어서 그 중 3곡은 최종추천에 반드시 포함되게 해야할듯
#피드백반영 후 생성된 쿼리도 문법에 맞춰 수정해야함
#지금 인기도(popularity)는 어떻게 반영되고 있는거?



#  상황 기반 음악 추천 시스템 


### 1. 컨텍스트 정의

**위치 (Location)**
```python
["home", "gym", "co-working", "library", "cafe", "moving", "park"]
```

**목표 (Goal)**
```python
["focus", "relax", "active", "sleep", 
 "anger", "consolation", "stabilization", "neutral"]
```

**소음 레벨 (Decibel)**
```python
["quiet", "moderate", "loud"]
```

---

##  추천 우선순위 시스템

### **1순위: 소음도 (Decibel)** - 가장 중요!
음악의 가청력과 직결되는 최우선 요소

**Quiet (조용함)**
- 에너지: 0.1-0.4 (매우 낮음)
- 키워드: soft, gentle, quiet, whisper, calm
- 템포: 60-100 BPM
- 보컬: 최소화 또는 인스트루멘탈

**Moderate (보통)**
- 에너지: 0.3-0.7 (중간)
- 키워드: moderate, balanced, comfortable
- 템포: 90-130 BPM
- 보컬: 자유

**Loud (시끄러움)**
- 에너지: 0.6-1.0 (높음)
- 키워드: powerful, energetic, intense, dynamic
- 템포: 120-180 BPM
- 보컬: 강력한 보컬 또는 헤비 인스트루멘탈

### **2순위: 목표 (Goal)**
사용자가 하고 싶은 행동 결정

| 목표 | 설명 | 추천 장르 | 에너지 |
|------|------|-----------|--------|
| **focus** | 집중력 향상 | lo-fi, ambient, classical | 낮음 |
| **relax** | 편안한 휴식 | acoustic, chill, jazz | 매우 낮음 |
| **active** | 활동적 행동 | edm, pop, rock, hip hop | 높음 |
| **sleep** | 수면 유도 | ambient, classical, meditation | 매우 낮음 |
| **anger** | 분노 해소 | rock, metal, aggressive | 높음 |
| **consolation** | 감정적 위로 | ballad, soul, emotional | 낮음→중간 |
| **stabilization** | 감정 안정 | ambient, soft rock, chill | 중간 |
| **neutral** | 일반 감상 | pop, indie, alternative | 중간 |

### **3순위: 위치 (Location)**
장소의 심리적 분위기를 보조적으로 반영

| 위치 | 분위기 | 에너지 조정 |
|------|--------|-------------|
| **library** | 조용하고 집중적 | -20% |
| **gym** | 동기부여 | +20% |
| **co-working** | 전문적 | -10% |
| **park** | 개방적, 상쾌 | +10% |
| **moving** | 역동적 | +10% |
| **home** | 편안함 | 0% |
| **cafe** | 아늑함 | 0% |

---

##  AI 장르 추천 시스템

### 작동 방식

1. **상황 분석**
   ```
   소음도(1순위) → 에너지/볼륨 범위 결정
   목표(2순위) → 분위기/리듬 결정
   위치(3순위) → 미세 조정
   ```

2. **AI 장르 추천**
   - AI가 상황에 최적인 장르 5개 추천
   - 예: quiet + focus + library → ["lo-fi", "ambient", "classical", "study music", "instrumental"]

3. **사용자 선호 장르와 타협**
   - 사용자 선호: ["k-pop", "hip hop"]
   - AI 추천: ["lo-fi", "ambient", "classical"]
   - 최종 타협: ["lo-fi hip hop", "chill", "ambient"]
   - 이유: K-pop은 너무 활기차서 조용한 환경에 부적합

### 예외 상황 대처

**예외 1: 충돌하는 요구사항**
```
입력: decibel=quiet, goal=focus
     선호 장르: ["metal", "rock"]

AI 처리:
- 소음도가 1순위 → metal/rock은 제외
- 대안 제시: ["acoustic", "soft rock", "ambient"]
- 이유: 조용한 환경에서는 차분한 음악 필수
```

**예외 2: 소음과 목표의 불일치**
```
입력: decibel=loud, goal=relax
     선호 장르: ["acoustic", "folk"]

AI 처리:
- 소음도가 1순위 → 소음 차단 위해 강한 음압 필요
- 타협안: ["chill electronic", "ambient electronic"]
- 이유: 전자음악으로 소음 차단하되 편안한 분위기 유지
```

**예외 3: 감정 목표 (consolation, anger)**
```
입력: goal=consolation
     위치/소음 관계없음

AI 처리:
- 목표가 감정적이므로 2순위가 1순위로 승격
- 추천: ["ballad", "soul", "emotional"]
- 점진적 밝아짐: 차분 → 희망적
```

---

##  선호 아티스트 20% 필수 포함

### 규칙
- **5곡 중 1곡(20%)은 반드시 선호 아티스트에서 선택**
- 단, 현재 상황(소음/목표/위치)에 적합한 곡이어야 함

### 예시

**시나리오: 도서관에서 집중**
```python
location = "library"
goal = "focus"
decibel = "quiet"
preferred_artists = ["BTS", "Stray Kids", "SEVENTEEN"]
```

**AI 처리:**
1. BTS/Stray Kids/SEVENTEEN의 전체 곡 중에서
2. **조용하고 집중에 도움되는 곡** 필터링
3. 예: BTS "Spring Day" (차분한 발라드)
4. 이 곡을 5곡 중 1곡으로 포함

**선택되지 않는 곡:**
- BTS "Dynamite" (너무 에너지가 높음)
- Stray Kids "God's Menu" (너무 강렬함)

---

##  일반적인 시나리오

### 1. Focus (집중) - 도서관, 조용함
```yaml
상황: library + focus + quiet
AI 추천: lo-fi, ambient, classical, study music
특징: 최소 보컬, 차분한 리듬
템포: 60-100 BPM
```

### 2. Active (활동) - 공원, 보통
```yaml
상황: park + active + moderate
AI 추천: pop, rock, edm, indie
특징: 높은 에너지, 강한 비트
템포: 120-150 BPM
```

### 3. Relax (휴식) - 집, 조용함
```yaml
상황: home + relax + quiet
AI 추천: acoustic, chill, jazz, soft pop
특징: 매우 낮은 에너지, 부드러움
템포: 60-90 BPM
```

### 4. Neutral (일반) - 이동 중, 시끄러움
```yaml
상황: moving + neutral + loud
AI 추천: pop, hip hop, electronic, upbeat
특징: 밝은 분위기, 높은 음압
템포: 110-140 BPM
목적: 소음 차단 + 기분 전환
```

### 5. Sleep (수면) - 집, 조용함
```yaml
상황: home + sleep + quiet
AI 추천: ambient, classical, meditation
특징: 극도로 낮은 에너지, 어쿠스틱
템포: 40-70 BPM
```

### 6. Consolation (위로) - 장소 무관
```yaml
상황: any + consolation + any
AI 추천: ballad, soul, emotional
특징: 감성적 보컬, 점진적 밝아짐
진행: 차분 → 희망적 → 밝음
```

### 7. Anger (분노) - 장소 무관
```yaml
상황: any + anger + any
AI 추천: rock, metal, aggressive electronic
특징: 강렬함, 카타르시스
템포: 140-180 BPM
```

---

##  워크플로우

```
1. analyze_preference
   - 사용자 아티스트/장르 분석
   
2. context_analysis 
   - 우선순위 기반 상황 분석
   - AI가 최적 장르 5개 추천
   - 사용자 선호와 타협
   
3. search_query_generator 
   - AI 추천 장르로 검색 쿼리 생성
   - 예: "lo-fi study beats", "ambient focus"
   
4. tools
   - Spotify API 병렬 검색
   
5. preference_search
   - 선호 아티스트의 곡 검색 (20% 용)
   
6. selection
   - 5곡 선택 (1곡은 선호 아티스트 필수)
   
7. remix_track_filter
   - 리믹스/라이브 필터링
   
8. quality_validator
   - 품질 검증
   - 선호 아티스트 20% 확인
   ├─ 통과 → 9번
   └─ 실패 → 3번으로 (재검색)
   
9. generate_reason
   - 우선순위 반영한 추천 이유
```

---

##  테스트 예시

### 테스트 1: 일반적인 상황
```python
recommend_music(
    location="library",
    goal="focus",
    decibel="quiet",
    preferred_artists=["Yiruma", "Ludovico Einaudi"],
    preferred_genres=["classical", "piano"]
)

# 예상 결과:
# AI 추천: ["classical", "piano", "ambient", "instrumental", "meditation"]
# 선호 아티스트 1곡: Yiruma - River Flows in You
# 나머지 4곡: 차분한 클래식/앰비언트
```

### 테스트 2: 예외 상황 (충돌)
```python
recommend_music(
    location="library",
    goal="focus",
    decibel="quiet",
    preferred_artists=["Metallica", "Slipknot"],
    preferred_genres=["metal", "rock"]
)

# AI 처리:
# - metal/rock은 소음도(quiet) 때문에 제외
# - 대안: ["acoustic", "soft rock", "ambient"]
# - 선호 아티스트: Metallica의 발라드 버전 곡 찾기
# - 예: "Nothing Else Matters" (Acoustic)
```

### 테스트 3: 감정 목표
```python
recommend_music(
    location="home",
    goal="consolation",
    decibel="moderate",
    preferred_artists=["Adele", "Sam Smith"],
    preferred_genres=["soul", "ballad"]
)

# AI 처리:
# - 감정 목표이므로 위로에 최적화
# - AI 추천: ["ballad", "soul", "emotional pop"]
# - 선호 아티스트 완벽 일치!
# - 점진적 밝아지는 플레이리스트
```

---

##  API 사용법

### 기본 요청
```bash
POST /recommend
Content-Type: application/json

{
  "location": "library",
  "goal": "focus",
  "decibel": "quiet",
  "preferred_artists": ["Lauv", "LANY"],
  "preferred_genres": ["indie pop", "alternative"]
}
```

### 응답
```json
{
  "recommendations": [...],
  "context_summary": " 소음: quiet |  목표: focus |  위치: library",
  "ai_recommended_genres": ["lo-fi", "indie pop", "ambient", "chill", "study"],
  "iteration_count": 1,
  "quality_scores": {
    "diversity_score": 0.8,
    "preferred_artist_ratio": 0.2,
    "recent_tracks_count": 3,
    "is_valid": true
  }
}
```

---

##  주요 특징

 **우선순위 기반 추천**
- 1순위: 소음도 (가청력)
- 2순위: 목표 (행동)
- 3순위: 위치 (분위기)

 **AI 장르 추천**
- 상황 분석 후 최적 장르 제안
- 사용자 선호와 지능적 타협

 **선호 아티스트 20% 필수**
- 5곡 중 1곡은 반드시 포함
- 단, 상황에 적합한 곡이어야 함

 **예외 상황 자동 대처**
- 충돌하는 요구사항 해결
- 감정 목표 특별 처리
- 일반/예외 모두 높은 품질

 **품질 검증 및 자동 재시도**
- 다양성, 선호도, 최신성 확인
- 실패 시 최대 3회 재시도

---

##  개발자 노트

### 수정된 파일
1. **config.py** - 컨텍스트, 우선순위 매트릭스, 시나리오
2. **models.py** - AI 추천 장르 필드 추가
3. **prompts.py** - 우선순위 기반 프롬프트
4. **nodes.py** - 새 노드 2개 (context_analysis, search_query_generator)
5. **graph.py** - 워크플로우 업데이트
6. **server.py** - API 엔드포인트 업데이트

### 실행 방법
```bash
python server.py
python test_client.py  # 테스트
```

