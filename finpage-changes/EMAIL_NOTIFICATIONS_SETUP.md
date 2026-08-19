# Portfolio-change email notification setup

## What this change does

Every time "Submit reviewed table to Excel" on the [algo-helper page](src/pages/algo-helper.py) saves successfully, the app sends an email summarizing the change: which portfolio (model window), the effective date, which tickers are incoming, which are outgoing, which are unchanged, and a link to `https://finpage.onrender.com/portfolio-daily`. [email module](src/email_notify.py)

Email is sent through [Resend](https://resend.com)'s HTTP API. If `RESEND_API_KEY` is not configured, the save still completes normally; the status message just notes that the notification email was not sent. A save is never blocked or rolled back by an email failure. [email module](src/email_notify.py)

The "Save edits to Excel" editor (direct edits to the currently saved sheet) does **not** send an email — only the build-review-submit flow does, since that's the one with a clear incoming/outgoing ticker diff.

## One-time setup

1. Create a free [Resend](https://resend.com) account.
2. Verify a sending domain, or use Resend's shared test sender (`onboarding@resend.dev`) if you don't want to verify a domain yet — it can send to your own verified account email even before domain verification.
3. Create an API key in Resend's dashboard.
4. In Render's **Environment** page for the web service, add:

   ```text
   RESEND_API_KEY=the_resend_api_key
   EMAIL_FROM=Finpage Algo Helper <onboarding@resend.dev>
   EMAIL_TO=jonas_fbh@hotmail.com
   ```

   `EMAIL_FROM` and `EMAIL_TO` are optional — they default to the values above if omitted, once you've verified a domain you can change `EMAIL_FROM` to that domain's address. `EMAIL_TO` accepts a comma-separated list to notify multiple recipients, e.g. `EMAIL_TO=jonas_fbh@hotmail.com,someoneelse@example.com`.

5. Save and deploy. No code change or redeploy is needed if you're just adding/rotating the API key later — Render environment variables are read at request time.

## Normal operation

After a successful save, the page's status message will show either "Notification email sent." or a specific reason it wasn't (e.g. missing API key, Resend API error), so you always know the save itself succeeded independent of email delivery. [algo-helper callback](src/pages/algo-helper.py)
