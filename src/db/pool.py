import asyncpg


async def create_pool(dsn: str) -> asyncpg.Pool:
    pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
    assert pool is not None
    return pool
