import os

import ollama


class OllamaClient:
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1")

    def generate(self, prompt: str) -> str:
        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )

        return response["message"]["content"]
