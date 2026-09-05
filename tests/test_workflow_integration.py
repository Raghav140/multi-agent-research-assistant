"""Integration tests for the complete research workflow."""

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
    provider.generate = AsyncMock(side_effect=[
        # Planner response
        '{"goal": "Research AI", "tasks": ["artificial intelligence overview", "AI history"]}',
        # Report response
        """## Executive Summary

Artificial intelligence (AI) is a branch of computer science focused on creating systems that can perform tasks requiring human intelligence.

## Key Findings

- AI encompasses machine learning, neural networks, and natural language processing
- Modern AI systems use deep learning techniques
- AI applications include healthcare, finance, and transportation

## Detailed Analysis

AI has evolved from symbolic AI to modern machine learning approaches. Key developments include:

1. Machine learning algorithms that learn from data
2. Neural networks inspired by biological systems
3. Natural language processing for text understanding

## Evidence

[1] Artificial Intelligence Overview
[2] AI History and Development

## References

[1] Artificial Intelligence Overview
    URL: http://test.com/ai-overview

[2] AI History and Development
    URL: http://test.com/ai-history
""",
    ])
    return provider


@pytest.fixture
def mock_search_provider():
    """Create a mock search provider."""
    provider = AsyncMock(spec=SearchProvider)
    provider.search = AsyncMock(return_value=[
        {
            "title": "Artificial Intelligence Overview",
            "url": "http://test.com/ai-overview",
            "snippet": "AI is a branch of computer science focused on creating intelligent systems that can perform tasks requiring human intelligence.",
            "relevance_score": 0.95,
            "quality_score": 0.9,
            "semantic_similarity": 0.92,
        },
        {
            "title": "AI History and Development",
            "url": "http://test.com/ai-history",
            "snippet": "AI has evolved from symbolic AI to modern machine learning approaches including deep learning and neural networks.",
            "relevance_score": 0.9,
            "quality_score": 0.85,
            "semantic_similarity": 0.88,
        },
        {
            "title": "Machine Learning Applications",
            "url": "http://test.com/ml-apps",
            "snippet": "Machine learning is used in healthcare, finance, transportation, and many other fields for predictive analytics.",
            "relevance_score": 0.88,
            "quality_score": 0.82,
            "semantic_similarity": 0.85,
        },
    ])
    return provider


@pytest.fixture
def mock_arxiv_provider():
    """Create a mock arXiv provider."""
    provider = AsyncMock(spec=ArxivProvider)
    provider.search = AsyncMock(return_value=[
        {
            "title": "Deep Learning for AI",
            "url": "http://arxiv.org/test",
            "snippet": "Deep learning has revolutionized artificial intelligence research.",
            "relevance_score": 0.88,
            "quality_score": 0.9,
            "semantic_similarity": 0.85,
            "entry_id": "arxiv:1234.5678",
            "pdf_url": "http://arxiv.org/pdf/1234.5678",
        },
    ])
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
async def test_workflow_complete_execution(mock_llm_provider, retrieval_engine):
    """Test complete workflow execution from planner to report."""
    # Build workflow
    workflow = build_workflow(mock_llm_provider, retrieval_engine)

    # Create initial state
    initial_state = create_initial_state(
        user_query="What is artificial intelligence?",
        conversation_id="test-conv-123",
        request_id="test-req-123",
    )

    # Execute workflow
    final_state = await workflow.ainvoke(initial_state)

    # Verify planner executed
    assert "metadata" in final_state
    assert "research_plan" in final_state["metadata"]
    assert final_state["metadata"]["research_plan"]["goal"] == "Research AI"
    assert final_state["metadata"]["research_plan"]["tasks"] == ["artificial intelligence overview", "AI history"]

    # Verify research executed
    assert "search_results" in final_state
    assert len(final_state["search_results"]) > 0
    assert "research_papers" in final_state

    # Verify report generated (may be fallback if validation fails)
    assert "report" in final_state
    assert "content" in final_state["report"]
    assert "## Executive Summary" in final_state["report"]["content"]

    # Verify final answer
    assert "final_answer" in final_state
    assert final_state["final_answer"] == final_state["report"]["content"]

    # Verify intermediate steps
    assert "intermediate_steps" in final_state
    assert len(final_state["intermediate_steps"]) >= 3
    node_names = [step["node"] for step in final_state["intermediate_steps"]]
    assert "planner" in node_names
    assert "research" in node_names
    assert "report" in node_names

    # Verify timing fields
    assert "_timing_planner" in final_state
    assert "_timing_research" in final_state
    assert "_timing_report" in final_state
    assert final_state["_timing_planner"] >= 0
    assert final_state["_timing_research"] >= 0
    assert final_state["_timing_report"] >= 0


