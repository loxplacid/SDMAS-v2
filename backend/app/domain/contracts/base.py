from __future__ import annotations

from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class RepositoryProtocol(Protocol[T]):
    async def get_by_id(self, id: Any) -> T | None: ...

    async def list(self, skip: int = 0, limit: int = 100) -> list[T]: ...

    async def create(self, **kwargs: Any) -> T: ...

    async def update(self, id: Any, **kwargs: Any) -> T | None: ...

    async def delete(self, id: Any) -> bool: ...


class ServiceProtocol(Protocol):
    pass
