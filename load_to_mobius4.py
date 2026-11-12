"""Seattle Weather CSV → 로컬 mobius4 리소스 적재.

train_model_local.ipynb 가 읽는 모양 그대로 만든다:

    /Mobius/TS-train/{precipitation_sensor, temperature_sensor, wind_sensor, ground_truth}/cin...
    /Mobius/TS-test/ (같은 구조)

설계상 두 가지를 일부러 이렇게 했다.

1. cin을 **날짜 역순으로** 넣는다.
   mobius4는 discovery(fu=1&ty=4)를 **최신 생성순**으로 돌려준다(cse/hostingCSE.js의
   order_newest_first — cin은 부모 컨테이너의 stateTag 순). 노트북은 받은 순서를 시간
   순서로 쓰고(창 3개 → 다음 항목의 weather), 날짜는 읽고 버린다. 날짜순으로 넣으면 노트북은
   "뒤 3일로 전날을 맞히는" 문제를 풀게 된다. 역순으로 넣으면 최신 생성순 = 날짜 오름차순이
   되어 강의 의도(예보)대로 받는다. 같은 컨테이너 안에서는 반드시 순차로 넣어야 한다.

2. 자식 리소스는 **그 AE 자신의 AE-ID로** 만든다. AE는 From "S"로 등록해 CSE가 ID를 붙이게
   하고(두 AE가 같은 ID를 쓰면 충돌한다), 응답의 aei로 컨테이너·cin을 만든다. 노트북은
   관리자(--admin, 기본 SM2)로 읽는다.

사용:
    python load_to_mobius4.py <seattle-weather.csv> --dry-run   # 무엇을 만들지 보기만
    python load_to_mobius4.py <seattle-weather.csv>             # 실제 적재 + 검증
    python load_to_mobius4.py <seattle-weather.csv> --verify-only  # 이미 넣은 것만 검증

검증은 노트북과 **같은 방식**(관리자 Origin으로 fu=1&ty=4 discovery)으로 읽어
① 개수가 맞는지 ② 첫 항목이 가장 이른 날짜인지(=노트북이 과거→최근 순으로 받는지) 본다.
개수가 정확히 200이면 discovery_limit 설정이 아직 반영되지 않은 것이다.
"""
import argparse
import csv
import hashlib
import sys

import requests

CONTAINERS = {
    # 노트북의 CONTAINERS와 같은 이름. 값은 그 컨테이너의 con에 실을 CSV 열(date 제외).
    # 노트북은 필드 이름이 아니라 순서만 보므로, temp_max·temp_min 순서가 곧 특징 순서다.
    "precipitation_sensor": ["precipitation"],
    "temperature_sensor": ["temp_max", "temp_min"],
    "wind_sensor": ["wind"],
    "ground_truth": ["weather"],  # 문자열 라벨 — 노트북이 con['weather']로 꺼낸다
}
EXPECTED_COLUMNS = ["date", "precipitation", "temp_max", "temp_min", "wind", "weather"]


def headers(origin, ty=None):
    h = {
        "Accept": "application/json",
        "X-M2M-RI": "load",
        "X-M2M-Origin": origin,
        "X-M2M-RVI": "3",
    }
    if ty is not None:
        h["Content-Type"] = f"application/json;ty={ty}"
    return h


def post(url, origin, ty, body):
    r = requests.post(url, json=body, headers=headers(origin, ty), timeout=10)
    if r.status_code != 201:
        sys.exit(f"❌ 생성 실패 {url} (HTTP {r.status_code}): {r.text[:300]}")
    return r.json()


