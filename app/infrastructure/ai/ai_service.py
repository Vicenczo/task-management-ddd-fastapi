"""
AI Service — Embedding generation and semantic analysis via Ollama + LangChain.

Design decisions:
  - Uses Ollama locally (RTX 5070, llama3 model, 4096-dim embeddings).
  - OllamaEmbeddings for vector generation — deterministic, no temperature.
  - OllamaLLM for subtask suggestions — structured JSON output.
  - Graceful degradation: if Ollama is unavailable, methods return None/[]
    so the main task creation flow is never blocked by AI failures.
  - This is Infrastructure layer — it knows about external services (Ollama).
    Application layer (TaskService) depends on this via dependency injection.

Requirements (add to requirements.txt):
    langchain-ollama
    langchain-core
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Ollama base URL — override via OLLAMA_BASE_URL env var
import os
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
EMBEDDING_DIM: int = 4096  # llama3 embedding dimension


class AIService:
    """
    Provides AI capabilities: embedding generation and semantic task analysis.

    Initialized lazily — Ollama clients are created on first use so that
    the app can start even if Ollama is not running.

    Usage:
        ai_service = AIService()
        vector = await ai_service.generate_embedding("Fix login bug")
        subtasks = await ai_service.get_semantic_suggestions(task_id, "Fix login bug in auth module")
    """

    def __init__(self) -> None:
        self._embeddings_client = None
        self._llm_client = None

    def _get_embeddings_client(self):
        """Lazy init of OllamaEmbeddings client."""
        if self._embeddings_client is None:
            try:
                from langchain_ollama import OllamaEmbeddings
                self._embeddings_client = OllamaEmbeddings(
                    model=OLLAMA_MODEL,
                    base_url=OLLAMA_BASE_URL,
                )
            except ImportError:
                logger.error(
                    "langchain-ollama not installed. Run: pip install langchain-ollama"
                )
                raise
        return self._embeddings_client

    def _get_llm_client(self):
        """Lazy init of OllamaLLM client."""
        if self._llm_client is None:
            try:
                from langchain_ollama import OllamaLLM
                self._llm_client = OllamaLLM(
                    model=OLLAMA_MODEL,
                    base_url=OLLAMA_BASE_URL,
                    temperature=0.3,  # Low temperature for structured output
                    format="json",    # Request JSON output directly
                )
            except ImportError:
                logger.error(
                    "langchain-ollama not installed. Run: pip install langchain-ollama"
                )
                raise
        return self._llm_client

    async def generate_embedding(self, text: str) -> Optional[list[float]]:
        """
        Convert text to a 4096-dimensional vector using llama3 via Ollama.

        Args:
            text: The text to embed (task title + description).

        Returns:
            List of 4096 floats, or None if Ollama is unavailable.

        Note:
            OllamaEmbeddings.aembed_query() is the async method.
            Never raises — logs error and returns None on failure.
        """
        if not text or not text.strip():
            logger.warning("generate_embedding called with empty text — skipping.")
            return None

        try:
            client = self._get_embeddings_client()
            # aembed_query is the async LangChain embedding method
            vector: list[float] = await client.aembed_query(text.strip())
            logger.debug(
                "Generated embedding: dim=%d, text_preview='%s...'",
                len(vector), text[:50],
            )
            return vector
        except Exception as exc:
            logger.error(
                "Embedding generation failed (Ollama unavailable?): %s", exc
            )
            return None

    async def get_semantic_suggestions(
        self, task_title: str, task_description: str
    ) -> list[str]:
        """
        Generate 3 logical subtask suggestions for a given task via llama3.

        Args:
            task_title: The task's title.
            task_description: The task's description.

        Returns:
            List of up to 3 subtask title strings.
            Returns empty list if Ollama is unavailable or parsing fails.

        Prompt strategy:
            Explicit JSON format requirement prevents markdown wrapping.
            Low temperature (0.3) ensures consistent, structured output.
        """
        prompt = f"""You are a project management assistant. Given a task, suggest exactly 3 specific subtasks that would help complete it.

Task Title: {task_title}
Task Description: {task_description if task_description else "No description provided."}

Respond ONLY with valid JSON in this exact format, no other text:
{{"subtasks": ["subtask 1 title", "subtask 2 title", "subtask 3 title"]}}"""

        try:
            client = self._get_llm_client()
            # ainvoke is the async LangChain LLM call
            response: str = await client.ainvoke(prompt)

            # Parse JSON response
            # Strip markdown code blocks if model ignores format="json"
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
                clean = clean.strip()

            data = json.loads(clean)
            subtasks = data.get("subtasks", [])

            if not isinstance(subtasks, list):
                logger.warning("LLM returned non-list subtasks: %s", subtasks)
                return []

            # Sanitize: ensure strings, max 3, non-empty
            result = [
                str(s).strip()
                for s in subtasks[:3]
                if s and str(s).strip()
            ]
            logger.info(
                "Generated %d subtask suggestions for task '%s'", len(result), task_title
            )
            return result

        except json.JSONDecodeError as exc:
            logger.error("LLM returned invalid JSON for subtask suggestions: %s", exc)
            return []
        except Exception as exc:
            logger.error("Subtask suggestion failed (Ollama unavailable?): %s", exc)
            return []


# Singleton instance — shared across the application lifecycle
ai_service: AIService = AIService()