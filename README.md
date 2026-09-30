# NextRung

Career guidance from people one rung ahead.

NextRung is a two-sided career platform. Learners, from final-year students to experienced professionals, book one-to-one sessions with verified working professionals ("guides") in their field. Guides set their own services and prices, accept requests, run sessions and share scorecards.

**Live site:** https://adityabankar266.github.io/nextrung/

## What works

| Area | What it does |
|---|---|
| Accounts | Sign up as a learner or a guide, sign in, reset password by email |
| Guide directory | Public list of verified guides, filter by field, profile with services and reviews |
| Booking | Learners request a service at a date and time (IST); prices are locked at booking time |
| Learner dashboard | Upcoming and past sessions, meeting links, cancel, scorecards, star ratings, profile |
| Guide dashboard | Requests to accept or decline, meeting links, mark completed, write scorecards, manage services, earnings this month after the platform fee, profile |
| Admin dashboard | Verify or un-verify guides, see counts and recent bookings |

Not included yet: online payments, built-in video calls, email notifications for bookings. Guides paste a Google Meet or Zoom link for now.

## How it's built

- **Front end:** plain HTML, CSS and JavaScript, hosted on GitHub Pages. No build step.
- **Back end:** [Supabase](https://supabase.com) (Postgres database + authentication). The browser talks to Supabase directly using the public anon key.
- **Security:** every table has row-level security. Learners only see their own bookings, guides only see bookings made with them, contact details are private, only admins can verify guides, and prices and statuses are enforced in the database, not the browser. See `supabase/schema.sql`.

```
index.html        home page (live guide list)
login.html        sign in, sign up, password reset
guides.html       guide directory, guide profile and booking
dashboard.html    learner, guide and admin dashboards
css/              site.css (brand styles), app.css (app pages)
js/config.js      your Supabase URL and anon key
js/core.js        shared helpers
supabase/         schema.sql, reset.sql, tests/
```

## Setup (one time)

1. **Create a Supabase project** at supabase.com (free tier). Region: Mumbai.
2. **Create the database:** Supabase → SQL Editor → New query → paste all of `supabase/schema.sql` → Run.
3. **Connect the site:** Supabase → Project Settings → API. Copy the Project URL and the `anon` `public` key into `js/config.js`. Never use the `service_role` key in the site.
4. **Set the redirect URLs:** Supabase → Authentication → URL Configuration.
   - Site URL: `https://adityabankar266.github.io/nextrung/`
   - Redirect URLs: add `https://adityabankar266.github.io/nextrung/**`
5. **Make yourself admin:** sign up on the site, confirm your email, then run in the SQL Editor:
   ```sql
   update public.profiles set role = 'admin'
   where id = (select id from auth.users where email = 'you@example.com');
   ```
6. **Verify guides:** sign in → Dashboard → To verify → Verify guide. Only verified guides appear in the directory.

## Testing the database

The security rules have automated tests that run against a local Postgres:

```bash
python3 supabase/tests/run_tests.py   # needs psql and a local Postgres
```

They check sign-up, verification, privacy, booking rules, scorecards, reviews and double-booking.

## Before a public launch

- Turn on a custom SMTP sender in Supabase (the built-in email service is rate-limited and meant for testing).
- Add a privacy policy and terms (India's DPDP Act applies to learner data).
- Add payments (e.g. Razorpay) and booking email notifications.
