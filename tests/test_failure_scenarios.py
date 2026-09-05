"""Failure scenario tests for the research workflow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.graph.workflow import build_workflow
from backend.graph.state import create_initial_state
from backend.core.interfaces import LLMProvider, SearchProvider
from backend.services.retrieval_engine import RetrievalEngine
from backend.providers.papers.arxiv_provider import ArxivProvider


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    provider = AsyncMock(spec=LLMProvider)
    provider.generate = AsyncMock(return_value='{"goal": "Test", "tasks": ["task"]}')
    return provider


@pytest.fixture
def mock_search_provider():
    """Create a mock search provider."""
    provider = AsyncMock(spec=SearchProvider)
    provider.search = AsyncMock(return_value=[
        {
            "title": "Test Result",
            "url": "http://test.com",
            "snippet": "Test snippet",
            "relevance_score": 0.9,
            "quality_score": 0.85,
            "semantic_similarity": 0.88,
        },
    ])
    return provider


@pytest.fixture
def mock_arxiv_provider():
    """Create a mock arXiv provider."""
    provider = AsyncMock(spec=ArxivProvider)
    provider.search = AsyncMock(return_value=[])
    return provider


@pytest.fixture
def retrieval_engine(mock_search_provider, mock_arxiv_provider):
    """Create a RetrievalEngine with mock providers."""
    return RetrievalEngine(
        duckduckgo_provider=mock_search_provider,
        arxiv_provider=mock_arxiv_provider,
        wikipedia_provider=None,
        documentation_provider=None,
        memory_manager=None,
        use_cache=False,
        use_memory=False,
    )


@pytest.mark.asyncio
async def test_planner_llm_failure(mock_llm_provider, retrieval_engine):
    """Test workflow handles planner LLM failure gracefully."""
    # Make LLM fail
    mock_llm_provider.generate = AsyncMock(side_effect=Exception("LLM connection failed"))

    workflow = build_workflow(mock_llm_provider, retrieval_engine)
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )

    # Should complete with fallback plan
    final_state = await workflow.ainvoke(initial_state)

    # Verify fallback plan was used
    assert "metadata" in final_state
    assert "research_plan" in final_state["metadata"]
    assert final_state["metadata"]["research_plan"]["fallback"] == True

    # Verify workflow continued
    assert "report" in final_state


@pytest.mark.asyncio
async def test_planner_empty_response(mock_llm_provider, retrieval_engine):
    """Test workflow handles empty planner response."""
    mock_llm_provider.generate = AsyncMock(return_value="")

    workflow = build_workflow(mock_llm_provider, retrieval_engine)
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )

    # Should complete with fallback plan
    final_state = await workflow.ainvoke(initial_state)

    assert "metadata" in final_state
    assert "research_plan" in final_state["metadata"]
    assert final_state["metadata"]["research_plan"]["fallback"] == True


@pytest.mark.asyncio
async def test_provider_timeout(mock_llm_provider, mock_search_provider, retrieval_engine):
    """Test workflow handles provider timeout."""
    # Make provider timeout
    import asyncio
    mock_search_provider.search = AsyncMock(side_effect=asyncio.TimeoutError("Provider timeout"))

    workflow = build_workflow(mock_llm_provider, retrieval_engine)
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )

    # Should complete despite provider timeout
    final_state = await workflow.ainvoke(initial_state)

    # Verify workflow completed
    assert "report" in final_state
    assert "content" in final_state["report"]


@pytest.mark.asyncio
async def test_provider_exception(mock_llm_provider, mock_search_provider, retrieval_engine):
    """Test workflow handles provider exception."""
    # Make provider raise exception
    mock_search_provider.search = AsyncMock(side_effect=Exception("Provider error"))

    workflow = build_workflow(mock_llm_provider, retrieval_engine)
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )

    # Should complete despite provider exception
    final_state = await workflow.ainvoke(initial_state)

    assert "report" in final_state


@pytest.mark.asyncio
async def test_all_providers_unavailable(mock_llm_provider, mock_search_provider, mock_arxiv_provider, retrieval_engine):
    """Test workflow handles all providers unavailable."""
    # Make all providers fail
    mock_search_provider.search = AsyncMock(side_effect=Exception("Provider unavailable"))
    mock_arxiv_provider.search = AsyncMock(side_effect=Exception("Provider unavailable"))

    workflow = build_workflow(mock_llm_provider, retrieval_engine)
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )

    # Should complete with no evidence response
    final_state = await workflow.ainvoke(initial_state)

    assert "report" in final_state
    assert "content" in final_state["report"]
    assert "## Executive Summary" in final_state["report"]["content"]


@pytest.mark.asyncio
async def test_partial_provider_failure(mock_llm_provider, mock_search_provider, mock_arxiv_provider, retrieval_engine):
    """Test workflow handles partial provider failure."""
    # Make one provider fail, one succeed
    mock_search_provider.search = AsyncMock(side_effect=Exception("Provider unavailable"))
    mock_arxiv_provider.search = AsyncMock(return_value=[
        {
            "title": "Test Paper",
            "url": "http://arxiv.org/test",
            "snippet": "Test abstract",
            "relevance_score": 0.9,
            "quality_score": 0.85,
            "semantic_similarity": 0.88,
            "entry_id": "arxiv:1234",
            "pdf_url": "http://arxiv.org/pdf/1234",
        },
    ])

    workflow = build_workflow(mock_llm_provider, retrieval_engine)
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )

    # Should complete with available evidence
    final_state = await workflow.ainvoke(initial_state)

    assert "report" in final_state


@pytest.mark.asyncio
async def test_cache_failure(mock_llm_provider, retrieval_engine):
    """Test workflow handles cache failure gracefully."""
    # Cache is disabled in the retrieval_engine fixture, so this test
    # verifies the workflow works without cache
    workflow = build_workflow(mock_llm_provider, retrieval_engine)
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )

    # Should complete without cache
    final_state = await workflow.ainvoke(initial_state)

    assert "report" in final_state


@pytest.mark.asyncio
async def test_memory_failure(mock_llm_provider, retrieval_engine):
    """Test workflow handles memory failure gracefully."""
    # Memory is disabled in the retrieval_engine fixture, so this test
    # verifies the workflow works without memory
    workflow = build_workflow(mock_llm_provider, retrieval_engine)
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )

    # Should complete without memory
    final_state = await workflow.ainvoke(initial_state)

    assert "report" in final_state


@pytest.mark.asyncio
async def test_metrics_failure(mock_llm_provider, retrieval_engine):
    """Test workflow handles metrics failure gracefully."""
    # Make metrics storage fail
    from backend.utils.evaluation import get_evaluator
    with patch('backend.utils.evaluation.get_evaluator', side_effect=Exception("Metrics failure")):
        workflow = build_workflow(mock_llm_provider, retrieval_engine)
        initial_state = create_initial_state(
            user_query="What is AI?",
            conversation_id="test-conv",
            request_id="test-req",
        )

        # Should complete despite metrics failure
        final_state = await workflow.ainvoke(initial_state)

        assert "report" in final_state


@pytest.mark.asyncio
async def test_report_validation_failure(mock_llm_provider, retrieval_engine):
    """Test workflow handles report validation failure."""
    # Make report generation produce invalid output that fails validation
    mock_llm_provider.generate = AsyncMock(side_effect=[
        '{"goal": "Test", "tasks": ["task"]}',
        "This is not a valid report format",  # Invalid report
    ])

    workflow = build_workflow(mock_llm_provider, retrieval_engine)
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )

    # Should complete with fallback or regenerated report
    final_state = await workflow.ainvoke(initial_state)

    assert "report" in final_state
    assert "content" in final_state["report"]


@pytest.mark.asyncio
async def test_report_regeneration(mock_llm_provider, retrieval_engine):
    """Test workflow handles report regeneration."""
    # Make first report generation fail validation, second succeed
    mock_llm_provider.generate = AsyncMock(side_effect=[
        '{"goal": "Test", "tasks": ["task"]}',
        "Invalid report",  # First attempt - fails validation
        """## Executive Summary

