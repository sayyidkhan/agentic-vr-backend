# Stripe Payments Runbook

SceneVerse uses Stripe-hosted Checkout Sessions for one-time premium scene unlocks. The browser never receives Stripe secret keys. The frontend calls the backend, the backend creates the Checkout Session, and the frontend redirects the user to the returned Stripe-hosted URL.

## Current Integration

```text
frontend
  -> POST /api/checkout
  -> backend validates scene_id exists
  -> Stripe Checkout Session is created server-side
  -> backend returns checkoutUrl
  -> frontend redirects to checkout.stripe.com
  -> Stripe calls POST /api/webhooks/stripe
  -> backend verifies Stripe-Signature with STRIPE_WEBHOOK_SECRET
```

Relevant backend files:

- `backend/app/services/checkout.py`
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/.env.example`
- `infra/aws/sync-ec2-env.sh`
- `infra/aws/deploy-ec2-with-env.sh`

Current payment mode:

- `mode=payment`
- product name: `SceneVerse premium scene unlock`
- default currency: `sgd`
- default amount: `500` cents
- Stripe API version in code: `2026-05-27.dahlia`

## Environment Variables

Set these in `backend/.env` locally and sync them to EC2 with the deployment wrapper.

| Variable | Required | Purpose |
| --- | --- | --- |
| `STRIPE_SECRET_KEY` | Yes for real Stripe Checkout | Server-side Stripe API key. Must start with `sk_test_` in sandbox or `sk_live_` in live mode. Never expose this to the frontend. |
| `STRIPE_WEBHOOK_SECRET` | Yes for webhooks | Endpoint signing secret from Stripe. Must start with `whsec_`. Used to verify `Stripe-Signature`. |
| `STRIPE_CURRENCY` | Yes | Currency for inline Checkout price data. Current default is `sgd`. |
| `STRIPE_UNLOCK_AMOUNT_CENTS` | Yes | Unlock price in minor units. Current default is `500`, meaning SGD 5.00. |
| `FRONTEND_URL` | Yes | Used for Checkout `success_url` and `cancel_url`. |

If `STRIPE_SECRET_KEY` is blank, the backend intentionally falls back to simulated checkout:

```json
{
  "mode": "simulated",
  "checkoutUrl": "<frontend>/unlock/simulated?sceneId=..."
}
```

## Stripe Dashboard Setup

Use the correct Stripe workspace before creating keys or webhooks. Sandbox and live mode are separate, and webhook secrets are unique per endpoint.

1. Open the Stripe Dashboard.
2. Switch to the target workspace.
3. Stay in sandbox/test mode for development.
4. Get the secret key from API keys.
5. Create a webhook endpoint that points to the backend:

```text
http://18.207.53.115/api/webhooks/stripe
```

6. Enable these events:

```text
checkout.session.completed
checkout.session.expired
payment_intent.succeeded
payment_intent.payment_failed
```

7. Copy the webhook signing secret into `STRIPE_WEBHOOK_SECRET`.

The current sandbox endpoint created for this environment is:

```text
we_1TgR8cJyILD52AS4vdztWn3A
```

Do not store the actual `sk_*` or `whsec_*` values in docs, commits, screenshots, or chat.

## Local Setup

From the backend repo:

```bash
cd backend
cp .env.example .env
```

Set the Stripe values in `backend/.env`:

```bash
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_CURRENCY=sgd
STRIPE_UNLOCK_AMOUNT_CENTS=500
FRONTEND_URL=http://localhost:5173
```

Install dependencies and run the backend:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

## Deployment

Use the wrapper script when env values changed. It syncs runtime env first, then deploys backend code.

```bash
./infra/aws/deploy-ec2-with-env.sh
```

The wrapper calls:

```text
infra/aws/sync-ec2-env.sh
infra/aws/deploy-ec2-sync.sh
```

Remote env target:

```text
/opt/sceneverse-config/shared.env
```

Live backend base URL:

```text
http://18.207.53.115
```

## Smoke Tests

Health checks:

```bash
curl -fsS http://18.207.53.115/health
curl -fsS http://18.207.53.115/health/db
```

Checkout should return `mode=stripe` and a `checkout.stripe.com` URL when `STRIPE_SECRET_KEY` is configured:

```bash
curl -fsS -X POST http://18.207.53.115/api/checkout \
  -H 'content-type: application/json' \
  -d '{"sceneId":"scene_5a1aafdb7b58","unlockType":"premium_scene"}'
```

Unsigned webhook requests should fail with `400`:

```bash
curl -s -o /tmp/stripe_webhook_body.txt -w '%{http_code}\n' \
  -X POST http://18.207.53.115/api/webhooks/stripe \
  -H 'content-type: application/json' \
  -d '{}'
```

Expected result:

```text
400
```

Signed webhook requests should return `200` if the deployed `STRIPE_WEBHOOK_SECRET` matches the Stripe endpoint secret.

## Production Notes

The current sandbox webhook endpoint uses HTTP because the MVP backend is exposed directly on EC2. Before live payments, put HTTPS in front of the backend with a real domain and TLS certificate. Stripe's documented webhook URL format expects HTTPS for deployed endpoints.

Recommended next production steps:

- Add an HTTPS domain in front of EC2 through ALB, CloudFront, or Nginx with ACM/Let's Encrypt.
- Create separate live-mode Stripe keys and live webhook endpoint.
- Store secrets in AWS Secrets Manager or SSM Parameter Store instead of a synced env file.
- Persist paid unlock state in the database on `checkout.session.completed`.
- Add idempotency handling for repeated webhook delivery.
- Add product/price IDs if pricing becomes more than one simple inline price.

## Official Stripe References

- [Checkout Sessions API](https://docs.stripe.com/payments/checkout-sessions)
- [Checkout Sessions API reference](https://docs.stripe.com/api/checkout/sessions)
- [Webhook signature verification](https://docs.stripe.com/webhooks/signatures)
- [Set Stripe API version](https://docs.stripe.com/sdks/set-version)
