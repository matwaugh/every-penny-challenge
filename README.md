# Every Penny Challenge

A front-end demonstration for OSCAR’s Paediatric Brain Tumour Charity. The interface keeps the simulation warning in the top strip, with the supplied original charity logo in the coloured challenge panel; other wording follows the intended donor experience. Donors have no application account or sign-out control. Manual selection remains available directly through the artwork/grid; Shuffle and clear sit together. Group 1 extends the original artwork and manual grid with square-based progress, automatic selection, simulated reservations and checkout, acknowledgements, and owner review.

**No real payments are taken. Use fictional details only.** There are no application accounts, backend, donor email collection, payment integration or cross-device state.

## Run locally

Use the existing checkout. Cloud tasks already run in isolation; do not create a Git worktree unless explicitly requested.

```sh
cd /workspace/every-penny-challenge
python3 -m http.server 8000 --bind 127.0.0.1
```

The app needs no package installation or build. `index.html` loads `core.js` (rules) and `app.js` (screens and session storage). The original canvas-based artwork generator is retained and its results cached by level. A limited £10 layout adjustment collapses empty inter-glyph columns, reduces lattice gaps and removes excess frame height; the wider artwork redesign remains deferred. For cloud onboarding, use the loopback server for internal validation only; the user-facing review site is the protected Cloudflare preview.

## Required checks before preview updates or merge

```sh
node --test tests/core.test.cjs
python3 -m unittest discover -s tests -p 'test_browser.py' -v
```

The cloud environment already supplies Node 24, Python 3.12, Python Playwright 1.62.0 and Chromium at `/usr/bin/chromium`. The browser tests start and stop their own local HTTP server. All test identities and messages are synthetic. These checks run locally; no paid CI service or GitHub Actions workflow has been activated. Verify GitHub plan allowances and obtain agreement for any potential charges before introducing hosted automation.

The rules suite covers integer-pence arithmetic, progress boundaries, balanced/exact allocation, sparse availability, reservation expiry/replacement, duplicate returns, minimum enforcement and approval/release. Browser tests cover all three levels, desktop and mobile layouts, selection editing, cancellation, reload, session recovery, pending/approved totals, expiry while checkout is open, keyboard focus, clipboard, acknowledgements and storage failure. Tests reject JavaScript errors and external requests during the donation journey. Physical iOS/Android, Safari and live payment-provider behaviour are not validated by these tests.

## Prototype behaviour

- Standard levels contain 200, 500 or 1,000 distinct integer-pence squares. Level names are maximum square values, not fundraising totals.
- Progress uses approved distinct squares / total squares. Display normal whole-percentage rounding, `0%` for none, `<1%` when positive progress rounds to zero, at most `99%` while incomplete, and `100%` only when all squares are approved.
- Approved monetary totals are computed from approved claims separately from square completion. Approval in this prototype is never payment verification. There is no UI for production-only unallocated or offline donations.
- Automatic proposals find an exact total using a varied, small allocation first, with an exact subset-sum fallback for sparse availability. Around 5–10 squares is preferred for £10 where feasible. No silent change to the donation value or monetary top-up. A new proposal replaces the selection, as explained beside the controls; manual edits and clear remain available.
- Minimum is strictly £2. The owner approved this temporary Group 1 handling: if the remaining available squares total less than £2, explain the limitation and block checkout. The final-remainder production exception is still unresolved.
- Selecting squares does not reserve them. Entering simulated checkout creates a unique `EPC-######` reference and a 30-minute reservation. The compact checkout shows the amount, reservation time, fundraiser name, Cancel/Complete donation controls and a small reference; individual square values remain on the selection and acknowledgement screens. Its donor-facing copy describes squares as reserved until marked complete, while the underlying returned claim still becomes pending exactly once and requires approval before advancing progress. Cancel/expiry releases the reservation; eligible details and selection can be recovered up to one hour after their last edit, without extending reservation time. New checkout attempts use a new reference.
- The donor key combines checkout reservations and pending claims as “Awaiting approval”, using the same pale fill; the dashboard retains their separate counts and expiry semantics. Selection is solid orange and approval solid teal, matching their key swatches without disabled-button fading. Reserved, pending, approved and available counts are exclusive. Expired reservations do not count as reserved. Pending claims cannot advance approved amount or completion. Approval and release require confirmation and update counts immediately. Actions are synchronous local transactions with rollback on persistence failure; no backend queue, API polling, audit service or artificial delays are introduced. Duplicate review/return transitions are rejected by the rules.
- Dashboard figures refresh every 60 seconds while visible, immediately on return to the tab, and after local actions. The open checkout clock also checks expiry each second. There is no network polling, so network refresh failure/retry UI and server idempotency remain production concerns.
- The thank-you screen shows the amount, exact square values, reference/copy, and current simulated approval status in the originating tab session. A fresh session visiting the thank-you URL sees only a generic acknowledgement. Sharing copies/shares the protected demo URL, not fictional fundraiser data. Broader Group 2 sharing is deferred.
- Amount raised and Squares approved appear in a compact row inside the white graphic panel, above its coloured graphic area. On mobile, this graphic panel precedes donation-value controls. Minimum-donation feedback appears only when needed, rather than as a standing note. The compact header uses the original logo; Graphic/Grid controls sit inside the graphic’s top-right corner. Square values appear immediately on pointer hover or keyboard focus, rather than using delayed native browser tooltips. Find Squares sits beside the donation-value label and enables when a valid amount of at least £2 has been entered. Manual grid controls and selection-removal controls have practical tap sizes. Artwork remains optional for choosing squares.

