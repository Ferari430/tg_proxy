import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from src.core.config import load_config
from src.core.logging import get_logger, setup_logging
from src.db.pool import create_pool
from src.db.repository import MappingRepository
from src.orchestrator import Orchestrator


async def main() -> None:
    load_dotenv()
    setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    log = get_logger(__name__)

    config_path = Path(os.getenv("CONFIG_PATH", "config.yaml"))
    cfg = load_config(config_path)
    log.info("config.loaded", accounts=len(cfg.accounts), mappings=len(cfg.mappings))

    dsn = os.environ["DATABASE_URL"]
    pool = await create_pool(dsn)
    repo = MappingRepository(pool)

    orchestrator = Orchestrator(cfg, repo)
    await orchestrator.run()


if __name__ == "__main__":
    asyncio.run(main())
