from app.config import Settings
from app.models.schemas import CheckoutRequest, CheckoutResponse


class CheckoutService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_checkout(self, payload: CheckoutRequest) -> CheckoutResponse:
        if not self.settings.stripe_secret_key:
            return CheckoutResponse(
                checkoutUrl=f"{self.settings.frontend_url}/unlock/simulated?sceneId={payload.sceneId}",
                mode="simulated",
            )

        return CheckoutResponse(
            checkoutUrl=f"{self.settings.frontend_url}/unlock/stripe-placeholder?sceneId={payload.sceneId}",
            mode="stripe",
        )
