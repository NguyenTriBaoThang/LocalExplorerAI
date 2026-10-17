import json
from types import SimpleNamespace

from openai.types.chat import ChatCompletionMessage


def reply(*calls, content=None):
    tool_calls = [
        {"id": f"call{i}", "type": "function",
         "function": {"name": name, "arguments": args if isinstance(args, str) else json.dumps(args)}}
        for i, (name, args) in enumerate(calls)
    ]
    msg = ChatCompletionMessage.model_validate({"role": "assistant", "content": content, "tool_calls": tool_calls})
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


class FakeClient:
    """Giả lập openai.OpenAI: trả lần lượt các response đã soạn sẵn."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def with_options(self, **options):
        self.options = options
        return self


class RoleClient:
    """LLM giả cho đa agent: mỗi kịch bản một hàng đợi riêng, chọn theo đoạn chữ có trong system prompt.

    Các chuyên gia chạy song song nên một hàng đợi chung (FakeClient) sẽ trả nhầm lượt.
    Phần tử là hàm thì được gọi lấy kết quả (dùng để ngủ hoặc ném lỗi muộn).
    """

    def __init__(self, scripts: dict[str, list]):
        self.scripts = {k: list(v) for k, v in scripts.items()}
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        system = kwargs["messages"][0]["content"]
        r = self.scripts[next(k for k in self.scripts if k in system)].pop(0)
        if callable(r):
            r = r()
        if isinstance(r, Exception):
            raise r
        return r

    def calls_for(self, key: str) -> list[dict]:
        return [c for c in self.calls if key in c["messages"][0]["content"]]

    def with_options(self, **options):
        self.options = options
        return self
