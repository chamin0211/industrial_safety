"""제조업 국내재해사례를 모두 받아 저장하고, 제목 끝 표현을 많이 나온 순서로 센다.

준비 1주차 데이터 확인용 탐색 스크립트다.
화학물질·가스 사고를 찾을 키워드 후보를 데이터에서 찾는 것이 목적이다.

실행: python scripts/fetch_manufacturing_cases.py
- 처음 실행: API에서 모두 받아 CASES_FILE_PATH 에 저장한 뒤 센다.
- 다음 실행부터: 저장된 파일을 읽어서 센다(API를 부르지 않는다).
- 새로 받고 싶으면 저장된 파일을 지우고 다시 실행한다.
"""

import json
import math
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from check_disaster_api import (
    SUCCESS_RESULT_CODE,
    load_service_key,
    parse_api_response,
    request_disaster_page,
)

# 사례 하나는 API가 준 칸 이름(keyword, contents 등)을 키로 가진 딕셔너리다
DisasterCase = dict[str, Any]

# --- 경로 ---
# 어느 폴더에서 실행하든 같은 곳에 저장되도록, 이 파일 위치를 기준으로 프로젝트 폴더를 찾는다
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASES_FILE_PATH = PROJECT_ROOT / "data" / "raw" / "disaster_cases" / "manufacturing_cases.json"

# --- 받을 데이터 ---
MANUFACTURING_BUSINESS_TYPE = "제조업"
DATA_SOURCE_NAME = "한국산업안전보건공단 국내재해사례 게시판 조회서비스"

# --- API 응답 칸 이름 (활용가이드 기준) ---
API_TOTAL_COUNT_FIELD = "totalCount"
API_TITLE_FIELD = "keyword"  # 이 API는 사례 제목을 keyword 칸에 담아 준다

# --- 저장 파일의 키 이름 (저장과 읽기가 같은 이름을 쓰도록 한 곳에 둔다) ---
SAVED_SOURCE_KEY = "source"
SAVED_BUSINESS_TYPE_KEY = "business_type"
SAVED_FETCHED_AT_KEY = "fetched_at"
SAVED_CASE_COUNT_KEY = "case_count"
SAVED_CASES_KEY = "cases"

# --- 요청 설정 ---
ROWS_PER_PAGE = 100
SECONDS_BETWEEN_REQUESTS = 0.5  # 공공 서버에 짧은 시간에 요청을 몰아 보내지 않으려고 쉰다

# --- 출력 설정 ---
SAMPLE_TITLE_COUNT = 10
TOP_ENDING_COUNT = 40
TITLE_ENDING_STRIP_CHARACTERS = "()[]<>-.,·\"' "


def fetch_page(service_key: str, page_number: int) -> dict[str, Any]:
    """제조업 사례 한 페이지를 요청해 body 딕셔너리를 돌려준다.

    결과 코드가 성공이 아니면 코드와 메시지를 출력하고 종료한다.
    """
    response = request_disaster_page(
        service_key,
        page_number=page_number,
        rows_per_page=ROWS_PER_PAGE,
        business_type=MANUFACTURING_BUSINESS_TYPE,
    )
    api_result = parse_api_response(response)

    header = api_result["header"]
    if header["resultCode"] != SUCCESS_RESULT_CODE:
        sys.exit(
            f"{page_number}페이지 요청 실패: {header['resultCode']} {header['resultMsg']}"
        )
    return api_result["body"]


def extract_page_cases(page_body: dict[str, Any]) -> list[DisasterCase]:
    """한 페이지 body 에서 사례 리스트만 꺼내 돌려준다."""
    return page_body["items"]["item"]


def calculate_total_pages(total_count: int, rows_per_page: int) -> int:
    """전체 건수를 페이지당 건수로 나눠, 모두 받는 데 필요한 페이지 수를 돌려준다."""
    # 1,463건을 100건씩 받으면 14.63번이므로 올림해서 15번 요청한다
    return math.ceil(total_count / rows_per_page)


def warn_if_count_mismatch(received_count: int, expected_count: int) -> None:
    """받은 건수가 API가 알려 준 전체 건수와 다르면 주의 메시지를 출력한다."""
    if received_count != expected_count:
        print(f"주의: 받은 건수 {received_count}건이 전체 건수 {expected_count}건과 다릅니다.")


