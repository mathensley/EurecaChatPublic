from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

class TokenCounterCallback(AsyncCallbackHandler):
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0

    async def on_llm_end(self, response: LLMResult, **kwargs):
        for generations in response.generations:
            for gen in generations:
                usage = getattr(gen.message, "usage_metadata", None) if hasattr(gen, "message") else None
                if usage:
                    self.input_tokens  += usage.get("input_tokens", 0)
                    self.output_tokens += usage.get("output_tokens", 0)
                    self.total_tokens  += usage.get("total_tokens", 0)