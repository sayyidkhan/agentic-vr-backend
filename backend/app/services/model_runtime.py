from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import Literal, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from pydantic import BaseModel

from app.config import Settings
from app.models.schemas import (
    EnabledModelResponse,
    ModelCatalogResponse,
    ModelProbeBatchResponse,
    ModelProbeResponse,
)


class ConfiguredModel(BaseModel):
    key: str
    label: str
    provider: str
    transport: Literal["bedrock", "openai"]
    modelId: str
    enabled: bool = True
    region: Optional[str] = None


class ModelRegistryFile(BaseModel):
    defaultModelKey: str
    models: list[ConfiguredModel]


class ModelRuntimeService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def registry(self) -> ModelRegistryFile:
        registry_path = Path(self.settings.model_registry_path)
        if not registry_path.is_absolute():
            registry_path = Path(__file__).resolve().parents[2] / registry_path

        body = json.loads(registry_path.read_text(encoding="utf-8"))
        registry = ModelRegistryFile.model_validate(body)
        enabled_models = [model for model in registry.models if model.enabled]
        if not enabled_models:
            raise ValueError(f"No enabled models found in registry: {registry_path}")
        return ModelRegistryFile(defaultModelKey=registry.defaultModelKey, models=enabled_models)

    def list_models(self) -> ModelCatalogResponse:
        models = [
            EnabledModelResponse(
                key=model.key,
                label=model.label,
                provider=model.provider,
                transport=model.transport,
                modelId=model.modelId,
                region=model.region,
                enabled=model.enabled,
                credentialSource=self._credential_source(model),
                credentialConfigured=self._credential_configured(model),
            )
            for model in self.registry.models
        ]
        return ModelCatalogResponse(defaultModelKey=self._default_model().key, models=models)

    def probe(self, prompt: str, model_key: str | None = None) -> ModelProbeResponse:
        model = self._resolve_model(model_key)
        if model.transport == "openai":
            return self._probe_openai(model=model, prompt=prompt)
        return self._probe_bedrock(model=model, prompt=prompt)

    def probe_all(self, prompt: str) -> ModelProbeBatchResponse:
        results = [self.probe(prompt=prompt, model_key=model.key) for model in self.registry.models]
        if all(result.status == "ok" for result in results):
            status = "ok"
        elif any(result.status == "ok" for result in results):
            status = "partial"
        else:
            status = "error"
        return ModelProbeBatchResponse(status=status, prompt=prompt, results=results)

    def _default_model(self) -> ConfiguredModel:
        for model in self.registry.models:
            if model.key == self.registry.defaultModelKey:
                return model
        return self.registry.models[0]

    def _resolve_model(self, model_key: str | None) -> ConfiguredModel:
        if not model_key:
            return self._default_model()
        for model in self.registry.models:
            if model.key == model_key:
                return model
        raise ValueError(f"Configured model not found: {model_key}")

    def _credential_source(self, model: ConfiguredModel) -> str:
        if model.transport == "openai":
            return "OPENAI_API_KEY"
        if self.settings.bedrock_api_key:
            return "AWS_BEARER_TOKEN_BEDROCK"
        return "AWS default credential chain"

    def _credential_configured(self, model: ConfiguredModel) -> bool:
        if model.transport == "openai":
            return bool(self.settings.openai_api_key)
        if self.settings.bedrock_api_key:
            return True
        try:
            return boto3.Session().get_credentials() is not None
        except BotoCoreError:
            return False

    def _probe_openai(self, model: ConfiguredModel, prompt: str) -> ModelProbeResponse:
        if not self.settings.openai_api_key:
            return ModelProbeResponse(
                status="error",
                modelKey=model.key,
                label=model.label,
                provider=model.provider,
                transport=model.transport,
                modelId=model.modelId,
                region=model.region,
                prompt=prompt,
                errorType="MissingCredential",
                errorMessage="OPENAI_API_KEY is not configured for this backend.",
            )

        payload = json.dumps(
            {
                "model": model.modelId,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt,
                            }
                        ],
                    }
                ],
                "max_output_tokens": 128,
            }
        ).encode("utf-8")
        request = urllib_request.Request(
            "https://api.openai.com/v1/responses",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.openai_api_key}",
            },
            method="POST",
        )

        try:
            with urllib_request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return ModelProbeResponse(
                status="error",
                modelKey=model.key,
                label=model.label,
                provider=model.provider,
                transport=model.transport,
                modelId=model.modelId,
                region=model.region,
                prompt=prompt,
                errorType=f"HTTP{exc.code}",
                errorMessage=body,
            )
        except urllib_error.URLError as exc:
            return ModelProbeResponse(
                status="error",
                modelKey=model.key,
                label=model.label,
                provider=model.provider,
                transport=model.transport,
                modelId=model.modelId,
                region=model.region,
                prompt=prompt,
                errorType=type(exc).__name__,
                errorMessage=str(exc.reason),
            )

        output_text = body.get("output_text") or self._extract_openai_output_text(body)
        return ModelProbeResponse(
            status="ok",
            modelKey=model.key,
            label=model.label,
            provider=model.provider,
            transport=model.transport,
            modelId=model.modelId,
            region=model.region,
            prompt=prompt,
            outputText=output_text,
        )

    def _probe_bedrock(self, model: ConfiguredModel, prompt: str) -> ModelProbeResponse:
        region = model.region or self.settings.bedrock_region
        if self.settings.bedrock_api_key:
            return self._probe_bedrock_with_bearer_token(model=model, prompt=prompt, region=region)

        try:
            client = boto3.client("bedrock-runtime", region_name=region)
            response = client.converse(
                modelId=model.modelId,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ],
                inferenceConfig={
                    "maxTokens": 128,
                    "temperature": 0.2,
                },
            )
            return ModelProbeResponse(
                status="ok",
                modelKey=model.key,
                label=model.label,
                provider=model.provider,
                transport=model.transport,
                modelId=model.modelId,
                region=region,
                prompt=prompt,
                outputText=self._extract_bedrock_output_text(response),
            )
        except NoCredentialsError:
            return ModelProbeResponse(
                status="error",
                modelKey=model.key,
                label=model.label,
                provider=model.provider,
                transport=model.transport,
                modelId=model.modelId,
                region=region,
                prompt=prompt,
                errorType="NoCredentialsError",
                errorMessage="No AWS credentials available to the backend. Attach an EC2 IAM role or configure AWS credentials.",
            )
        except ClientError as exc:
            error = exc.response.get("Error", {})
            return ModelProbeResponse(
                status="error",
                modelKey=model.key,
                label=model.label,
                provider=model.provider,
                transport=model.transport,
                modelId=model.modelId,
                region=region,
                prompt=prompt,
                errorType=error.get("Code", "ClientError"),
                errorMessage=error.get("Message", str(exc)),
            )
        except BotoCoreError as exc:
            return ModelProbeResponse(
                status="error",
                modelKey=model.key,
                label=model.label,
                provider=model.provider,
                transport=model.transport,
                modelId=model.modelId,
                region=region,
                prompt=prompt,
                errorType=type(exc).__name__,
                errorMessage=str(exc),
            )

    def _probe_bedrock_with_bearer_token(self, model: ConfiguredModel, prompt: str, region: str) -> ModelProbeResponse:
        url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model.modelId}/converse"
        payload = json.dumps(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ]
            }
        ).encode("utf-8")
        request = urllib_request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.bedrock_api_key}",
            },
            method="POST",
        )

        try:
            with urllib_request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return ModelProbeResponse(
                status="error",
                modelKey=model.key,
                label=model.label,
                provider=model.provider,
                transport=model.transport,
                modelId=model.modelId,
                region=region,
                prompt=prompt,
                errorType=f"HTTP{exc.code}",
                errorMessage=body,
            )
        except urllib_error.URLError as exc:
            return ModelProbeResponse(
                status="error",
                modelKey=model.key,
                label=model.label,
                provider=model.provider,
                transport=model.transport,
                modelId=model.modelId,
                region=region,
                prompt=prompt,
                errorType=type(exc).__name__,
                errorMessage=str(exc.reason),
            )

        return ModelProbeResponse(
            status="ok",
            modelKey=model.key,
            label=model.label,
            provider=model.provider,
            transport=model.transport,
            modelId=model.modelId,
            region=region,
            prompt=prompt,
            outputText=self._extract_bedrock_output_text(body),
        )

    @staticmethod
    def _extract_bedrock_output_text(response: dict) -> str:
        text_blocks: list[str] = []
        for block in response.get("output", {}).get("message", {}).get("content", []):
            block_text = block.get("text")
            if block_text:
                text_blocks.append(block_text)
        return "\n".join(text_blocks) if text_blocks else ""

    @staticmethod
    def _extract_openai_output_text(response: dict) -> str:
        text_blocks: list[str] = []
        for item in response.get("output", []):
            for content_item in item.get("content", []):
                if content_item.get("type") == "output_text" and content_item.get("text"):
                    text_blocks.append(content_item["text"])
        return "\n".join(text_blocks) if text_blocks else ""