Valid report content.

## Key Findings

Test findings.

## Detailed Analysis

Test analysis.

## Evidence

[1] Test

## References

[1] Test
    URL: http://test.com
""",  # Second attempt - succeeds
    ])

    workflow = build_workflow(mock_llm_provider, retrieval_engine)
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )

    # Should complete with regenerated report
    final_state = await workflow.ainvoke(initial_state)

    assert "report" in final_state
    assert "content" in final_state["report"]


@pytest.mark.asyncio
async def test_workflow_no_hanging_on_failure(mock_llm_provider, mock_search_provider, retrieval_engine):
    """Test workflow doesn't hang on provider failure."""
    # Make provider hang (simulate with very long timeout)
    import asyncio

    async def hanging_search(*args, **kwargs):
        await asyncio.sleep(10)  # Simulate hanging
        return []

    mock_search_provider.search = AsyncMock(side_effect=hanging_search)

    workflow = build_workflow(mock_llm_provider, retrieval_engine)
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )

    # Should timeout and complete (circuit breaker should protect)
    try:
        final_state = await asyncio.wait_for(workflow.ainvoke(initial_state), timeout=30)
        assert "report" in final_state
    except asyncio.TimeoutError:
        # If it times out, that's also acceptable behavior
        pytest.fail("Workflow hung on provider failure")


