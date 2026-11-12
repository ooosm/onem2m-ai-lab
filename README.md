# 시계열 날씨 예측 실습 — 로컬 mobius4 연동

원격(세종대) Mobius 대신 **내 PC의 mobius4**에 학습·검증 데이터를 넣고, 노트북이 그 데이터를
읽어 LSTM 모델을 학습합니다.

## 받은 파일

| 파일 | 하는 일 |
|---|---|
| `seattle-weather.csv` | 데이터(Kaggle — Seattle 2012~2015, 1,461일) |
| `load_to_mobius4.py` | CSV를 mobius4 리소스로 만들고, 제대로 들어갔는지 스스로 검증 |
| `train_model_local.ipynb` | 실습 노트북(원격판에서 주소·AE 이름·헤더만 바꾼 것) |

## 준비물

- mobius4 **v4.15.1 이상** — 그 이전 버전은 데이터 순서가 보장되지 않습니다
- Python 패키지: `torch`(1.13 이상), `scikit-learn`(1.2 이상), `numpy`, `requests`, 그리고 Jupyter

## 1단계 — mobius4 설정 한 줄 추가 후 재기동

`config/local.json`의 `"cse"` 블록에 아래 한 줄을 넣고 **mobius4를 다시 띄웁니다.**

```json
"discovery_limit": 2000,
```

> **왜 필요한가** — 노트북은 컨테이너의 데이터를 한 번에 목록으로 받아 옵니다. mobius4는
> 기본으로 **200개까지만** 돌려주는데, 학습 데이터는 컨테이너당 1,096개입니다. 이 설정 없이는
> **오류 없이 200개만 받아 학습**하게 됩니다.

## 2단계 — 내 관리자 신원 확인

같은 파일 `config/local.json`의 `"cse"` 블록에서 `"admin"` 값을 확인합니다. 예: `"admin": "SM2"`
→ 내 관리자 신원은 `SM2`. 아래 3·4단계에서 이 값을 씁니다.

## 3단계 — 데이터 적재

세 파일을 한 폴더에 두고, 그 폴더에서 실행합니다. `<내관리자>` 자리에 2단계의 값을 넣습니다.

```bash
python load_to_mobius4.py seattle-weather.csv --dry-run                # 무엇을 만들지 미리 보기
python load_to_mobius4.py seattle-weather.csv --admin <내관리자>      # 실제 적재 + 자동 검증
```

마지막에 아래처럼 8줄이 모두 ✅이고 `검증 통과`가 나오면 됩니다.

```
  ✅ TS-train/precipitation_sensor: 1096/1096개, 첫 항목 날짜 2012-01-01 (기대 2012-01-01)
  ...
  ✅ TS-test/ground_truth: 365/365개, 첫 항목 날짜 2015-01-01 (기대 2015-01-01)
검증 통과 — 노트북을 실행해도 됩니다.
```

만들어지는 리소스 트리(노트북이 읽는 그대로):

```
/Mobius
├── TS-train   (2012-01-01 ~ 2014-12-31, 학습용)
│   ├── precipitation_sensor   cin 1,096개  {"date", "precipitation"}
│   ├── temperature_sensor     cin 1,096개  {"date", "temp_max", "temp_min"}
│   ├── wind_sensor            cin 1,096개  {"date", "wind"}
│   └── ground_truth           cin 1,096개  {"date", "weather"}   ← 정답(sun·rain·drizzle·fog·snow)
└── TS-test    (2015-01-01 ~ 2015-12-31, 검증용) — 같은 구조, 각 365개
```

> 학습/검증은 **노트북이 나누지 않습니다.** 어느 AE에 들어 있느냐로 정해지며, 위 기간으로
> 나눠 넣습니다.

## 4단계 — 노트북 실행

`train_model_local.ipynb`를 열고, 첫 셀 위쪽의 **이 한 줄만** 2단계의 값으로 바꾼 뒤 실행합니다.

```python
ADMIN_ORIGIN       = "SM2"     # ← 내 관리자 신원으로
```

`[RESULT] Test Accuracy: 0.6...` 이 나오면 끝입니다(학습할 때마다 소수점 아래가 조금 달라질 수 있습니다).

## 잘 안 될 때

| 증상 | 원인 | 해결 |
|---|---|---|
| 적재 검증에서 개수가 **정확히 200** | 1단계 설정이 반영되지 않음 | `local.json` 확인 후 mobius4 재기동 |
| 적재 검증에서 첫 날짜가 2014-12-31 / 2015-12-31 | mobius4가 v4.15.1보다 오래됨 | mobius4 업데이트 |
| 노트북이 `수신 완료: 0건` | `ADMIN_ORIGIN`이 내 관리자 신원과 다름 | 2단계 값으로 수정 |
| 적재 시 `TS-train가 이미 있다`로 멈춤 | 이미 적재함 | 그대로 노트북 실행. 다시 넣으려면 두 AE를 먼저 삭제 |
| 데이터만 다시 확인하고 싶음 | — | `python load_to_mobius4.py seattle-weather.csv --admin <내관리자> --verify-only` |

## 출처와 라이선스

- **노트북** — [seslabSJU/sejong_iotclass](https://github.com/seslabSJU/sejong_iotclass)의
  `For_Training_Practice/TimeSeries/train_model.ipynb`를 고친 것입니다. 원본은 MIT 라이선스
  (© 2025 Autonomous Intelligent System Lab)이며 전문은 [`LICENSE-sejong_iotclass`](LICENSE-sejong_iotclass)에 있습니다.
  바꾼 곳은 노트북 첫 셀 맨 위 주석에 적어 두었습니다.
- **데이터** — Kaggle "WEATHER PREDICTION"(`seattle-weather.csv`). 같은 데이터가
  [vega-datasets](https://github.com/vega/vega-datasets)에도 있으며, 두 사본의 내용(1,461행 전부)이
  같음을 확인했습니다(줄바꿈 방식만 다름).
