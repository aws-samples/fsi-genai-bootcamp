from lambda_code.index import (
    web_search,
    get_current_date,
    get_ticker_data,
    get_fred_data,
    lambda_handler,
)


from dataclasses import dataclass
from pathlib import Path
import pytest
import json


@dataclass
class LambdaContext:
    function_name: str = "test"
    memory_limit_in_mb: int = 128
    invoked_function_arn: str = "arn:aws:lambda:us-east-1:123456789012:function:test"
    aws_request_id: str = "1234567890abcdef"


@pytest.fixture
def lambda_context() -> LambdaContext:
    return LambdaContext()


def test_web_search():
    query = "amazon stock news"
    max_results = 5
    response = web_search(query, max_results)
    assert response is not None
    assert isinstance(response, str)
    assert "Search Results" in response
    assert "amazon" in response.lower()
    assert "stock" in response.lower()


def test_get_current_date():
    response = get_current_date()
    assert response is not None
    assert isinstance(response, str)
    assert len(response) == 10  # YYYY-MM-DD format
    assert int(response.split("-")[0]) > 2000  # Year should be greater than 2000
    assert int(response.split("-")[1]) in range(
        1, 13
    )  # Month should be between 1 and 12


def test_get_ticker_data():
    ticker = "AAPL"
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    response = get_ticker_data(ticker, start_date, end_date)
    assert response is not None
    assert isinstance(response, dict)
    assert "AAPL" in response
    ticker_data = response["AAPL"]
    assert isinstance(ticker_data, list)
    assert len(ticker_data) > 0
    assert "Date" in ticker_data[0]
    assert start_date <= ticker_data[0]["Date"] <= end_date


def test_get_fred_data():
    series_id = "GDP"
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    response = get_fred_data(series_id, start_date, end_date)
    assert response is not None
    assert isinstance(response, list)
    assert len(response) > 0
    first_entry = response[0]
    assert isinstance(first_entry, dict)
    assert "Date" in first_entry
    assert series_id in first_entry


def test_lambda_handler(lambda_context):

    test_events_dir = Path(__file__).parent / "test_events"
    test_event_files = list(test_events_dir.glob("*.json"))

    for event_file in test_event_files:
        print(f"Testing with event file: {event_file}")
        with open(event_file, "r") as f:
            event = json.load(f)

        response = lambda_handler(event, lambda_context)
        assert response is not None
        assert isinstance(response, dict)
        status_code = response["response"]["httpStatusCode"]
        print(response)

        expected_status_code = int(event_file.stem.split("_")[-1])

        assert status_code == expected_status_code
