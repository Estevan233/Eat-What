from typing import Any

import httpx

from scripts.verify_qweather import verify_qweather


class QWeatherProbe:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"url": url, **kwargs})
        return self.response


def _response(status_code: int, payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("GET", "https://example.test/v7/weather/now"),
    )


def test_verify_qweather_normalizes_bare_host_and_uses_server_header() -> None:
    probe = QWeatherProbe(_response(200, {"code": "200", "now": {}}))

    summary = verify_qweather(
        api_host="abc.qweatherapi.com/",
        api_key="server-secret",
        request_get=probe.get,
    )

    assert probe.calls == [
        {
            "url": "https://abc.qweatherapi.com/v7/weather/now",
            "params": {"location": "116.41,39.92", "lang": "zh", "unit": "m"},
            "headers": {"X-QW-Api-Key": "server-secret"},
            "timeout": 2.5,
        }
    ]
    assert summary["status"] == 200
    assert summary["provider_code"] == "200"
    assert isinstance(summary["elapsed_ms"], int)


def test_verify_qweather_rejects_provider_error_without_leaking_key() -> None:
    probe = QWeatherProbe(_response(200, {"code": "401"}))

    try:
        verify_qweather(
            api_host="https://abc.qweatherapi.com",
            api_key="do-not-print-me",
            request_get=probe.get,
        )
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("provider error should fail verification")

    assert "provider_code=401" in message
    assert "do-not-print-me" not in message
