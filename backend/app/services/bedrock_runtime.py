from __future__ import annotations

from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
import boto3

from app.config import Settings
from app.models.schemas import BedrockProbeResponse


class BedrockRuntimeService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def probe(self, prompt: str) -> BedrockProbeResponse:
        provider = self.settings.bedrock_model_id.split(".", 1)[0]

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
