"""Run the durable integration worker separately from the HTTP service."""

import argparse
import asyncio
import logging
from uuid import uuid4

from app.core.config import settings
from app.core.database import worker_engine
from app.services.integration_jobs import claim_run, process_claim, schedule_due


async def serve(*, once: bool) -> None:
    if not settings.INTEGRATIONS_ENABLED:
        raise RuntimeError("The durable integration worker requires INTEGRATIONS_ENABLED")
    worker_id = uuid4()
    try:
        while True:
            try:
                await schedule_due()
                claim = await claim_run(worker_id)
                if claim:
                    await process_claim(**claim)
                if once:
                    return
                if not claim:
                    await asyncio.sleep(5)
            except Exception:
                if once:
                    raise
                logging.getLogger(__name__).warning("Integration worker could not complete a poll")
                await asyncio.sleep(5)
    finally:
        await worker_engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    asyncio.run(serve(once=parser.parse_args().once))
