from typing import Any
from urllib.parse import urlencode

from app.config import Settings
from app.models.schemas import CheckoutLineItem, CheckoutRequest, CheckoutResponse


STRIPE_API_VERSION = "2026-05-27.dahlia"


class CheckoutError(RuntimeError):
    pass


class StripeWebhookError(ValueError):
    pass


class CheckoutService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_checkout(self, payload: CheckoutRequest) -> CheckoutResponse:
        if not self.settings.stripe_secret_key:
            query = urlencode(
                {
                    "sceneId": payload.sceneId,
                    "unlockType": payload.unlockType,
                    "mode": "agentic_commerce",
                }
            )
            return CheckoutResponse(
                checkoutUrl=f"{self.settings.frontend_url}/unlock/simulated?{query}",
                mode="simulated",
            )

        try:
            import stripe
        except ImportError as exc:
            raise CheckoutError("Stripe SDK is not installed.") from exc

        stripe.api_key = self.settings.stripe_secret_key
        stripe.api_version = STRIPE_API_VERSION

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                line_items=self._build_line_items(payload),
                metadata={
                    "sceneId": payload.sceneId,
                    "unlockType": payload.unlockType,
                    "agentName": self._metadata_value(payload.agentName),
                    "agentReason": self._metadata_value(payload.agentReason),
                    "itemCount": str(len(payload.items)),
                    "source": "sceneverse_agentic_commerce",
                },
                success_url=(
                    f"{self.settings.frontend_url}/unlock/success"
                    f"?session_id={{CHECKOUT_SESSION_ID}}&sceneId={payload.sceneId}"
                ),
                cancel_url=f"{self.settings.frontend_url}/unlock/cancel?sceneId={payload.sceneId}",
            )
        except Exception as exc:
            raise CheckoutError("Unable to create Stripe Checkout Session.") from exc

        checkout_url = session.get("url") if hasattr(session, "get") else getattr(session, "url", None)
        if not checkout_url:
            raise CheckoutError("Stripe Checkout Session did not return a checkout URL.")

        return CheckoutResponse(
            checkoutUrl=checkout_url,
            mode="stripe",
        )

    def _build_line_items(self, payload: CheckoutRequest) -> list[dict[str, Any]]:
        items = payload.items[:5] or [
            CheckoutLineItem(
                title="SceneVerse premium scene unlock",
                sourceTitle="SceneVerse",
                summary=f"Unlock type: {payload.unlockType}",
                quantity=1,
            )
        ]

        return [self._line_item(item, payload) for item in items]

    def _line_item(self, item: CheckoutLineItem, payload: CheckoutRequest) -> dict[str, Any]:
        name = item.title.strip() or "SceneVerse scene item"
        source = item.sourceTitle or "Agent-discovered scene item"
        description = item.summary or f"Recommended by {payload.agentName} from the current scene."
        product_metadata = {
            "sceneId": payload.sceneId,
            "unlockType": payload.unlockType,
            "sourceTitle": self._metadata_value(source),
            "sourceUrl": self._metadata_value(item.sourceUrl),
            "agentName": self._metadata_value(payload.agentName),
        }

        return {
            "quantity": item.quantity,
            "price_data": {
                "currency": self.settings.stripe_currency,
                "unit_amount": self.settings.stripe_unlock_amount_cents,
                "product_data": {
                    "name": name[:120],
                    "description": description[:800],
                    "metadata": product_metadata,
                },
            },
        }

    @staticmethod
    def _metadata_value(value: str | None) -> str:
        if not value:
            return ""
        return value[:500]

    def construct_webhook_event(self, *, payload: bytes, signature: str | None) -> Any:
        if not self.settings.stripe_webhook_secret:
            raise CheckoutError("Stripe webhook secret is not configured.")
        if not signature:
            raise StripeWebhookError("Missing Stripe-Signature header.")

        try:
            import stripe
        except ImportError as exc:
            raise CheckoutError("Stripe SDK is not installed.") from exc

        stripe.api_key = self.settings.stripe_secret_key
        stripe.api_version = STRIPE_API_VERSION

        try:
            return stripe.Webhook.construct_event(payload, signature, self.settings.stripe_webhook_secret)
        except ValueError as exc:
            raise StripeWebhookError("Invalid Stripe webhook payload.") from exc
        except stripe.error.SignatureVerificationError as exc:
            raise StripeWebhookError("Invalid Stripe webhook signature.") from exc
