"""국내재해사례 API를 한 번 호출해 전체 건수, 필드 이름, 샘플 사례를 출력한다.

준비 1주차 데이터 확인용 일회용 탐색 스크립트다.
API 명세: data/raw/api_guides/18. 한국산업안전보건공단_국내재해사례 게시판 조회서비스_오픈API활용가이드.docx

실행: python scripts/check_disaster_api.py
필요: 프로젝트 폴더의 .env 에 DATA_GO_KR_KEY (공공데이터포털 일반 인증키, Decoding)
"""

import os
import sys
from typing import Any

import requests
from dotenv import load_dotenv

# --- API 정보 (활용가이드 기준) ---
DISASTER_API_URL = "https://apis.data.go.kr/B552468/disaster_api02/getdisaster_api02"
DISASTER_CALL_API_ID = "1060"  # 활용가이드에 "필수입력 고정값"으로 적힌 호출 아이디
SUCCESS_RESULT_CODE = "00"

# --- 실행 설정 ---
API_KEY_ENV_NAME = "DATA_GO_KR_KEY"
REQUEST_TIMEOUT_SECONDS = 10
SAMPLE_SIZE = 3  # 전체 건수와 필드 모양만 보면 되므로 샘플은 조금만 받는다
CONTENT_PREVIEW_LENGTH = 150
ERROR_PREVIEW_LENGTH = 500


def load_service_key() -> str:
    """.env 에서 공공데이터포털 인증키를 읽어 돌려준다. 없으면 안내 메시지와 함께 종료한다."""
    load_dotenv()
    service_key = os.getenv(API_KEY_ENV_NAME)
    if not service_key:
        sys.exit(f".env 에 {API_KEY_ENV_NAME} 가 없습니다.")
    return service_key


def request_disaster_page(
    service_key: str,
    page_number: int = 1,
    rows_per_page: int = SAMPLE_SIZE,
    business_type: str | None = None,
) -> requests.Response:
    """국내재해사례 API에 한 페이지를 요청하고 HTTP 응답을 돌려준다.

    business_type 을 주면(예: "제조업") 그 업종 게시판의 사례만 요청한다.
    """
    query_params = {
        "serviceKey": service_key,
        "callApiId": DISASTER_CALL_API_ID,
        "pageNo": page_number,
        "numOfRows": rows_per_page,
    }
    # 업종을 고르지 않았으면 business 칸 자체를 보내지 않아야 전체 업종이 조회된다
    if business_type:
        query_params["business"] = business_type

    response = requests.get(
        DISASTER_API_URL,
        params=query_params,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response


def parse_api_response(response: requests.Response) -> dict[str, Any]:
    """HTTP 응답을 header 와 body 가 든 딕셔너리로 바꿔 돌려준다.

    JSON 이 아니면 응답 앞부분을 출력하고 종료한다.
    """
    try:
        payload = response.json()
    except ValueError:
        # 공공데이터포털은 인증키 오류 같은 경우 JSON 대신 XML 을 돌려줄 때가 있다
        print("JSON 이 아닌 응답이 왔습니다. 앞부분:")
        print(response.text[:ERROR_PREVIEW_LENGTH])
        sys.exit(1)

    # 일부 API 는 전체를 {"response": {...}} 로 한 번 더 감싸서 준다. 감싸져 있으면 벗긴다
    return payload.get("response", payload)


def print_summary(section_title: str, api_result: dict[str, Any]) -> None:
    """결과 코드, 전체 건수, 필드 이름, 샘플 사례를 출력한다."""
    header = api_result["header"]
    print(f"\n===== {section_title} =====")
    print("결과 코드:", header["resultCode"], header["resultMsg"])
    if header["resultCode"] != SUCCESS_RESULT_CODE:
        return

    body = api_result["body"]
    print("전체 건수:", body["totalCount"])

    disaster_cases = body["items"]["item"]
    if not disaster_cases:
        print("사례 없음")
        return

    print("필드 이름:", list(disaster_cases[0].keys()))
    for case_number, disaster_case in enumerate(disaster_cases, start=1):
        case_title = disaster_case.get("keyword", "").strip()
        content_preview = disaster_case.get("contents", "")[:CONTENT_PREVIEW_LENGTH]
        content_preview = content_preview.replace("\n", " ")

        print(f"\n[{case_number}] 게시판: {disaster_case.get('business')}")
        print(f"    제목: {case_title}")
        print(f"    본문 앞부분: {content_preview}")


def main() -> None:
    """전체 업종과 제조업을 각각 조회해 결과를 나란히 출력한다."""
    service_key = load_service_key()

    all_response = request_disaster_page(service_key)
    print_summary("전체", parse_api_response(all_response))

    manufacturing_response = request_disaster_page(service_key, business_type="제조업")
    print_summary("제조업", parse_api_response(manufacturing_response))


if __name__ == "__main__":
    main()
