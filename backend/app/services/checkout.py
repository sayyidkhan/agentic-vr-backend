from app.config import Settings
from app.models.schemas import CheckoutRequest, CheckoutResponse


STRIPE_API_VERSION = "2026-02-25.clover"


class CheckoutError(RuntimeError):
    pass


class StripeWebhookError(ValueError):
    pass


class CheckoutService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_checkout(self, payload: CheckoutRequest) -> CheckoutResponse:
        if not self.settings.stripe_secret_key:
            return CheckoutResponse(
                checkoutUrl=f"{self.settings.frontend_url}/unlock/simulated?sceneId={payload.sceneId}",
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
                line_items=[
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": self.settings.stripe_currency,
                            "unit_amount": self.settings.stripe_unlock_amount_cents,
                            "product_data": {
                                "name": "SceneVerse premium scene unlock",
                                "description": f"Unlock type: {payload.unlockType}",
                            },
                        },
                    }
                ],
                metadata={"sceneId": payload.sceneId, "unlockType": payload.unlockType},
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

    def construct_webhook_event(self, *, payload: bytes, signature: str | None) -> dict:
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
