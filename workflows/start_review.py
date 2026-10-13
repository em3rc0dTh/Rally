"""Start or approve an optional read-only human review workflow.

Usage: python -m workflows.start_review start CASE_UUID
       python -m workflows.start_review approve CASE_UUID
Requires Temporal server + worker and optional temporal dependencies installed.
"""
import asyncio
import os
import sys
from temporalio.client import Client
from workflows.review import HumanCaseReview

async def main(action, case_id):
    client = await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
    workflow_id = "rally-case-review-" + case_id
    if action == "start":
        handle = await client.start_workflow(HumanCaseReview.run, case_id,
                                             id=workflow_id, task_queue="rally-human-review")
        print(handle.id)
    elif action == "approve":
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(HumanCaseReview.approve_review)
        print("Review approved; worker will query the case state.")
    else:
        raise ValueError("Use start or approve")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m workflows.start_review start|approve CASE_UUID")
    asyncio.run(main(sys.argv[1], sys.argv[2]))
