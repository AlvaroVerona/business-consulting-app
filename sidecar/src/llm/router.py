from src.llm.base import LLMClient
from src.llm.claude_client import ClaudeClient
from src.llm.ollama_client import OllamaClient


def get_llm_client(use_claude: bool = False) -> LLMClient:
    """Local Ollama is the default for every call in this product. Claude is
    available only when a caller explicitly opts in for that one call —
    typically a Deep Analysis step where reasoning quality matters more than
    cost — never as a silent fallback or a stored preference."""

    if use_claude:
        return ClaudeClient()

    return OllamaClient()