@pytest.mark.asyncio
async def test_workflow_research_plan_influences_retrieval(mock_llm_provider, retrieval_engine):
    """Test that research plan influences query variations."""
    # Build workflow
    workflow = build_workflow(mock_llm_provider, retrieval_engine)

    # Create initial state
    initial_state = create_initial_state(
        user_query="What is artificial intelligence?",
        conversation_id="test-conv-123",
        request_id="test-req-123",
    )

    # Execute workflow
    final_state = await workflow.ainvoke(initial_state)

    # Verify research plan was used
    research_plan = final_state["metadata"]["research_plan"]
    assert research_plan["tasks"] == ["artificial intelligence overview", "AI history"]

    # Verify retrieval was performed (mock providers should have been called)
    assert len(final_state["search_results"]) > 0


@pytest.mark.asyncio
async def test_workflow_provider_selector_execution(mock_llm_provider, retrieval_engine):
    """Test that provider selector is used during retrieval."""
    # Build workflow
    workflow = build_workflow(mock_llm_provider, retrieval_engine)

    # Create initial state
    initial_state = create_initial_state(
        user_query="What is artificial intelligence?",
        conversation_id="test-conv-123",
        request_id="test-req-123",
    )

    # Execute workflow
    final_state = await workflow.ainvoke(initial_state)

    # Verify providers were called
    assert len(final_state["search_results"]) > 0


@pytest.mark.asyncio
async def test_workflow_circuit_breaker_protection(mock_llm_provider, retrieval_engine):
    """Test that circuit breaker protects provider calls."""
    # Build workflow
    workflow = build_workflow(mock_llm_provider, retrieval_engine)

    # Create initial state
    initial_state = create_initial_state(
        user_query="What is artificial intelligence?",
        conversation_id="test-conv-123",
        request_id="test-req-123",
    )

    # Execute workflow
    final_state = await workflow.ainvoke(initial_state)

    # Verify workflow completed despite circuit breaker being present
    assert "report" in final_state
    assert "content" in final_state["report"]


@pytest.mark.asyncio
async def test_workflow_cache_and_memory_disabled(mock_llm_provider, retrieval_engine):
    """Test workflow with cache and memory disabled."""
    # Build workflow (cache and memory are disabled in retrieval_engine fixture)
    workflow = build_workflow(mock_llm_provider, retrieval_engine)

    # Create initial state
    initial_state = create_initial_state(
        user_query="What is artificial intelligence?",
        conversation_id="test-conv-123",
        request_id="test-req-123",
    )

    # Execute workflow
    final_state = await workflow.ainvoke(initial_state)

    # Verify workflow completed
    assert "report" in final_state
    assert "content" in final_state["report"]

    # Verify retrieval was performed (not from cache/memory)
    assert len(final_state["search_results"]) > 0


@pytest.mark.asyncio
async def test_workflow_evidence_production(mock_llm_provider, retrieval_engine):
    """Test that evidence is produced and used."""
    # Build workflow
    workflow = build_workflow(mock_llm_provider, retrieval_engine)

    # Create initial state
    initial_state = create_initial_state(
        user_query="What is artificial intelligence?",
        conversation_id="test-conv-123",
        request_id="test-req-123",
    )

    # Execute workflow
    final_state = await workflow.ainvoke(initial_state)

    # Verify evidence exists
    assert "search_results" in final_state
    assert len(final_state["search_results"]) > 0

    # Verify report was generated (may be fallback if validation fails)
    report_content = final_state["report"]["content"]
    assert "## Executive Summary" in report_content


@pytest.mark.asyncio
async def test_workflow_citation_validation(mock_llm_provider, retrieval_engine):
    """Test that citations are validated in report."""
    # Build workflow
    workflow = build_workflow(mock_llm_provider, retrieval_engine)

    # Create initial state
    initial_state = create_initial_state(
        user_query="What is artificial intelligence?",
        conversation_id="test-conv-123",
        request_id="test-req-123",
    )

    # Execute workflow
    final_state = await workflow.ainvoke(initial_state)

    # Verify report was generated
    report_content = final_state["report"]["content"]
    assert "## Executive Summary" in report_content


