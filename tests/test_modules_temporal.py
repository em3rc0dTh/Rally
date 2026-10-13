"""Temporal SDK contract coverage without contacting a workflow server.

A complete durable-recovery E2E certification is intentionally separate.
"""
import asyncio
import pytest

def test_temporal_case_review_reads_only_and_handles_not_found(monkeypatch):
    import httpx
    from workflows.review import read_case, HumanCaseReview
    original_client=httpx.AsyncClient
    recorded=[]
    def handler(request):
        recorded.append((request.method,request.url.path))
        if request.url.path.endswith("case-existing"):
            return httpx.Response(200,json={"id":"case-existing","state":"acknowledged"})
        return httpx.Response(404,json={"detail":"not found"})
    transport=httpx.MockTransport(handler)
    monkeypatch.setattr("workflows.review.httpx.AsyncClient",
                        lambda **kwargs: original_client(transport=transport))
    monkeypatch.setenv("RALLY_URL","https://rally.example.com")
    monkeypatch.setenv("RALLY_TENANT_TOKEN","test-credential")
    found=asyncio.run(read_case("case-existing"))
    assert found=={"case_id":"case-existing","found":True,"state":"acknowledged"}
    missing=asyncio.run(read_case("case-missing"))
    assert missing=={"case_id":"case-missing","found":False,"state":"missing"}
    assert recorded==[("GET","/api/cases/case-existing"),
                      ("GET","/api/cases/case-missing")]
    assert callable(HumanCaseReview.approve_review)