@pytest.mark.asyncio
async def test_multiple_sequential_failures(mock_llm_provider, mock_search_provider, retrieval_engine):
    """Test workflow handles multiple sequential failures."""
    # Make provider fail first time, succeed second time
    call_count = [0]

    async def flaky_search(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception("First call fails")
        return [
            {
                "title": "Test Result",
                "url": "http://test.com",
                "snippet": "Test snippet",
                "relevance_score": 0.9,
                "quality_score": 0.85,
                "semantic_similarity": 0.88,
            },
        ]

    mock_search_provider.search = AsyncMock(side_effect=flaky_search)

    workflow = build_workflow(mock_llm_provider, retrieval_engine)
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )

    # Should complete despite initial failure
    final_state = await workflow.ainvoke(initial_state)

    assert "report" in final_state


@pytest.mark.asyncio
async def test_state_corruption_recovery(mock_llm_provider, retrieval_engine):
    """Test workflow recovers from state corruption."""
    workflow = build_workflow(mock_llm_provider, retrieval_engine)

    # Create initial state with corrupted field that will be overwritten
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )
    initial_state["search_results"] = "not a list"  # Corrupted field that will be overwritten

    # Should recover and complete
    final_state = await workflow.ainvoke(initial_state)

    # State should be fixed by the workflow
    assert isinstance(final_state.get("search_results"), list)
    assert "report" in final_state


@pytest.mark.asyncio
async def test_workflow_error_propagation(mock_llm_provider, retrieval_engine):
    """Test errors are properly propagated to state."""
    # Make planner fail
    mock_llm_provider.generate = AsyncMock(side_effect=Exception("Planner error"))

    workflow = build_workflow(mock_llm_provider, retrieval_engine)
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )

    final_state = await workflow.ainvoke(initial_state)

    # Verify error was recorded
    assert "errors" in final_state
    assert len(final_state["errors"]) > 0
    assert final_state["errors"][0]["node"] == "planner"


@pytest.mark.asyncio
async def test_workflow_graceful_degradation(mock_llm_provider, mock_search_provider, mock_arxiv_provider, retrieval_engine):
    """Test workflow degrades gracefully when components fail."""
    # Make most components fail but allow minimal functionality
    mock_search_provider.search = AsyncMock(side_effect=Exception("Search failed"))
    mock_arxiv_provider.search = AsyncMock(side_effect=Exception("Papers failed"))

    workflow = build_workflow(mock_llm_provider, retrieval_engine)
    initial_state = create_initial_state(
        user_query="What is AI?",
        conversation_id="test-conv",
        request_id="test-req",
    )

    # Should complete with minimal/no evidence response
    final_state = await workflow.ainvoke(initial_state)

    assert "report" in final_state
    assert "content" in final_state["report"]
    # Should indicate lack of evidence
    assert "## Executive Summary" in final_state["report"]["content"]
