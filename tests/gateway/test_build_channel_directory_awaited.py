"""Regression: build_channel_directory is async and must be awaited (gateway #coroutine)."""

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

from gateway.channel_directory import build_channel_directory


def test_build_channel_directory_is_coroutine_until_awaited():
    out = build_channel_directory({})
    assert asyncio.iscoroutine(out)
    loop = asyncio.new_event_loop()
    try:
        directory = loop.run_until_complete(out)
    finally:
        loop.close()
    assert isinstance(directory, dict)
    assert "platforms" in directory


def test_cron_ticker_uses_run_coroutine_threadsafe_for_refresh():
    """_start_cron_ticker runs in a thread; channel refresh must hop to the main loop."""
    from gateway.run import _start_cron_ticker

    stop = threading.Event()
    loop = asyncio.new_event_loop()

    mock_fut = MagicMock()
    mock_fut.result = MagicMock(return_value={"platforms": {"telegram": []}})

    def _fake_run_coroutine_threadsafe(coro, loop_arg):
        # Real helper schedules ``coro`` on ``loop_arg``; this mock must not
        # leave an un-awaited coroutine (GC RuntimeWarning).
        if asyncio.iscoroutine(coro):
            coro.close()
        return mock_fut

    with patch("cron.scheduler.tick", lambda **kwargs: None):
        with patch(
            "gateway.run.asyncio.run_coroutine_threadsafe",
            side_effect=_fake_run_coroutine_threadsafe,
        ) as rct:
            t = threading.Thread(
                target=_start_cron_ticker,
                args=(stop,),
                kwargs={"adapters": {"stub": 1}, "loop": loop, "interval": 0},
                daemon=True,
            )
            t.start()
            time.sleep(0.15)
            stop.set()
            t.join(timeout=5)

    assert rct.called
    args, _kwargs = rct.call_args
    coro, passed_loop = args[0], args[1]
    assert passed_loop is loop
    assert asyncio.iscoroutine(coro)
