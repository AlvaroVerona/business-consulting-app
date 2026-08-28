import os

import ollama

# Ollama's own server default (4096, confirmed live via `ollama ps` on this
# machine) is smaller than what this app's own prompts need: a real project's
# full chunk-context dump (build_chunk_context) alone measured ~4171 tokens
# for the Fermento fixture — already over budget before the prompt template,
# question, or any other context is added. Ollama silently truncates a
# prompt that exceeds num_ctx rather than erroring, so this was a likely
# contributor to BusinessUnderstandingAgent's hallucination on Fermento
# (see notes/Backlog/Open questions.md) — the memo text may never have fully
# reached the model. 8192 gives headroom above the measured real-project
# size without a large VRAM/RAM cost for an 8B model.
_DEFAULT_NUM_CTX = 8192


class OllamaClient:
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1")
        self.num_ctx = int(os.getenv("OLLAMA_NUM_CTX", str(_DEFAULT_NUM_CTX)))

    def generate(self, prompt: str) -> str:
        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options={"num_ctx": self.num_ctx},
        )

        return response["message"]["content"]
