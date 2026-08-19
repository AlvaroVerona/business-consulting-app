import os

import anthropic


class ClaudeClient:
    """Opt-in backend for Deep Analysis calls where reasoning quality
    matters more than cost (README.md / DISCOVERY.md: hybrid LLM decision,
    2026-08-19). Never selected as a default — see llm/router.py."""

    def __init__(self, model: str | None = None):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Claude is an opt-in backend — "
                "set the key in sidecar/.env to enable it."
            )

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

    def generate(self, prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        return "".join(block.text for block in response.content if block.type == "text")
