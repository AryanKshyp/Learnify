# Putting Learnify online

This turns the repo into a website anyone can use: they open a URL, create an account, connect
their own AI account, and start. No GitHub, no Docker, no terminal on their side.

**Architecture:** one container (Render) serves the web app and the API on one address.
Supabase provides the Postgres database and the sign-in. Each user's data is private to their
account, and each user's AI usage is billed to **their own** AI account - you pay for hosting
only, never for inference.

Expect about 30 minutes the first time.

## 1. Supabase (database + sign-in)

1. Create a project at supabase.com. Choose a region near your users.
2. **Project Settings → API**: copy the **Project URL** and the **anon public** key.
3. **Project Settings → Database → Connection string → Session pooler**: copy it. Replace the
   scheme so it starts `postgresql+psycopg://` and put your database password in.
   Use the *session* pooler (not "transaction", not "direct"): direct is IPv6-only, which Render
   cannot reach, and the transaction pooler breaks prepared statements.
4. **Authentication → Providers → Email** is on by default. Under **Authentication → URL
   Configuration**, set **Site URL** to your final address (step 2 gives it to you; come back
   and set it, or sign-up emails will link to the wrong place).
5. **Project Settings → Data API**: you can switch the Data API off. The app does not use it, and
   the migration already denies it all access (row level security with no policies), so this is
   belt and braces.

## 2. Render (the app)

1. Push this repo to your own GitHub account.
2. In Render: **New → Blueprint**, pick the repo. It reads `render.yaml`.
3. Fill in the four secrets it asks for:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | the session-pooler string from step 1.3 |
   | `SUPABASE_URL` | the Project URL |
   | `SUPABASE_ANON_KEY` | the anon public key |
   | `SECRETS_ENCRYPTION_KEY` | generate once: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

   `SECRETS_ENCRYPTION_KEY` encrypts the AI keys users save. **Back it up and never change it:**
   changing it makes every saved key unreadable and everyone must re-enter theirs.
4. Deploy. The first start runs the database migrations itself.
5. Open the URL Render gives you. Go back to Supabase and set **Site URL** to it (step 1.4).

The server **refuses to start** in production unless accounts, the database and the encryption
key are all configured. That is deliberate: a misconfiguration fails loudly instead of quietly
serving everyone one shared account. If a deploy fails, read the log first - it says which.

## 3. Letting people use their own AI

Users do this themselves in **Settings**:

- **Connect OpenRouter** - one click; they sign in at OpenRouter and sessions use their credits.
  This is the only provider that lets an app act on a user's account without a pasted key.
- **Paste a key** - Anthropic, OpenAI or Google Gemini.

Claude.ai and ChatGPT *subscriptions* cannot be used this way: those providers do not allow
third-party apps to spend a consumer subscription. Users need an API key or OpenRouter credit.

## Running it without accounts (your own machine)

Leave the Supabase variables unset and `ENVIRONMENT` unset: it runs as a single local user,
exactly as `RUNNING.md` describes.

## Before real users arrive

- **Terms and privacy.** The app stores people's assessment answers' *scores* and their
  encrypted AI keys. Publish a privacy policy that says so.
- **Backups.** Turn on Supabase's backups; the evidence history is the product.
- **Email.** Supabase's built-in email sender is rate-limited. Add your own SMTP under
  Authentication → SMTP before launch.
- **Abuse.** Each AI call is paid by the user, so there is no inference bill to run up, but add
  rate limiting at your host or CDN if you expect hostile traffic.
