# 바꿔 API 영상 제작 실행

최신 결과는 [20초 전투 수정본](DUEL-V2.md)이다. 상대 얼굴과 긴 가는 무기를 수정해 6개 원본 클립을 생성하고, 원곡 2:50~3:10과 합성했다. 아래 35초 구성은 초기 계획이며, 실제 결과는 6초 첫 시험과 20초 수정본 두 가지다.

6개 시안을 Veo 3.1 Fast 720p로 생성한 뒤 원곡의 2:35~3:10과 합성하는 실행 절차다. 사용자 승인 범위인 첫 전투 SHOT 04만 6초로 1회 생성했고, 원곡의 2:50~2:56을 붙였다. [테스트 결과와 검수 내용](SHOT-04-TEST.md)을 확인할 수 있다. 나머지 장면과 전체 35초 영상은 아직 생성하지 않았다.

## 예상 비용

2026년 10월 17일 확인한 [Google 공식 API 요금](https://ai.google.dev/gemini-api/docs/pricing) 기준이다. Fast 720p의 출력 초당 요금은 US$0.10이다. 구독 또는 Flow 크레딧과 별도다.

| 장면 | 생성 원본 | 최종 사용 | 예상 API 요금 |
| --- | --- | --- | --- |
| 01 대치 | 6초 | 5초 | US$0.60 |
| 02 빼앗긴 이상 | 6초 | 5초 | US$0.60 |
| 03 칼자루 | 6초 | 5초 | US$0.60 |
| 04 무기 옆 시점 | 6초 | 6초 | US$0.60 |
| 05 전장 전경 | 8초 | 7초 | US$0.80 |
| 06 상대 반응 | 8초 | 7초 | US$0.80 |
| 합계 | 40초 | 35초 | US$4.00 |

세금과 환율 등은 별도일 수 있다. 이 금액은 각 장면을 한 번씩 생성하는 계획이며 추가 재생성은 포함하지 않는다. 실패나 시간 초과에 따른 자동 재생성은 하지 않는다.

## 키와 비용 한도

키는 flows/.env의 GEMINI_API_KEY에서 읽는다. 키를 명령줄 인수나 결과 파일에 기록하지 않는다. 기본 VEO_MAX_BUDGET_USD=0에서는 유료 생성이 실행되지 않는다. 별도로 합의한 금액을 명령의 --budget-usd로 지정하면 해당 실행 그룹의 누적 예약액을 검사한다.

## 비용을 쓰지 않는 확인

저장소 루트 PowerShell에서 실행한다.

```powershell
python flows/scripts/veo_pipeline.py quote
python flows/scripts/veo_pipeline.py quote --shots 04
```

## 비용 범위를 정한 뒤 실행

예시는 비용 범위를 합의한 뒤에만 실행한다.

```powershell
# 04번 한 컷만 먼저 시험하는 경우
python flows/scripts/veo_pipeline.py generate --shots 04 --budget-usd 0.60

# 전체 6컷의 누적 예산을 US$4로 정한 경우
python flows/scripts/veo_pipeline.py generate --budget-usd 4.00

# 생성 영상 6개가 준비되면 원곡과 합성
python flows/scripts/veo_pipeline.py render
```

먼저 04번을 생성하고 나중에 전체를 실행하면, 같은 결과는 다시 생성하지 않고 재사용한다. 진행 중 작업은 저장한 operation을 조회해 이어간다. 제출 결과가 불명확한 작업은 자동으로 재요청하지 않고 검토를 위해 멈춘다.

결과는 renders/veo-3.1-fast-720p/bakkuo-climax-155-190.mp4에 저장된다. 생성 영상이 없는 장면을 정지 이미지로 자동 대체하지 않는다. 원곡 2:50은 완성 영상의 15초 위치다. 첫 합성 후 화풍, 얼굴 가림, 손과 칼, 동작 및 음악의 전환을 검수한다.

## 필요한 패키지

이 작업 환경의 flows/.tools에 google-genai 2.31.0을 설치했다. 다른 환경에서는 아래처럼 준비한다.

```powershell
python -m pip install --target flows/.tools -r flows/requirements-video.txt
```

ffmpeg와 ffprobe도 실행 경로에 있어야 한다.
