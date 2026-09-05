"""Tests for planner node and research plan generation."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.graph.nodes.planner import planner_node, _parse_research_plan, _fallback_plan
from backend.graph.state import ResearchState, create_initial_state
from backend.core.interfaces import LLMProvider


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    provider = AsyncMock(spec=LLMProvider)
    provider.generate = AsyncMock(return_value='{"goal": "Test goal", "tasks": ["task 1", "task 2"]}')
    return provider


@pytest.fixture
def initial_state():
    """Create an initial state for testing."""
    return create_initial_state(
        user_query="What is artificial intelligence?",
        conversation_id="test-conv-123",
        request_id="test-req-123",
    )


def test_fallback_plan():
    """Test fallback plan generation."""
    plan = _fallback_plan("test query", fallback=True)

    assert plan["goal"] == "Research and analyze: test query"
    assert len(plan["tasks"]) == 4
    assert "test query" in plan["tasks"]
    assert plan["query_type"] == "research"
    assert plan["preferred_providers"] == ["duckduckgo", "arxiv"]
    assert plan["research_depth"] == "moderate"
    assert plan["fallback"] == True


def test_fallback_plan_with_raw_response():
    """Test fallback plan with raw response."""
    plan = _fallback_plan("test query", raw_response="LLM failed", fallback=True)

    assert plan["raw_response"] == "LLM failed"
    assert plan["fallback"] == True


def test_parse_research_plan_valid_json():
    """Test parsing valid JSON research plan."""
    response = '{"goal": "Research AI", "tasks": ["AI overview", "AI history"]}'
    plan = _parse_research_plan(response, "What is AI?")

    assert plan["goal"] == "Research AI"
    assert plan["tasks"] == ["AI overview", "AI history"]
    assert plan["fallback"] == False
    assert plan["query_type"] == "research"
    assert plan["preferred_providers"] == ["duckduckgo", "arxiv"]


def test_parse_research_plan_with_optional_fields():
    """Test parsing JSON with optional fields."""
    response = '{"goal": "Research AI", "tasks": ["AI overview"], "query_type": "definition", "preferred_providers": ["wikipedia"], "research_depth": "deep"}'
    plan = _parse_research_plan(response, "What is AI?")

    assert plan["query_type"] == "definition"
    assert plan["preferred_providers"] == ["wikipedia"]
    assert plan["research_depth"] == "deep"
    assert plan["fallback"] == False


def test_parse_research_plan_malformed_json():
    """Test parsing malformed JSON falls back to default plan."""
    response = 'This is not JSON at all'
    plan = _parse_research_plan(response, "test query")

    assert plan["fallback"] == True
    assert plan["goal"] == "Research and analyze: test query"


def test_parse_research_plan_empty_tasks():
    """Test parsing JSON with empty tasks falls back."""
    response = '{"goal": "Test", "tasks": []}'
    plan = _parse_research_plan(response, "test query")

    assert plan["fallback"] == True


def test_parse_research_plan_invalid_tasks():
    """Test parsing JSON with invalid tasks falls back."""
    response = '{"goal": "Test", "tasks": "not a list"}'
    plan = _parse_research_plan(response, "test query")

    assert plan["fallback"] == True


def test_parse_research_plan_json_in_text():
    """Test extracting JSON from text response."""
    response = 'Here is the plan: {"goal": "Test", "tasks": ["task1"]}. Hope this helps!'
    plan = _parse_research_plan(response, "test query")

    assert plan["goal"] == "Test"
    assert plan["tasks"] == ["task1"]
    assert plan["fallback"] == False


def test_parse_research_plan_tasks_limit():
    """Test that tasks are limited to 5."""
    response = '{"goal": "Test", "tasks": ["t1", "t2", "t3", "t4", "t5", "t6", "t7"]}'
    plan = _parse_research_plan(response, "test query")

    assert len(plan["tasks"]) == 5
    assert plan["tasks"] == ["t1", "t2", "t3", "t4", "t5"]


def test_parse_research_plan_normalizes_fields():
    """Test that fields are normalized to correct types."""
    response = '{"goal": 123, "tasks": ["task"], "query_type": 456, "preferred_providers": "not a list", "research_depth": 789}'
    plan = _parse_research_plan(response, "test query")

    assert plan["goal"] == "123"  # Converted to string
    assert plan["query_type"] == "research"  # Invalid type falls back to default
    assert plan["preferred_providers"] == ["duckduckgo", "arxiv"]  # Invalid type falls back to default
    assert plan["research_depth"] == "moderate"  # Invalid type falls back to default


@pytest.mark.asyncio
async def test_planner_node_success(mock_llm_provider, initial_state):
    """Test planner node successful execution."""
    result = await planner_node(initial_state, mock_llm_provider)

    assert result["user_query"] == initial_state["user_query"]
    assert "metadata" in result
    assert "research_plan" in result["metadata"]
    assert result["metadata"]["research_plan"]["goal"] == "Test goal"
    assert result["metadata"]["research_plan"]["tasks"] == ["task 1", "task 2"]
    assert result["metadata"]["research_plan"]["fallback"] == False
    assert "intermediate_steps" in result
    assert len(result["intermediate_steps"]) == 1
    assert result["intermediate_steps"][0]["node"] == "planner"
    assert result["intermediate_steps"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_planner_node_llm_failure(mock_llm_provider, initial_state):
    """Test planner node handles LLM failure gracefully."""
    mock_llm_provider.generate = AsyncMock(side_effect=Exception("LLM error"))

    result = await planner_node(initial_state, mock_llm_provider)

    assert "metadata" in result
    assert "research_plan" in result["metadata"]
    assert result["metadata"]["research_plan"]["fallback"] == True
    assert "errors" in result
    assert len(result["errors"]) == 1
    assert result["errors"][0]["node"] == "planner"
    assert result["intermediate_steps"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_planner_node_empty_response(mock_llm_provider, initial_state):
    """Test planner node handles empty response."""
    mock_llm_provider.generate = AsyncMock(return_value="")

    result = await planner_node(initial_state, mock_llm_provider)

    assert result["metadata"]["research_plan"]["fallback"] == True
    assert result["metadata"]["research_plan"]["goal"] == "Research and analyze: What is artificial intelligence?"


@pytest.mark.asyncio
async def test_planner_node_malformed_response(mock_llm_provider, initial_state):
    """Test planner node handles malformed response."""
    mock_llm_provider.generate = AsyncMock(return_value="This is not valid JSON")

    result = await planner_node(initial_state, mock_llm_provider)

    assert result["metadata"]["research_plan"]["fallback"] == True
    assert result["metadata"]["research_plan"]["goal"] == "Research and analyze: What is artificial intelligence?"


@pytest.mark.asyncio
async def test_planner_node_preserves_state(mock_llm_provider, initial_state):
    """Test planner node preserves existing state fields."""
    initial_state["custom_field"] = "custom_value"
    initial_state["existing_metadata"] = {"key": "value"}

    result = await planner_node(initial_state, mock_llm_provider)

    assert result["custom_field"] == "custom_value"
    assert result["existing_metadata"] == {"key": "value"}
    assert result["user_query"] == initial_state["user_query"]
    assert result["request_id"] == initial_state["request_id"]


@pytest.mark.asyncio
async def test_planner_node_query_type_propagation(mock_llm_provider, initial_state):
    """Test that query_type from plan is preserved."""
    mock_llm_provider.generate = AsyncMock(
        return_value='{"goal": "Test", "tasks": ["task"], "query_type": "definition"}'
    )

    result = await planner_node(initial_state, mock_llm_provider)

    assert result["metadata"]["research_plan"]["query_type"] == "definition"


@pytest.mark.asyncio
async def test_planner_node_preferred_providers_propagation(mock_llm_provider, initial_state):
    """Test that preferred_providers from plan is preserved."""
    mock_llm_provider.generate = AsyncMock(
        return_value='{"goal": "Test", "tasks": ["task"], "preferred_providers": ["wikipedia", "arxiv"]}'
    )

    result = await planner_node(initial_state, mock_llm_provider)

    assert result["metadata"]["research_plan"]["preferred_providers"] == ["wikipedia", "arxiv"]


@pytest.mark.asyncio
async def test_planner_node_research_depth_propagation(mock_llm_provider, initial_state):
    """Test that research_depth from plan is preserved."""
    mock_llm_provider.generate = AsyncMock(
        return_value='{"goal": "Test", "tasks": ["task"], "research_depth": "deep"}'
    )

    result = await planner_node(initial_state, mock_llm_provider)

    assert result["metadata"]["research_plan"]["research_depth"] == "deep"


def test_parse_research_plan_whitespace_handling():
    """Test that whitespace is properly handled in parsing."""
    response = '{"goal": "  Test Goal  ", "tasks": ["  task 1  ", "  task 2  "]}'
    plan = _parse_research_plan(response, "test query")

    assert plan["goal"] == "Test Goal"
    assert plan["tasks"] == ["task 1", "task 2"]


def test_parse_research_plan_empty_string_tasks():
    """Test that empty string tasks are filtered out."""
    response = '{"goal": "Test", "tasks": ["task 1", "", "  ", "task 2"]}'
    plan = _parse_research_plan(response, "test query")

    assert plan["tasks"] == ["task 1", "task 2"]
    assert len(plan["tasks"]) == 2