## Data and storage

New demo state uses `sessionStorage` under `epc-group1-session-v1`, not persistent local storage. Browser session restoration may restore it. Reset clears the current fictional challenge, its receipt and draft. Closing a tab normally ends its session; neither closing nor resetting is a production data-erasure guarantee.

The older proof of concept used `oscars-demo-v4-*` local storage. Its entries are not read, migrated, modified or deleted by Group 1, preserving the old demo's data separately. Do not enter real personal information in either version. Owner review mode resets on reload and is explicitly simulated. Each tab has its own simulation; browser tab duplication can copy session state initially. This is not a concurrency-safe reservation system.

## Private preview and release

- Development branch: `development/group-1`. Original demo is preserved at commit `a0502c7854ab409a43ec31cc67494e7e6ce40699`.
- Cloudflare Pages project: `every-penny-challenge`; its deployment branch is `preview-setup`, not `main`.
- User review address: `https://every-penny-challenge.pages.dev`.
- Cloudflare Access must protect **both** `every-penny-challenge.pages.dev` and `*.every-penny-challenge.pages.dev`, including immutable deployment addresses. Both applications must allow only the saved exact-email policy `Preview owner only`; no broad Allow or Bypass policy. The owner signed in successfully using the Cloudflare identity provider; email one-time PIN delivery was not working. Never weaken protection to bypass a login issue.
- Access protection was checked by the owner in an incognito browser before application upload. The developer cannot inspect the owner's Cloudflare session. Confirm actual deployment completion and sign-in behaviour separately from local tests and successful Git pushes.
- Public test link: `https://matwaugh.github.io/every-penny-challenge/`, served from `main` at the repository root with `.nojekyll` for the plain static files. Publication was authorised by the owner on 10 November 2026; enabling Pages and confirming its live deployment are separate from a successful Git push.
- Push tested development commits to `preview-setup` to update the protected review site. Do not merge into or push `main`, republish GitHub Pages, add a custom domain, or change the public test site without explicit approval for the reviewed version.
- Use only the existing Pages/Workers Free and Zero Trust Free subscriptions. Static hosting requests are free; Pages Free has 500 builds/month. Access blocks additional users when its seat allowance is full. Paid Workers upgrades start at US$5/month plus usage; additional products can have separate charges. No upgrades, purchased seats, domains, metered add-ons, real payment services or other potential costs are authorised. Check current terms before recommending any service change.
- Cloudflare integration can create protected previews for pushed development branches. Every hostname must remain covered by Access. The temporary personal Cloudflare account is not the charity's final production account; plan to recreate hosting and Access configuration under charity ownership before launch.

Production work (provider validation, Supabase, real authentication, server-authoritative allocation, security/retention operations, email, lifecycle and full sharing) remains outside Group 1. Do not treat this demonstration as production-ready.

For any future pull request: have the relevant tests passed, and have operational, security and setup instructions been updated where necessary?
