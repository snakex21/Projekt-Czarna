"""Współdzielony helper do uruchamiania async kodu w sync testach.

Udostępnia ``run_async_safely(coro)`` — sync wrapper, który:
1. Uruchamia podaną coroutine na świeżej pętli asyncio (``asyncio.run``).
2. Zapisuje i przywraca thread-local ``running_loop`` PRZED i PO wywołaniu.

Punkt (2) jest konieczny, bo pytest-playwright (e2e testy z fixtures
``page``/``browser``) potrafi zostawić ``ProactorEventLoop`` jako
``running_loop`` w bieżącym wątku nawet po teardownie strony. Bez
save/restore następny sync test, który tworzy własny loop, dostaje
``RuntimeError: Cannot run the event loop while another loop is running``.

W izolacji testy przechodzą bez tego wrappera — problem objawia się
tylko gdy Playwright/pytest są w tym samym procesie.

Po wywołaniu ``run_async_safely`` running_loop jest PRZYWRACANY do
wartości sprzed wywołania (często None). Dzięki temu session-scoped
fixtures Playwright (``browser``) nie crashują przy teardownie
(``Browser.close: no running event loop``).
"""
from __future__ import annotations

import asyncio
import asyncio.events
from typing import Awaitable, TypeVar

T = TypeVar("T")


def run_async_safely(coro: Awaitable[T]) -> T:
    """Uruchamia coroutine sync, bezpiecznie względem thread-local running loop.

    :param coro: awaitable do wykonania
    :returns: wynik coroutine

    Użycie::

        async def _run():
            return await some_async_func(...)

        result = run_async_safely(_run())
    """
    previous_loop = asyncio.events._get_running_loop()
    asyncio.events._set_running_loop(None)
    try:
        return asyncio.run(coro)
    finally:
        asyncio.events._set_running_loop(previous_loop)
