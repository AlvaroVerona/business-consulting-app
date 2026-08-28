import src.llm.ollama_client as ollama_client_module
from src.llm.ollama_client import OllamaClient


class _FakeOllamaModule:
    def __init__(self):
        self.calls: list[dict] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return {"message": {"content": "ok"}}


def test_generate_passes_num_ctx_option(monkeypatch):
    fake = _FakeOllamaModule()
    monkeypatch.setattr(ollama_client_module, "ollama", fake)

    OllamaClient(model="llama3.1").generate("hello")

    assert len(fake.calls) == 1
    assert fake.calls[0]["options"] == {"num_ctx": 8192}


def test_num_ctx_is_configurable_via_env(monkeypatch):
    fake = _FakeOllamaModule()
    monkeypatch.setattr(ollama_client_module, "ollama", fake)
    monkeypatch.setenv("OLLAMA_NUM_CTX", "16384")

    OllamaClient(model="llama3.1").generate("hello")

    assert fake.calls[0]["options"] == {"num_ctx": 16384}
