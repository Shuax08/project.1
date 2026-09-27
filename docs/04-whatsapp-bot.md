# WhatsApp customer bot

This build processes Meta Cloud API `messages` webhooks. POST requires a valid `X-Hub-Signature-256` computed with `WHATSAPP_APP_SECRET`. The shop is identified only by `metadata.phone_number_id` in the signed payload. Message IDs are stored to avoid creating the same order twice on retries. Replies use the Meta Messages API.

Commands: `START`, `MENU`, `ADD <item-number> <quantity>`, `CART`, `REMOVE <item-number>`, `CLEAR`, `NAME <name>`, `CONFIRM CASH`, `CONFIRM CREDIT` (requires enabled credit), `STATUS`, `HELP`. WhatsApp shared location is supported for shops with a safe zone. Prices come from the database at order confirmation. CASH remains unpaid until collected; CREDIT creates a ledger entry.

Natural text such as “2 chicken biriyani” and a payment gateway are not implemented. A new order sends a notification to the first linked active owner or manager number. If delivery fails, the webhook requests a retry without creating another order. Order status can be changed through the authenticated owner API or the linked owner's WhatsApp number; status change notifications to customers are not implemented.

## Owner commands

After verifying the owner's number independently, link it with `flask --app server link-owner-whatsapp --slug demo --email owner@example.com --phone 9715XXXXXXXX`. The number must use international digits without `+`. This server-side link is the authorization step; a message body cannot claim owner access. Owner commands: `PENDING`, `ORDER <id>`, `ACCEPT <id>`, `REJECT <id>`, `PREPARING <id>`, `READY <id>`, `DELIVERED <id>`, `SALES`, `HELP`. Status transitions are checked and audited; cross-shop orders are hidden.

To try both bots without Meta credentials, run `flask --app server simulate-whatsapp --slug demo --from-phone 9715XXXXXXXX --message MENU` after adding a menu item. Use an unlinked number for customer commands and the linked number for owner commands. Run one command at a time; state is stored in the configured database. This local command does not send real WhatsApp messages or owner notifications.

## Live test

1. Create a Meta app with a WhatsApp Cloud API test number. Register your own WhatsApp number as a test recipient in Meta's dashboard.
2. Put a random `WHATSAPP_VERIFY_TOKEN`, the Meta app secret in `WHATSAPP_APP_SECRET`, and the Meta access token in `WHATSAPP_ACCESS_TOKEN` in local `.env`. Do not commit them.
3. Run `flask --app server db upgrade`, then `flask --app server bootstrap --slug demo --name "Demo Shop" --email owner@example.com` and set a password at the prompt.
4. Run `flask --app server add-menu-item --slug demo --name "Chicken Biriyani" --price 15.00`.
5. Run `flask --app server configure-whatsapp --slug demo --phone-number-id YOUR_META_PHONE_NUMBER_ID --display-number YOUR_META_TEST_NUMBER`. The number ID and display number are different values.
6. Expose the Flask service through public HTTPS. In Meta set callback URL `https://YOUR_DOMAIN/webhooks/whatsapp`, enter the same verify token, and subscribe to `messages`.
7. From the registered recipient send `START` to the Meta test number, followed by `MENU`, `ADD <id> 2`, `NAME Your Name`, `CONFIRM CASH`, and `STATUS`.

The server must be reachable over HTTPS for callbacks. On outbound failure the webhook returns 503 for a retry; the inbound message ID prevents duplicate order creation.