def con_of(row, cnt):
    con = {"date": row["date"]}
    for col in CONTAINERS[cnt]:
        con[col] = row[col] if col == "weather" else float(row[col])
    return con


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--base", default="http://localhost:7599/Mobius")
    ap.add_argument("--admin", default="SM2",
                    help="노트북이 읽을 때 쓰는 관리자 Origin(config/local.json의 cse.admin)")
    ap.add_argument("--split", default="2015-01-01",
                    help="이 날짜 이전은 TS-train, 이후(포함)는 TS-test")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    a = ap.parse_args()

    raw = open(a.csv, "rb").read()
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    cols = list(rows[0].keys()) if rows else []
    if cols != EXPECTED_COLUMNS:
        sys.exit(f"❌ CSV 열이 예상과 다르다: {cols} (예상 {EXPECTED_COLUMNS})")
    rows.sort(key=lambda r: r["date"])
    sets = {
        "TS-train": [r for r in rows if r["date"] < a.split],
        "TS-test": [r for r in rows if r["date"] >= a.split],
    }
    print(f"CSV {a.csv} — {len(rows)}행, sha256 {hashlib.sha256(raw).hexdigest()[:16]}…")
    for ae, rs in sets.items():
        print(f"  {ae}: {len(rs)}일 ({rs[0]['date']} ~ {rs[-1]['date']}) → cin {len(rs) * len(CONTAINERS)}개")
    if a.dry_run:
        r0 = sets["TS-train"][-1]
        print("dry-run — 실제 요청 없음. 첫 번째로 넣을 cin(가장 늦은 날짜) 예:")
        for cnt in CONTAINERS:
            print(f"  {cnt}: {con_of(r0, cnt)}")
        return

    if a.verify_only:
        sys.exit(verify(a, sets))

    # 이미 있으면 멈춘다 — 다시 넣으면 cin이 두 벌 쌓이고 노트북은 인덱스로 짝을 지으므로 조용히 어긋난다.
    for ae in sets:
        r = requests.get(f"{a.base}/{ae}", headers=headers(a.admin), timeout=10)
        if r.status_code == 200:
            sys.exit(f"❌ {ae}가 이미 있다. 지우고 다시 하려면 먼저 삭제할 것 — 이 스크립트는 지우지 않는다.")

    for ae, rs in sets.items():
        res = post(a.base, "S", 2, {"m2m:ae": {"rn": ae, "api": "Nweather-lstm-lab", "rr": False, "srv": ["3"]}})
        aei = res["m2m:ae"]["aei"]
        print(f"✅ AE {ae} (aei={aei})")
        for cnt in CONTAINERS:
            post(f"{a.base}/{ae}", aei, 3, {"m2m:cnt": {"rn": cnt}})
            for row in reversed(rs):  # 날짜 역순 — 위 docstring 1번
                post(f"{a.base}/{ae}/{cnt}", aei, 4, {"m2m:cin": {"con": con_of(row, cnt)}})
            print(f"   ✅ {cnt}: cin {len(rs)}개")
    sys.exit(verify(a, sets))


def verify(a, sets):
    """노트북이 읽는 그대로 읽어 본다. 실패 수를 돌려준다(0이면 통과)."""
    root = a.base.split("/Mobius")[0] + "/"
    fails = 0
    for ae, rs in sets.items():
        for cnt in CONTAINERS:
            r = requests.get(f"{a.base}/{ae}/{cnt}?fu=1&ty=4", headers=headers(a.admin), timeout=30)
            uril = r.json().get("m2m:uril", []) if r.status_code == 200 else []
            first = requests.get(root + uril[0], headers=headers(a.admin), timeout=10).json() if uril else {}
            first_date = first.get("m2m:cin", {}).get("con", {}).get("date")
            ok_n, ok_d = len(uril) == len(rs), first_date == rs[0]["date"]
            hint = " ← discovery_limit가 아직 200인 듯(설정 후 재기동 필요)" if len(uril) == 200 else ""
            # mobius4는 권한이 없는 Origin에게 오류가 아니라 **빈 목록**을 준다 — 0개면 대개 이것이다.
            hint += f" ← --admin {a.admin} 이(가) 내 mobius4의 cse.admin과 같은지 확인" if r.status_code == 200 and not uril else ""
            hint += f" ← HTTP {r.status_code}, Origin {a.admin} 권한 확인" if r.status_code != 200 else ""
            print(f"  {'✅' if ok_n and ok_d else '❌'} {ae}/{cnt}: {len(uril)}/{len(rs)}개, "
                  f"첫 항목 날짜 {first_date} (기대 {rs[0]['date']}){hint}")
            fails += not (ok_n and ok_d)
    print("검증 통과 — 노트북을 실행해도 됩니다." if fails == 0 else f"검증 실패 {fails}건")
    return 1 if fails else 0


if __name__ == "__main__":
    main()
