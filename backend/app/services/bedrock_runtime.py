from __future__ import annotations

import json
from urllib import error as urllib_error
from urllib import request as urllib_request

from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
import boto3

from app.config import Settings
from app.models.schemas import BedrockProbeResponse


class BedrockRuntimeService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def probe(self, prompt: str) -> BedrockProbeResponse:
        provider = self.settings.bedrock_model_id.split(".", 1)[0]

        if self.settings.bedrock_api_key:
            return self._probe_with_bearer_token(provider=provider, prompt=prompt)

        try:
            client = boto3.client("bedrock-runtime", region_name=self.settings.bedrock_region)
            response = client.converse(
                modelId=self.settings.bedrock_model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt,
                            }
                        ],
                    }
                ],
                inferenceConfig={
                    "maxTokens": 128,
                    "temperature": 0.2,
                },
            )

            text_blocks = []
            for block in response.get("output", {}).get("message", {}).get("content", []):
                block_text = block.get("text")
                if block_text:
                    text_blocks.append(block_text)

            return BedrockProbeResponse(
                status="ok",
                provider=provider,
                modelId=self.settings.bedrock_model_id,
                region=self.settings.bedrock_region,
                prompt=prompt,
                outputText="\n".join(text_blocks) if text_blocks else "",
            )
        except NoCredentialsError:
            return BedrockProbeResponse(
                status="error",
                provider=provider,
                modelId=self.settings.bedrock_model_id,
                region=self.settings.bedrock_region,
                prompt=prompt,
                errorType="NoCredentialsError",
                errorMessage="No AWS credentials available to the backend. Attach an EC2 IAM role or configure AWS credentials.",
            )
        except ClientError as exc:
            error = exc.response.get("Error", {})
            return BedrockProbeResponse(
                status="error",
                provider=provider,
                modelId=self.settings.bedrock_model_id,
                region=self.settings.bedrock_region,
                prompt=prompt,
                errorType=error.get("Code", "ClientError"),
                errorMessage=error.get("Message", str(exc)),
            )
        except BotoCoreError as exc:
            return BedrockProbeResponse(
                status="error",
                provider=provider,
                modelId=self.settings.bedrock_model_id,
                region=self.settings.bedrock_region,
                prompt=prompt,
                errorType=type(exc).__name__,
                errorMessage=str(exc),
            )

    def _probe_with_bearer_token(self, provider: str, prompt: str) -> BedrockProbeResponse:
        url = (
            f"https://bedrock-runtime.{self.settings.bedrock_region}.amazonaws.com/"
            f"model/{self.settings.bedrock_model_id}/converse"
        )
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
            return BedrockProbeResponse(
                status="error",
                provider=provider,
                modelId=self.settings.bedrock_model_id,
                region=self.settings.bedrock_region,
                prompt=prompt,
                errorType=f"HTTP{exc.code}",
                errorMessage=body,
            )
        except urllib_error.URLError as exc:
            return BedrockProbeResponse(
                status="error",
                provider=provider,
                modelId=self.settings.bedrock_model_id,
                region=self.settings.bedrock_region,
                prompt=prompt,
                errorType=type(exc).__name__,
                errorMessage=str(exc.reason),
            )

        text_blocks = []
        for block in body.get("output", {}).get("message", {}).get("content", []):
            block_text = block.get("text")
            if block_text:
                text_blocks.append(block_text)

        return BedrockProbeResponse(
            status="ok",
            provider=provider,
            modelId=self.settings.bedrock_model_id,
            region=self.settings.bedrock_region,
            prompt=prompt,
            outputText="\n".join(text_blocks) if text_blocks else "",
        )