def fetch_all_cases(service_key: str) -> list[DisasterCase]:
    """제조업 사례를 모든 페이지에 걸쳐 받아 하나의 리스트로 돌려준다."""
    first_page_body = fetch_page(service_key, page_number=1)
    total_count = int(first_page_body[API_TOTAL_COUNT_FIELD])
    total_pages = calculate_total_pages(total_count, ROWS_PER_PAGE)
    print(f"전체 {total_count}건, {total_pages}페이지를 받습니다.")

    all_cases = list(extract_page_cases(first_page_body))
    for page_number in range(2, total_pages + 1):
        time.sleep(SECONDS_BETWEEN_REQUESTS)
        page_body = fetch_page(service_key, page_number)
        all_cases.extend(extract_page_cases(page_body))
        print(f"  {page_number}/{total_pages} 페이지 완료 (누적 {len(all_cases)}건)")

    warn_if_count_mismatch(len(all_cases), total_count)
    return all_cases


def save_cases(cases: list[DisasterCase], file_path: Path) -> None:
    """사례 리스트를 출처·업종·받은 시각과 함께 JSON 파일로 저장한다."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    saved_data = {
        SAVED_SOURCE_KEY: DATA_SOURCE_NAME,
        SAVED_BUSINESS_TYPE_KEY: MANUFACTURING_BUSINESS_TYPE,
        SAVED_FETCHED_AT_KEY: datetime.now().isoformat(timespec="seconds"),
        SAVED_CASE_COUNT_KEY: len(cases),
        SAVED_CASES_KEY: cases,
    }
    with file_path.open("w", encoding="utf-8") as cases_file:
        json.dump(saved_data, cases_file, ensure_ascii=False, indent=2)
    print(f"{len(cases)}건을 {file_path} 에 저장했습니다.")


def load_cases(file_path: Path) -> list[DisasterCase]:
    """저장해 둔 JSON 파일에서 사례 리스트를 읽어 돌려준다."""
    with file_path.open(encoding="utf-8") as cases_file:
        saved_data = json.load(cases_file)
    print(
        f"저장된 파일에서 {saved_data[SAVED_CASE_COUNT_KEY]}건을 읽었습니다. "
        f"(받은 시각: {saved_data[SAVED_FETCHED_AT_KEY]})"
    )
    return saved_data[SAVED_CASES_KEY]


def get_manufacturing_cases() -> list[DisasterCase]:
    """저장 파일이 있으면 읽고, 없으면 API에서 받아 저장한 뒤 사례 리스트를 돌려준다."""
    if CASES_FILE_PATH.exists():
        return load_cases(CASES_FILE_PATH)

    service_key = load_service_key()
    cases = fetch_all_cases(service_key)
    save_cases(cases, CASES_FILE_PATH)
    return cases


def get_case_title(disaster_case: DisasterCase) -> str:
    """사례 하나의 제목을 앞뒤 공백을 떼고 돌려준다."""
    return disaster_case.get(API_TITLE_FIELD, "").strip()


def extract_title_ending(case_title: str) -> str:
    """제목의 마지막 단어를 앞뒤 괄호·문장부호를 떼고 돌려준다.

    1차 확인에서 제목 끝에 발생 형태가 붙는 것을 봤으므로,
    띄어쓰기 기준 마지막 단어를 그 표현으로 본다.
    """
    title_words = case_title.split()
    if not title_words:
        return ""
    return title_words[-1].strip(TITLE_ENDING_STRIP_CHARACTERS)


def print_sample_titles(cases: list[DisasterCase], sample_count: int) -> None:
    """앞쪽 사례의 제목을 그대로 출력한다. 제목 끝 모양을 눈으로 확인하는 용도다."""
    print(f"\n===== 제목 샘플 {sample_count}개 =====")
    for disaster_case in cases[:sample_count]:
        print(" -", get_case_title(disaster_case))


def print_title_ending_counts(cases: list[DisasterCase], top_count: int) -> None:
    """제목 끝 표현을 세어 많이 나온 순서로 출력한다."""
    ending_counter = Counter(
        extract_title_ending(get_case_title(disaster_case)) for disaster_case in cases
    )
    print(f"\n===== 제목 끝 표현 상위 {top_count}개 (전체 {len(ending_counter)}종) =====")
    for title_ending, case_count in ending_counter.most_common(top_count):
        print(f"{case_count:5d}  {title_ending}")


def main() -> None:
    """제조업 사례를 준비하고 제목 샘플과 제목 끝 표현 빈도를 출력한다."""
    cases = get_manufacturing_cases()
    print_sample_titles(cases, SAMPLE_TITLE_COUNT)
    print_title_ending_counts(cases, TOP_ENDING_COUNT)


if __name__ == "__main__":
    main()