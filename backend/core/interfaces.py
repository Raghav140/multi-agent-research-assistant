"""Core interface definitions for AI platform components.

This module defines abstract base classes that establish contracts for
major components of the AI platform. Implementations of these interfaces
will follow these contracts to ensure consistency and interoperability.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator


class LLMProvider(ABC):
    """Abstract base class for Large Language Model providers.

    This interface defines the contract for LLM providers such as
    OpenAI, Anthropic, Ollama, or other language model services.

    Implementations must provide methods for text generation, chat
    completion, and streaming responses.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> str:
        """Generate text completion for a given prompt.

        Args:
            prompt: Input prompt for text generation
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text completion

        Raises:
            LLMProviderError: If generation fails
        """
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate chat completion for a conversation.

        Args:
            messages: List of message dictionaries with role and content
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Dictionary containing response and metadata

        Raises:
            LLMProviderError: If chat completion fails
        """
        pass

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream text completion for a given prompt.

        Args:
            prompt: Input prompt for text generation
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Yields:
            Generated text chunks

        Raises:
            LLMProviderError: If streaming fails
        """
        pass


class SearchProvider(ABC):
    """Abstract base class for search providers.

    This interface defines the contract for search providers such as
    web search APIs, academic databases, or other search services.

    Implementations must provide methods for searching and retrieving
    search results.
    """

    @abstractmethod
    async def search(
        self,
        query: str,
        num_results: int = 10,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Perform a search query.

        Args:
            query: Search query string
            num_results: Number of results to return
            **kwargs: Additional provider-specific parameters

        Returns:
            List of search result dictionaries

        Raises:
            SearchProviderError: If search fails
        """
        pass

    @abstractmethod
    async def get_content(self, url: str, **kwargs: Any) -> str:
        """Retrieve content from a URL.

        Args:
            url: URL to retrieve content from
            **kwargs: Additional provider-specific parameters

        Returns:
            Retrieved content as string

        Raises:
            SearchProviderError: If content retrieval fails
        """
        pass


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers.

    This interface defines the contract for embedding providers that
    convert text to vector representations.

    Implementations must provide methods for generating embeddings
    for single texts and batches of texts.
    """

    @abstractmethod
    async def embed(self, text: str, **kwargs: Any) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed
            **kwargs: Additional provider-specific parameters

        Returns:
            Vector representation as list of floats

        Raises:
            EmbeddingProviderError: If embedding generation fails
        """
        pass

    @abstractmethod
    async def embed_batch(
        self,
        texts: list[str],
        **kwargs: Any,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts to embed
            **kwargs: Additional provider-specific parameters

        Returns:
            List of vector representations

        Raises:
            EmbeddingProviderError: If batch embedding fails
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get the dimension of the embedding vectors.

        Returns:
            Dimension of the embedding vectors
        """
        pass


class VectorStore(ABC):
    """Abstract base class for vector database stores.

    This interface defines the contract for vector stores such as
    ChromaDB, Milvus, FAISS, or other vector databases.

    Implementations must provide methods for storing, searching,
    and managing vector embeddings.
    """

    @abstractmethod
    async def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        """Add documents and embeddings to the vector store.

        Args:
            ids: List of unique identifiers
            embeddings: List of embedding vectors
            documents: List of document texts
            metadatas: Optional list of metadata dictionaries
            **kwargs: Additional store-specific parameters

        Raises:
            VectorStoreError: If add operation fails
        """
        pass

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_dict: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Search for similar documents.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            filter_dict: Optional metadata filters
            **kwargs: Additional store-specific parameters

        Returns:
            List of search results with scores and metadata

        Raises:
            VectorStoreError: If search fails
        """
        pass

    @abstractmethod
    async def delete(self, ids: list[str], **kwargs: Any) -> None:
        """Delete documents from the vector store.

        Args:
            ids: List of document identifiers to delete
            **kwargs: Additional store-specific parameters

        Raises:
            VectorStoreError: If delete operation fails
        """
        pass

    @abstractmethod
    async def get(
        self,
        ids: list[str],
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Retrieve documents by IDs.

        Args:
            ids: List of document identifiers
            **kwargs: Additional store-specific parameters

        Returns:
            List of document dictionaries

        Raises:
            VectorStoreError: If retrieval fails
        """
        pass


class Agent(ABC):
    """Abstract base class for AI agents.

    This interface defines the contract for autonomous AI agents that
    perform specific tasks within the research assistant system.

    Implementations must provide methods for task execution, state
    management, and capability reporting.
    """

    @abstractmethod
    async def execute(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a task.

        Args:
            task: Task description or input
            context: Optional context information
            **kwargs: Additional agent-specific parameters

        Returns:
            Dictionary containing execution results

        Raises:
            AgentError: If execution fails
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> dict[str, Any]:
        """Get agent capabilities and metadata.

        Returns:
            Dictionary describing agent capabilities
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get agent name.

        Returns:
            Agent name
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Get agent description.

        Returns:
            Agent description
        """
        pass


class MemoryStore(ABC):
    """Abstract base class for memory storage systems.

    This interface defines the contract for memory stores that
    maintain conversation history, context, and other persistent
    information for the AI system.

    Implementations must provide methods for storing, retrieving,
    and managing memory entries.
    """

    @abstractmethod
    async def add(
        self,
        key: str,
        value: Any,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Add a memory entry.

        Args:
            key: Unique identifier for the memory
            value: Value to store
            metadata: Optional metadata dictionary
            **kwargs: Additional store-specific parameters

        Raises:
            MemoryStoreError: If add operation fails
        """
        pass

    @abstractmethod
    async def get(self, key: str, **kwargs: Any) -> Any:
        """Retrieve a memory entry.

        Args:
            key: Memory identifier
            **kwargs: Additional store-specific parameters

        Returns:
            Stored value

        Raises:
            MemoryStoreError: If retrieval fails
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 10,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Search memory entries.

        Args:
            query: Search query
            limit: Maximum number of results
            **kwargs: Additional store-specific parameters

        Returns:
            List of matching memory entries

        Raises:
            MemoryStoreError: If search fails
        """
        pass

    @abstractmethod
    async def delete(self, key: str, **kwargs: Any) -> None:
        """Delete a memory entry.

        Args:
            key: Memory identifier
            **kwargs: Additional store-specific parameters

        Raises:
            MemoryStoreError: If delete operation fails
        """
        pass

    @abstractmethod
    async def clear(self, **kwargs: Any) -> None:
        """Clear all memory entries.

        Args:
            **kwargs: Additional store-specific parameters

        Raises:
            MemoryStoreError: If clear operation fails
        """
        pass
