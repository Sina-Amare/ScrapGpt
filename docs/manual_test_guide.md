# ScrapeGPT — Manual Test Guide

A hands-on, human test checklist covering the auth/UX, password-reset/email,
activity-log, sibling-extraction, retry/error-handling, dropdown, and dev-tooling
work. Work top to bottom; each item is **Do → Expect**. Tick the boxes as you go.

> Three frontend unit tests (`scopeCopy — mode labels`) are **known pre-existing
> failures** unrelated to this work — ignore them. If retry ever 500s, grab the
> trace from `.dev-backend.err.log`.

---

## 0. Setup (do once)
- [ ] **DB migrated:** `alembic upgrade head` has been run (tables `password_reset_codes`, `project_events`, column `users.password_changed_at` exist).
- [ ] **Start servers:** `.\dev-start.ps1` (or backend + `npm run dev` manually). Open `http://127.0.0.1:5173`.
- [ ] **Hard-refresh** the browser (Ctrl+F5) so the new CSS/JS loads.
- [ ] **Providers:** have **at least 2** AI providers configured — needed for "retry with a different provider".
- [ ] **SMTP (optional):** if the `SMTP_*` vars are set in `.env`, emails send for real. Otherwise reset codes appear in **`.dev-backend.log`** (search `dev_code=`). Both paths are covered below.

---

## 1. Auth page — visuals (login/register)
- [ ] Watch the **background**: three soft drifting blobs (blue/teal/indigo), a faint moving grid, small glowing dots floating upward. → Alive but not distracting; the form card stays crisp.
- [ ] Click the **theme toggle** (top-right sun/moon). → The **whole page** switches light↔dark (not just the icon).
- [ ] In **light** theme, read **"Forgot password?"** and **"Create an account"**. → Clear blue links (not pale/washed-out).
- [ ] All label/subtitle text is readable in both themes (no near-invisible gray).

## 2. Login / Register / Logout
- [ ] **Register** a new account → lands in the app (Dashboard).
- [ ] **Log out** (header). → A **"Log out?" confirmation modal** appears. **Cancel** → stays logged in. **Logout → Log out** → returns to login.
- [ ] **Log in** with the account.
- [ ] **Theme persistence:** set dark, log out, reload, log back in, navigate. → Theme stays consistent everywhere (no flip-flop across login ↔ app).

## 3. Forgot password (full flow)
- [ ] On login, click **Forgot password?** (only shows when reset is enabled = SMTP set **or** dev mode).
- [ ] Enter your email → **Send reset code**. → Generic "if that email is registered, a code has been sent", then the code step.
- [ ] **Get the code:** from your inbox (SMTP) **or** `.dev-backend.log` (`dev_code=NNNNNN`). *(If you just enabled log redirection, run `.\dev-stop.ps1` then `.\dev-start.ps1` first.)*
- [ ] Enter code + new password → **Reset password** → success → **Back to sign in**.
- [ ] Sign in with the **new** password → works; old password → fails.
- [ ] **Enumeration check:** request a reset for a **non-existent** email → same generic success.
- [ ] **Bad code:** enter a **wrong** 6-digit code → generic "invalid or expired". After ~5 wrong tries the code is burned.

## 4. Session invalidation on reset (security)
- [ ] Log in on the app. In another tab, do a full password reset for that same account.
- [ ] Return to the **first** session and act. → It is **logged out / rejected** (old token predates the password change).

## 5. Emails (only if SMTP configured)
- [ ] **Welcome email:** register a fresh account → branded "Welcome to ScrapeGPT" HTML email.
- [ ] **Reset email:** trigger a reset → branded email with the 6-digit code in a boxed style (plain-text fallback exists too).

## 6. Providers page
- [ ] **Layout stability:** click **Test** on a provider. → "Testing…" shows **without** wrapping/pushing the Reveal/Edit/Delete buttons to a second row or jumping the row height.
- [ ] The **capability panel** appears above the table after the test.
- [ ] **Dropdown sanity:** open the provider **type** dropdown in Add/Edit → clean single-line labels, selects on the **first click**.

