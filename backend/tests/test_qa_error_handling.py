import httpx

from app.services.qa_error_handling import classify_qa_exception


def test_classify_timeout_exception():
    result = classify_qa_exception(httpx.ReadTimeout("timeout"))

    assert result.reason == "model_timeout"
    assert "超时" in result.user_message
    assert result.should_record_unanswered is True


def test_classify_http_status_exception():
    request = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
    response = httpx.Response(429, request=request)
    exc = httpx.HTTPStatusError("too many requests", request=request, response=response)

    result = classify_qa_exception(exc)

    assert result.reason == "model_http_error"
    assert result.status_code == 429
    assert result.should_record_unanswered is True


def test_classify_unknown_exception():
    result = classify_qa_exception(ValueError("bad payload"))

    assert result.reason == "qa_internal_error"
    assert result.status_code is None
    assert result.should_record_unanswered is True
