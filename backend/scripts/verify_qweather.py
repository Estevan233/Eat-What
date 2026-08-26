"""Verify QWeather server credentials without printing secrets or weather data."""

from collections.abc import Callable
from time import perf_counter
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.weather_client import normalize_qweather_host

RequestGet = Callable[..., httpx.Response]


def verify_qweather(
    *,
    api_host: str,
    api_key: str,
    timeout: float = 2.5,
    request_get: RequestGet = httpx.get,
) -> dict[str, int | str]:
    """Call QWeather's current endpoint and return only safe diagnostic fields."""
    host = normalize_qweather_host(api_host)
    if not host or not api_key:
        raise RuntimeError("QWEATHER_API_HOST/API_KEY is not configured")

    started = perf_counter()
    try:
        response = request_get(
            f"{host}/v7/weather/now",
            params={"location": "116.41,39.92", "lang": "zh", "unit": "m"},
            headers={"X-QW-Api-Key": api_key},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"qweather request failed: {type(exc).__name__}") from None
    elapsed_ms = round((perf_counter() - started) * 1000)

    try:
        payload: Any = response.json()
    except ValueError:
        payload = {}
    provider_code = str(payload.get("code", "missing")) if isinstance(payload, dict) else "missing"
    if response.status_code != 200 or provider_code != "200":
        raise RuntimeError(
            "qweather verification failed: "
            f"status={response.status_code} provider_code={provider_code}"
        )

    return {
        "status": response.status_code,
        "provider_code": provider_code,
        "elapsed_ms": elapsed_ms,
    }


def main() -> None:
    settings = get_settings()
    api_key = settings.qweather_api_key
    summary = verify_qweather(
        api_host=settings.qweather_api_host,
        api_key=api_key.get_secret_value() if api_key is not None else "",
        timeout=settings.qweather_timeout_seconds,
    )
    print(
        "qweather_ok",
        "status=" + str(summary["status"]),
        "provider_code=" + str(summary["provider_code"]),
        "elapsed_ms=" + str(summary["elapsed_ms"]),
    )


if __name__ == "__main__":
    main()
