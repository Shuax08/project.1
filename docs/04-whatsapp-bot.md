# WhatsApp customer bot

This build processes Meta Cloud API `messages` webhooks. POST requires a valid `X-Hub-Signature-256` computed with `WHATSAPP_APP_SECRET`. The shop is identified only by `metadata.phone_number_id` in the signed payload. Message IDs are stored to avoid creating the same order twice on retries. Replies use the Meta Messages API.

Commands: `START`, `MENU`, `ADD <item-number> <quantity>`, `CART`, `REMOVE <item-number>`, `CLEAR`, `NAME <name>`, `CONFIRM CASH`, `CONFIRM CREDIT` (requires enabled credit), `STATUS`, `HELP`. WhatsApp shared location is supported for shops with a safe zone. Prices come from the database at order confirmation. CASH remains unpaid until collected; CREDIT creates a ledger entry.

Natural text such as “2 chicken biriyani”, an owner bot, a payment gateway, and automated owner notification are not implemented. Order status can be changed through the authenticated owner API.

## Live test

1. Create a Meta app with a WhatsApp Cloud API test number. Register your own WhatsApp number as a test recipient in Meta's dashboard.
2. Put a random `WHATSAPP_VERIFY_TOKEN`, the Meta app secret in `WHATSAPP_APP_SECRET`, and the Meta access token in `WHATSAPP_ACCESS_TOKEN` in local `.env`. Do not commit them.
3. Run `flask --app server db upgrade`, then `flask --app server bootstrap --slug demo --name "Demo Shop" --email owner@example.com` and set a password at the prompt.
4. Run `flask --app server add-menu-item --slug demo --name "Chicken Biriyani" --price 15.00`.
5. Run `flask --app server configure-whatsapp --slug demo --phone-number-id YOUR_META_PHONE_NUMBER_ID --display-number YOUR_META_TEST_NUMBER`. The number ID and display number are different values.
6. Expose the Flask service through public HTTPS. In Meta set callback URL `https://YOUR_DOMAIN/webhooks/whatsapp`, enter the same verify token, and subscribe to `messages`.
7. From the registered recipient send `START` to the Meta test number, followed by `MENU`, `ADD <id> 2`, `NAME Your Name`, `CONFIRM CASH`, and `STATUS`.

The server must be reachable over HTTPS for callbacks. On outbound failure the webhook returns 503 for a retry; the inbound message ID prevents duplicate order creation.
