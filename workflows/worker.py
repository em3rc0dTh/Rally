"""Temporal worker for optional HumanCaseReview sample."""
import asyncio
import os
from temporalio.client import Client
from temporalio.worker import Worker
from workflows.review import HumanCaseReview, read_case

async def main():
    client = await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
    worker = Worker(client, task_queue="rally-human-review", workflows=[HumanCaseReview], activities=[read_case])
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
