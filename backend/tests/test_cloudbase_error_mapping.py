"""CloudBase failures must remain actionable without leaking credentials."""

import pytest

from app.core.cloudbase_errors import map_cloudbase_failure
from app.repositories.cloudbase_rdb import CloudBaseRdbError


@pytest.mark.parametrize("status_code", [401, 403, 404])
def test_auth_and_resource_failures_are_server_configuration_errors(status_code: int) -> None:
    failure = map_cloudbase_failure(CloudBaseRdbError(
        status_code=status_code,
        code="PERMISSION_DENIED",
        message="denied",
    ))

    assert failure.status_code == 503
    assert failure.code == "SERVICE_CONFIG_ERROR"


def test_auto_pause_failure_is_retryable() -> None:
    failure = map_cloudbase_failure(CloudBaseRdbError(
        status_code=503,
        code="RESOURCE_UNAVAILABLE",
        message="database sleeping",
    ))

    assert failure.status_code == 503
    assert failure.code == "DATABASE_UNAVAILABLE"
    assert "唤醒" in failure.message
