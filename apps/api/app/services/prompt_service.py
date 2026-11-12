import json
from collections.abc import Sequence
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.adapters.llm.provider import Attachment, StructuredOutputProvider
from app.prompts.registry import PromptCatalog, catalog


OutputModel = TypeVar("OutputModel", bound=BaseModel)


class InvalidStructuredOutput(RuntimeError):
    pass


class PromptRunner:
    """Loads versioned templates and validates every model response before use."""

    def __init__(self, provider: StructuredOutputProvider, prompt_catalog: PromptCatalog = catalog):
        self.provider = provider
        self.catalog = prompt_catalog

    def run(self, prompt_id: str, user_input: dict[str, Any], output_model: type[OutputModel], attachments: Sequence[Attachment] = ()) -> OutputModel:
        definition = self.catalog.get(prompt_id)
        schema = output_model.model_json_schema()
        # Canonical JSON serialization keeps the prompt input stable and auditable.
        safe_input = json.loads(json.dumps(user_input, ensure_ascii=False, default=str))
        # Providers written before attachments existed keep their three-argument signature.
        extra = {"attachments": attachments} if attachments else {}
        raw_output = self.provider.generate(definition.system_prompt, safe_input, schema, **extra)
        try:
            return output_model.model_validate(raw_output)
        except ValidationError as error:
            raise InvalidStructuredOutput(f"{prompt_id} returned data outside its declared schema.") from error
