"""server.log: the browser closing a connection on Windows is not logged as an error."""
from __future__ import annotations

import logging
import sys

from app.__main__ import _quiet_connection_reset


def _record(exc: BaseException, msg: str) -> logging.LogRecord:
    try:
        raise exc
    except BaseException:  # noqa: BLE001
        info = sys.exc_info()
    return logging.LogRecord("asyncio", logging.ERROR, __file__, 1, msg, None, info)


def test_connection_reset_is_dropped_other_errors_stay():
    reset = ConnectionResetError(10054, "reset")
    assert not _quiet_connection_reset(_record(reset, "Exception in callback _ProactorBasePipeTransport._call_connection_lost(None)"))
    assert _quiet_connection_reset(_record(reset, "Exception in callback something_else()"))
    assert _quiet_connection_reset(_record(ValueError("x"), "Exception in callback _call_connection_lost"))
