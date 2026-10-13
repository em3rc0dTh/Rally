"""Optional Temporal case-review example; NOT connected automatically to Rally API.

Only reads case state after a human approval signal. Does not mutate Odoo,
assign custody, pay invoices, or automatically resolve cases.
Install with: pip install -e '.[temporal]'
"""
from datetime import timedelta
import os
import httpx
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

@activity.defn
async def read_case(case_id: str) -> dict:
    base = os.environ["RALLY_URL"].rstrip("/")
    token = os.environ["RALLY_TENANT_TOKEN"]
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(base + "/api/cases/" + case_id, headers={"Authorization":"Bearer " + token})
        if res.status_code == 404:
            return {"case_id": case_id, "found": False, "state": "missing"}
        res.raise_for_status()
        case = res.json()
    return {"case_id": case_id, "found": True, "state": case["state"]}

@workflow.defn
class HumanCaseReview:
    def __init__(self):
        self.review_approved = False

    @workflow.signal
    def approve_review(self):
        self.review_approved = True

    @workflow.run
    async def run(self, case_id: str) -> dict:
        await workflow.wait_condition(lambda: self.review_approved)
        # This activity is read-only. Recovery commands need explicit policy + idempotency.
        return await workflow.execute_activity(
            read_case, case_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