## 7. New Extraction — the dropdown bugs
- [ ] **New Extraction → Advanced options**.
- [ ] **AI provider** dropdown: each option reads cleanly like **`name (provider / model)`** — *not* `name, (,provider, / ,model,)`. Long names **truncate** (don't stretch the box); hover shows full text.
- [ ] Click a provider option **once** → selects immediately and the menu closes (no second click needed).
- [ ] **Guided cards:** "What are you extracting?" shows **Structured data** / **Content / documents** / **Let ScrapeGPT decide** as cards; selecting highlights it.
- [ ] **Render dropdown** is "How should ScrapeGPT load the page?" with plain options (Automatic / Static / Browser).

## 8. "Let ScrapeGPT decide" heuristic
- [ ] Submit a **GitHub repo URL** with mode left on **Let ScrapeGPT decide**. → After analysis, project Type = **CONTENT**.
- [ ] Submit a **shop/listing URL** with "decide". → Type = **STRUCTURED**.

## 9. Run an extraction end-to-end
- [ ] Submit a listing/table page (Structured). Watch QUEUED → ANALYZING → ready.
- [ ] Open the project: pick **Scope** ("This page only" is simplest), select **Fields**, run **Preview** (real sample rows), then **Extract**.
- [ ] **Results** → records render; **Download** CSV/JSON/XLSX works.

## 10. Sibling suggestion (page with both data kinds)
- [ ] Analyze a page with **both** structured rows and prose (e.g., a docs page with a table, or a GitHub README).
- [ ] In project **Overview**, a banner appears: *"This page also looks like it has … data — Also extract as Content/Structured."*
- [ ] Click it → a **new sibling project** starts for the same URL in the other mode; you're navigated to it; the original is untouched.

## 11. Activity Log (Dashboard)
- [ ] Create/run a project, go to **Dashboard**, scroll past "Recent projects" to **Activity log**.
- [ ] → Events appear within ~10s, grouped by project: **Analysis started → Analysis ready**, then **Extraction started → completed/failed**, plus **Canceled/Retried**.
- [ ] Filter chips work: **All / Errors / Warnings / Completed**. *(Only events created after the migration show — old projects have no history.)*

## 12. Retry & error handling (the big fix)
- [ ] **Force an analysis failure:** point a project at a provider/model that errors (or temporarily break a provider key) so it ends **FAILED** before analysis.
- [ ] The FAILED project shows a **guided message** (title + how-to-fix), not a raw error; raw text appears as a small "Details" line.
- [ ] A **"Retry with provider:"** dropdown appears next to **Retry** (analysis hadn't succeeded). Pick a **different** provider → **Retry**.
- [ ] → It **starts analyzing again** with the chosen provider — **no "Internal Server Error", no 500**, and the old error doesn't linger.
- [ ] **Regression check (original bug):** click Retry repeatedly/fast → it just works; you should **not** see "Internal Server Error" then "Only FAILED can be retried."
- [ ] **Analysis preserved:** if a project fails *after* analysis (extraction failure), the message says **"analysis is kept — retry continues from field setup"**, and Retry returns to field setup without re-running the AI.
- [ ] **Bot-protection path:** a `BOT_PROTECTION_BLOCKED` failure still shows the browser-session picker.

## 13. UI polish
- [ ] **Tab switching:** click between sidebar tabs quickly → instant switches, **no double-appear/flash**.
- [ ] **Scrolling under headers:** scroll a long page → the sticky top bar and project tab bar stay **solid** (content behind them is **not blurred**).
- [ ] **Help page:** the "1. URL → … → 6. Export" pipeline pills are **solid** (no fuzzy/translucent text).

## 14. Dev scripts (logs)
- [ ] `.\dev-start.ps1` prints the log paths; `.dev-backend.log` / `.dev-frontend.log` (+ `.err.log`) are created.
- [ ] Use the app, then `.\dev-stop.ps1`. → **All four** `.dev-*.log` files are deleted (including the **frontend** ones — the bug). Anything locked prints a yellow warning instead of silently lingering.

## 15. Reduced motion (optional, accessibility)
- [ ] Windows **Settings → Accessibility → Visual effects → Animation effects = Off**, reload login. → Aurora/grid/nodes are **static/hidden**, page still fully usable.