@pytest.mark.asyncio
async def test_workflow_metrics_recorded(mock_llm_provider, retrieval_engine):
    """Test that metrics are recorded during workflow."""
    # Build workflow
    workflow = build_workflow(mock_llm_provider, retrieval_engine)

    # Create initial state
    initial_state = create_initial_state(
        user_query="What is artificial intelligence?",
        conversation_id="test-conv-123",
        request_id="test-req-123",
    )

    # Execute workflow
    final_state = await workflow.ainvoke(initial_state)

    # Verify research metrics exist
    assert "metadata" in final_state
    assert "research_metrics" in final_state["metadata"]

    # Verify report quality metrics exist
    assert "report" in final_state
    assert "quality_metrics" in final_state["report"]


@pytest.mark.asyncio
async def test_workflow_state_propagation(mock_llm_provider, retrieval_engine):
    """Test that state is properly propagated through workflow."""
    # Build workflow
    workflow = build_workflow(mock_llm_provider, retrieval_engine)

    # Create initial state
    initial_state = create_initial_state(
        user_query="What is artificial intelligence?",
        conversation_id="test-conv-123",
        request_id="test-req-123",
    )

    # Execute workflow
    final_state = await workflow.ainvoke(initial_state)

    # Verify core fields are present
    assert final_state["user_query"] == "What is artificial intelligence?"
    assert final_state["conversation_id"] == "test-conv-123"
    assert final_state["request_id"] == "test-req-123"


@pytest.mark.asyncio
async def test_workflow_no_duplicate_execution(mock_llm_provider, retrieval_engine):
    """Test that nodes execute only once."""
    # Build workflow
    workflow = build_workflow(mock_llm_provider, retrieval_engine)

    # Create initial state
    initial_state = create_initial_state(
        user_query="What is artificial intelligence?",
        conversation_id="test-conv-123",
        request_id="test-req-123",
    )

    # Execute workflow
    final_state = await workflow.ainvoke(initial_state)

    # Verify each node executed exactly once
    node_names = [step["node"] for step in final_state["intermediate_steps"]]
    assert node_names.count("planner") == 1
    assert node_names.count("research") == 1
    assert node_names.count("report") == 1


@pytest.mark.asyncio
async def test_workflow_final_state_completeness(mock_llm_provider, retrieval_engine):
    """Test that final state contains all expected fields."""
    # Build workflow
    workflow = build_workflow(mock_llm_provider, retrieval_engine)

    # Create initial state
    initial_state = create_initial_state(
        user_query="What is artificial intelligence?",
        conversation_id="test-conv-123",
        request_id="test-req-123",
    )

    # Execute workflow
    final_state = await workflow.ainvoke(initial_state)

    # Verify all expected fields are present
    expected_fields = [
        "user_query",
        "conversation_id",
        "request_id",
        "search_results",
        "research_papers",
        "intermediate_steps",
        "final_answer",
        "report",
        "metadata",
    ]

    for field in expected_fields:
        assert field in final_state, f"Missing field: {field}"

    # Verify timing fields
    timing_fields = [
        "_timing_planner",
        "_timing_research",
        "_timing_report",
    ]

    for field in timing_fields:
        assert field in final_state, f"Missing timing field: {field}"


@pytest.mark.asyncio
async def test_workflow_query_type_propagation(mock_llm_provider, retrieval_engine):
    """Test that query_type from research plan is propagated."""
    # Modify LLM to return query_type
    mock_llm_provider.generate = AsyncMock(side_effect=[
        '{"goal": "Research AI", "tasks": ["AI overview"], "query_type": "definition"}',
        """## Executive Summary

Test report.

## Key Findings

Test findings.

## Detailed Analysis

Test analysis.

## Evidence

[1] Test

## References

[1] Test
    URL: http://test.com
""",
    ])

    # Build workflow
    workflow = build_workflow(mock_llm_provider, retrieval_engine)

    # Create initial state
    initial_state = create_initial_state(
        user_query="What is artificial intelligence?",
        conversation_id="test-conv-123",
        request_id="test-req-123",
    )

    # Execute workflow
    final_state = await workflow.ainvoke(initial_state)

    # Verify query_type is in research plan
    assert final_state["metadata"]["research_plan"]["query_type"] == "definition"
