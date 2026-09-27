# BetBoy customer portal (DE / EN)

Separate Django 5.2 service in the existing repository. **Pre-launch:** no live
Stripe account, SMTP delivery, legal pages, public-domain cutover or native
Store apps have been completed. The production Streamlit app stays in personal
mode unless `BETBOY_CUSTOMER_ACCESS_REQUIRED=1` is explicitly configured.

## Local preview / tests (PowerShell, repository root)

```powershell
.\.venv\Scripts\python.exe -m venv .portal-venv
.\.portal-venv\Scripts\python.exe -m pip install -r portal/requirements.txt
$env:BETBOY_PORTAL_DEV='1'
.\.portal-venv\Scripts\python.exe portal/manage.py migrate --noinput
.\.portal-venv\Scripts\python.exe portal/manage.py runserver 127.0.0.1:8010 --noreload
```

Open `http://127.0.0.1:8010/de/` or `/en/`. Registration/payment are intentionally
closed in the unconfigured preview. A development secret is ephemeral unless
supplied through `BETBOY_PORTAL_SECRET`; do not expose development mode publicly.
The preview creates only `portal/.runtime/customers.sqlite3`, not sports data.

```powershell
.\.portal-venv\Scripts\python.exe portal/manage.py test members --settings=siteconfig.qa_settings --noinput
.\.venv\Scripts\python.exe -m pytest tests/test_customer_access.py tests/test_account_identity.py tests/test_workflow_integrity.py tests/test_daily3_ui.py -q
```

Portal tests use an in-memory database and local mail outbox; Stripe responses
are simulated. They do **not** prove live payment, email delivery or Store acceptance.
No real credentials are stored in source or required by the tests.

## Payment contract

- Authenticated, email-confirmed customers choose a server-owned plan ID.
- Stripe-hosted Checkout: CHF 990/1990/2990 cents monthly, inclusive tax,
  quantity one, licensed recurring price. No client amount or redirect override.
- Stripe API version used by pinned SDK: `2026-08-26.dahlia`. Configure the
  webhook endpoint to this version. Requalify payload fixtures on SDK upgrades.
- `billing/stripe/webhook/` verifies the signature over the exact request bytes.
  Subscription ownership is tied to the saved Stripe customer and account UUID,
  not an unverified email address, success URL, mobile field or browser flag.
- Event IDs are idempotent. Current subscription is re-read while serialized per
  customer. A matching paid invoice must cover the exact current billing period.
- Refund/dispute places a persistent billing hold, including if it arrives before
  the subscription event. This conservative hold needs operator review; an older
  paid event must not restore access. Do not promise automatic dispute resolution.
- Cancellation at period end keeps paid access. Failed/unpaid/expired/trial
  subscriptions do not unlock it. No trial was requested.
- Stripe Billing Portal: cancellation, invoices and payment methods. Do **not**
  enable immediate prorated tier changes in Stripe yet: that lifecycle is not
  implemented. Schedule tier changes for period end or implement/test proration.
- Missing webhook deliveries need a read-only Stripe reconciliation job and alert
  before unattended commercial operation. No new scheduler has been installed.

## Production cutover checklist (not executed)

1. Confirm operator identity, final domain, support sender, legal/privacy/terms,
   sale-country and payment-provider approval. World-language support is not
   automatic permission to sell in every country.
2. Activate Stripe and test account. Create the three **approved** monthly prices
   (CHF 9.90 / 19.90 / 29.90, tax-inclusive), enable Stripe Tax as appropriate,
   publish terms in Checkout, and configure cancellation portal. Configure
   approved billing-country restrictions at Stripe as well as app eligibility;
   otherwise customers outside the access allowlist could pay without access.
   This is an explicit launch blocker until tested, not a completed geo-control.
3. Subscribe to `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
   `customer.subscription.created/updated/deleted`, `invoice.paid`,
   `invoice.payment_failed`, `charge.refunded`, `charge.dispute.created`.
4. Store secrets in protected `/etc/betboy/portal.env`, **not Git/chat**. Use the
   environment names in `.env.example`. Give the portal a separate virtualenv
   and `/var/lib/betboy-portal` (0700). No new backup is created by this code.
5. Install reviewed `deploy/systemd/betboy-portal.service.example` only after
   configuring its state directory; migrate the new customer database and run
   `collectstatic`. Never point the portal at any existing BetBoy database.
6. Configure the reviewed Caddy template for the real host. It hides `/internal/*`,
   serves portal assets, and routes `/app/*` to Streamlit. Streamlit needs
   `--server.baseUrlPath=app` and loopback binding. Never publish port 8501 directly.
   Share only `BETBOY_PORTAL_INTERNAL_TOKEN` with Streamlit, not Stripe/SMTP secrets.
7. Run `manage.py check --deploy` and `manage.py check_customer_launch` (no external
   calls). Then prove actual inbox delivery, sandbox checkout, webhook replay,
   cancellation, refund, feature denial, account isolation and expired cookies
   in the **deployed** two-service/proxy layout before opening registration.
8. Keep existing personal browser records intact. No ownership transfer is
   inferred from someone logging in from the same browser. Provide a separate
   verified migration if those records need to move into a customer account.
9. Enable live payments only after explicit commercial launch readiness. No
   global paywall cutover was performed by adding these files.

## Mobile boundary

The website is responsive; **there is no native iOS/Android project yet**.
The customer model can represent provider-specific entitlements, but no Apple/
Google receipt is accepted by a client endpoint and no Store adapter exists.
Native authentication, StoreKit/Play Billing verification, restore purchases,
server notifications, account deletion, device builds and Store submissions
remain separate work. Do not substitute Stripe links for required in-app billing.

The existing analysis workspace is still German. DE/EN coverage in this release
is the landing page and customer/account flows, not every historical analysis UI.
