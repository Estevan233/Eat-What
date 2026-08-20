"""Safe monotonic timings for recommendation diagnostics."""

from time import perf_counter


class TimingTrace:
    """Collect only whitelisted stage durations; never stores request data."""

    _allowed = frozenset({"profile", "weather", "history", "catalog", "rank", "write"})

    def __init__(self) -> None:
        self._started = perf_counter()
        self._durations_ms: dict[str, float] = {}

    @staticmethod
    def start() -> float:
        return perf_counter()

    def stop(self, name: str, started: float) -> None:
        if name not in self._allowed:
            raise ValueError(f"unsupported timing stage: {name}")
        elapsed_ms = (perf_counter() - started) * 1000
        self._durations_ms[name] = self._durations_ms.get(name, 0.0) + elapsed_ms

    def header_value(self) -> str:
        total_ms = (perf_counter() - self._started) * 1000
        entries = [("total", total_ms), *self._durations_ms.items()]
        return ", ".join(f"{name};dur={duration:.1f}" for name, duration in entries)

    def log_fields(self) -> dict[str, float]:
        return {
            f"timing_{name}_ms": round(duration, 1)
            for name, duration in self._durations_ms.items()
        }
