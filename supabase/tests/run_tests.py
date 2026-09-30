"""Security and workflow tests for supabase/schema.sql against a local Postgres.

Usage: PGHOST=... PGPORT=... python3 supabase/tests/run_tests.py
Creates a throwaway database, loads the Supabase shim and the schema, then
acts as different users to check what each one can and cannot do.
"""
import os, subprocess, sys, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = "nextrung_test"
PASS = FAIL = 0


def psql(sql, db=DB, check=True):
    r = subprocess.run(["psql", "-U", "postgres", "-d", db, "-tA", "-v", "ON_ERROR_STOP=1", "-q"],
                       input=sql, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r


def as_user(uid, sql):
    """Run sql as a signed-in user (uid) or anonymous visitor (uid=None)."""
    role = "anon" if uid is None else "authenticated"
    sub = "" if uid is None else str(uid)
    wrapped = (f"begin;\nset local role {role};\n"
               f"select set_config('request.jwt.claim.sub', '{sub}', true) \\g /dev/null\n"
               f"{sql}\ncommit;\n")
    r = psql(wrapped, check=False)
    return r.returncode == 0, r.stdout.strip(), r.stderr.strip()


def expect(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}  {detail}")


def signup(email, meta):
    uid = uuid.uuid4()
    import json
    m = json.dumps(meta, ensure_ascii=False).replace("'", "''")
    psql(f"insert into auth.users (id, email, raw_user_meta_data) values ('{uid}', '{email}', '{m}'::jsonb);")
    return uid


def main():
    psql(f"drop database if exists {DB};", db="postgres")
    psql(f"create database {DB} encoding 'UTF8' template template0 lc_collate 'C' lc_ctype 'C';", db="postgres")
    psql(open(os.path.join(HERE, "supabase_shim.sql")).read())
    psql(open(os.path.join(ROOT, "schema.sql")).read())
    mig = os.path.join(ROOT, "migrations")
    for f in sorted(os.listdir(mig)):
        psql(open(os.path.join(mig, f)).read())
    print("schema and migrations loaded")

    # --- sign-up trigger -------------------------------------------------
    print("sign-up")
    learner = signup("sneha@example.com", {"role": "learner", "full_name": "Sneha Patil",
                     "career_stage": "Final-year student", "field": "Business Analysis", "goal": "Crack interviews"})
    guide = signup("rahul@example.com", {"role": "guide", "full_name": "Rahul Deshmukh", "headline": "Senior BA",
                   "field": "Business Analysis", "years_experience": "5–10 years", "availability": "Both",
                   "services": ["Mock panels", "Career roadmap"], "price_inr": "1200"})
    guide2 = signup("meera@example.com", {"role": "guide", "full_name": "Meera S", "field": "Not a field",
                    "services": ["Bogus"], "price_inr": "abc"})
    other = signup("amit@example.com", {"role": "admin", "full_name": "Amit"})
    admin = signup("owner@example.com", {"role": "learner", "full_name": "Owner"})
    psql(f"update public.profiles set role='admin' where id='{admin}';")

    r = psql(f"select role from public.profiles where id='{other}';").stdout.strip()
    expect("sign-up cannot create an admin", r == "learner", r)
    r = psql(f"select field, career_stage from public.learner_profiles where user_id='{learner}';").stdout.strip()
    expect("learner profile filled from sign-up", r == "Business Analysis|Final-year student", r)
    r = psql(f"select count(*), min(price_inr) from public.services where guide_id='{guide}';").stdout.strip()
    expect("guide services created with chosen price", r == "2|1200", r)
    r = psql(f"select coalesce(field,'null') from public.guide_profiles where user_id='{guide2}';").stdout.strip()
    expect("invalid field dropped instead of failing sign-up", r == "null", r)
    r = psql(f"select count(*) from public.services where guide_id='{guide2}';").stdout.strip()
    expect("unknown service ignored", r == "0", r)

    # --- verification ------------------------------------------------------
    print("verification")
    ok, out, _ = as_user(None, "select count(*) from public.guide_directory;")
    expect("unverified guide hidden from directory", out == "0", out)
    as_user(guide, f"update public.guide_profiles set is_verified=true where user_id='{guide}';")
    r = psql(f"select is_verified from public.guide_profiles where user_id='{guide}';").stdout.strip()
    expect("guide cannot verify themself", r == "f", r)
    as_user(learner, f"update public.profiles set role='admin' where id='{learner}';")
    r = psql(f"select role from public.profiles where id='{learner}';").stdout.strip()
    expect("user cannot make themself admin", r == "learner", r)
    ok, _, err = as_user(admin, f"update public.guide_profiles set is_verified=true where user_id='{guide}';")
    r = psql(f"select is_verified from public.guide_profiles where user_id='{guide}';").stdout.strip()
    expect("admin can verify a guide", ok and r == "t", err or r)
    ok, out, _ = as_user(None, "select full_name||'|'||from_price from public.guide_directory;")
    expect("verified guide shows in public directory", out == "Rahul Deshmukh|1200", out)

    # --- rejection -------------------------------------------------------------
    print("rejection")
    as_user(guide2, f"update public.guide_profiles set is_rejected=true where user_id='{guide2}';")
    as_user(guide, f"update public.guide_profiles set is_rejected=true where user_id='{guide}';")
    r = psql(f"select is_rejected from public.guide_profiles where user_id='{guide}';").stdout.strip()
    expect("guide cannot change their own rejection flag", r == "f", r)
    ok, _, err = as_user(admin, f"update public.guide_profiles set is_rejected=true where user_id='{guide2}';")
    r = psql(f"select is_rejected from public.guide_profiles where user_id='{guide2}';").stdout.strip()
    expect("admin can reject a guide", ok and r == "t", err or r)
    as_user(guide2, f"update public.guide_profiles set bio='please', is_rejected=false where user_id='{guide2}';")
    r = psql(f"select is_rejected||'|'||bio from public.guide_profiles where user_id='{guide2}';").stdout.strip()
    expect("rejected guide can edit profile but not clear rejection", r == "true|please", r)
    as_user(admin, f"update public.guide_profiles set is_verified=true where user_id='{guide2}';")
    r = psql(f"select is_verified||'|'||is_rejected from public.guide_profiles where user_id='{guide2}';").stdout.strip()
    expect("verifying a rejected guide clears the rejection", r == "true|false", r)
    as_user(admin, f"update public.guide_profiles set is_verified=false where user_id='{guide2}';")

    # --- privacy ---------------------------------------------------------------
    print("privacy")
    ok, out, _ = as_user(None, "select count(*) from public.contacts;")
    expect("visitors cannot read contacts", (not ok) or out == "0", out)
    ok, out, _ = as_user(learner, "select count(*) from public.contacts;")
    expect("user sees only own contact row", out == "1", out)
    ok, out, _ = as_user(guide, f"select count(*) from public.learner_profiles where user_id='{learner}';")
    expect("guide cannot see learner before a booking", out == "0", out)
    ok, out, _ = as_user(None, f"select count(*) from public.profiles where id='{learner}';")
    expect("visitors cannot see learner profiles", out == "0", out)

    # --- bookings -------------------------------------------------------------
    print("slots")
    ok, _, _ = as_user(guide, f"insert into public.availability_slots (guide_id, starts_at) values ('{guide}', now() - interval '1 hour');")
    expect("guide cannot add a slot in the past", not ok)
    ok, _, _ = as_user(learner, f"insert into public.availability_slots (guide_id, starts_at) values ('{guide}', now() + interval '3 days');")
    expect("learner cannot add slots for a guide", not ok)
    def slot(when):
        ok, out, err = as_user(guide, f"insert into public.availability_slots (guide_id, starts_at) values ('{guide}', {when}) returning id;")
        return out.splitlines()[0] if ok and out else ""
    s1 = slot("date_trunc('hour', now()) + interval '3 days'")
    s2 = slot("date_trunc('hour', now()) + interval '4 days'")
    s3 = slot("date_trunc('hour', now()) + interval '5 days'")
    s_soon = slot("now() + interval '30 minutes'")
    expect("guide can add future slots", all([s1, s2, s3, s_soon]))
    ok, out, _ = as_user(None, f"select count(*) from public.open_slots('{guide}');")
    expect("visitors see free slots at least 2 hours ahead", out == "3", out)
    ok, out, _ = as_user(None, "select count(*) from public.availability_slots;")
    expect("visitors cannot read the slots table directly", (not ok) or out == "0", out)

    print("bookings")
    svc = psql(f"select id from public.services where guide_id='{guide}' order by title limit 1;").stdout.strip()
    when = "now() + interval '3 days'"
    ok, _, err = as_user(learner, f"insert into public.bookings (learner_id, guide_id, service_id, scheduled_at) "
                                  f"values ('{learner}','{guide}','{svc}', {when});")
    expect("a booking must use a slot", not ok and "time slots" in err, err)
    ok, bid, err = as_user(learner, f"insert into public.bookings (learner_id, guide_id, service_id, slot_id, scheduled_at, status, price_inr) "
                                    f"values ('{learner}','{guide}','{svc}','{s1}', now() + interval '9 days', 'completed', 1) returning id;")
    expect("learner can request a slot", ok, err)
    bid = bid.splitlines()[0] if bid else ""
    r = psql(f"select status, price_inr, scheduled_at = (select starts_at from public.availability_slots where id='{s1}') from public.bookings where id='{bid}';").stdout.strip()
    expect("status, price and time come from the server, not the form", r == "requested|1200|t", r)
    ok, out, _ = as_user(None, f"select count(*) from public.open_slots('{guide}');")
    expect("a requested slot disappears from free slots", out == "2", out)
    l2 = signup("kavya@example.com", {"role": "learner", "full_name": "Kavya"})
    ok, _, err = as_user(l2, f"insert into public.bookings (learner_id, guide_id, service_id, slot_id, scheduled_at) values ('{l2}','{guide}','{svc}','{s1}', now());")
    expect("nobody else can take a requested slot", not ok, err)
    ok, _, err = as_user(learner, f"insert into public.bookings (learner_id, guide_id, service_id, slot_id, scheduled_at) values ('{other}','{guide}','{svc}','{s2}', now());")
    expect("cannot book on behalf of someone else", not ok)
    ok, _, err = as_user(learner, f"insert into public.bookings (learner_id, guide_id, service_id, slot_id, scheduled_at) values ('{learner}','{guide}','{svc}','{s_soon}', now());")
    expect("cannot book a slot in the next 2 hours", not ok)
    ok, _, _ = as_user(guide, f"delete from public.availability_slots where id='{s1}';")
    r = psql(f"select count(*) from public.availability_slots where id='{s1}';").stdout.strip()
    expect("guide cannot delete a booked slot", r == "1", r)
    svc2 = psql(f"insert into public.services (guide_id,title,price_inr) values ('{guide2}','Test service',500) returning id;").stdout.strip().splitlines()[0]
    g2slot = psql(f"insert into public.availability_slots (guide_id, starts_at) values ('{guide2}', now() + interval '3 days') returning id;").stdout.strip().splitlines()[0]
    ok, _, err = as_user(learner, f"insert into public.bookings (learner_id, guide_id, service_id, slot_id, scheduled_at) values ('{learner}','{guide2}','{svc2}','{g2slot}', now());")
    expect("cannot book an unverified guide", not ok)

    ok, out, _ = as_user(other, f"select count(*) from public.bookings where id='{bid}';")
    expect("outsiders cannot see a booking", out == "0", out)
    ok, out, _ = as_user(guide, f"select career_stage from public.learner_profiles where user_id='{learner}';")
    expect("guide can see learner details after a booking", out == "Final-year student", out)
    ok, _, _ = as_user(learner, f"update public.bookings set status='accepted' where id='{bid}';")
    expect("learner cannot accept their own request", not ok)
    ok, _, _ = as_user(guide, f"update public.bookings set price_inr=1 where id='{bid}';")
    expect("guide cannot change the price", not ok)
    ok, _, _ = as_user(guide, f"update public.bookings set scheduled_at=now() + interval '6 days' where id='{bid}';")
    expect("time can only change through reschedule", not ok)
    ok, _, err = as_user(guide, f"update public.bookings set status='accepted', meeting_link='https://meet.google.com/abc-defg-hij' where id='{bid}';")
    expect("guide can accept and add a meeting link", ok, err)
    ok, _, _ = as_user(guide, f"update public.bookings set meeting_link='javascript:alert(1)' where id='{bid}';")
    expect("meeting link must be https", not ok)

    print("reschedule")
    ok, _, _ = as_user(other, f"select public.reschedule_booking('{bid}', '{s2}');")
    expect("outsiders cannot reschedule", not ok)
    ok, _, err = as_user(learner, f"select public.reschedule_booking('{bid}', '{s_soon}');")
    expect("cannot reschedule into the next 2 hours", not ok)
    ok, _, err = as_user(learner, f"select public.reschedule_booking('{bid}', '{s2}');")
    r = psql(f"select status||'|'||last_rescheduled_by||'|'||reschedule_count||'|'||(slot_id='{s2}') from public.bookings where id='{bid}';").stdout.strip()
    expect("learner reschedule moves the slot and needs the guide's OK again", ok and r == "requested|learner|1|true", err or r)
    ok, out, _ = as_user(None, f"select string_agg(id::text, ',') from public.open_slots('{guide}');")
    expect("old slot is free again after reschedule", s1 in out and s2 not in out, out)
    as_user(guide, f"update public.bookings set status='accepted' where id='{bid}';")
    ok, _, err = as_user(guide, f"select public.reschedule_booking('{bid}', '{s3}');")
    r = psql(f"select status||'|'||last_rescheduled_by from public.bookings where id='{bid}';").stdout.strip()
    expect("guide reschedule keeps the session accepted", ok and r == "accepted|guide", err or r)
    b2 = as_user(l2, f"insert into public.bookings (learner_id, guide_id, service_id, slot_id, scheduled_at) values ('{l2}','{guide}','{svc}','{s2}', now()) returning id;")[1].splitlines()[0]
    ok, _, err = as_user(learner, f"select public.reschedule_booking('{bid}', '{s2}');")
    expect("cannot reschedule into a taken slot", not ok and "taken" in err, err)
    ok, _, err = as_user(l2, f"update public.bookings set status='cancelled' where id='{b2}';")
    expect("learner can cancel a request", ok, err)
    ok, _, err = as_user(admin, f"update public.bookings set status='accepted' where id='{b2}';")
    expect("admin can change a booking status", ok, err)

    # --- scorecards and reviews -------------------------------------------------
    print("scorecards and reviews")
    crit = '[{"name":"Problem framing","score":4},{"name":"Communication","score":3}]'
    ok, _, _ = as_user(learner, f"insert into public.scorecards (booking_id, criteria) values ('{bid}', '{crit}');")
    expect("learner cannot write a scorecard", not ok)
    ok, _, err = as_user(guide, f"insert into public.scorecards (booking_id, criteria, note) values ('{bid}', '{crit}', 'Good');")
    expect("guide can write a scorecard", ok, err)
    ok, out, _ = as_user(learner, f"select overall from public.scorecards where booking_id='{bid}';")
    expect("learner can read scorecard with overall score", out == "3.5", out)
    ok, _, _ = as_user(learner, f"insert into public.reviews (booking_id, guide_id, learner_id, rating) values ('{bid}','{guide}','{learner}',5);")
    expect("cannot review before the session is completed", not ok)
    ok, _, err = as_user(guide, f"update public.bookings set status='completed' where id='{bid}';")
    expect("guide can mark session completed", ok, err)
    ok, _, err = as_user(learner, f"insert into public.reviews (booking_id, guide_id, learner_id, rating, comment) values ('{bid}','{guide}','{learner}',5,'Great');")
    expect("learner can review a completed session", ok, err)
    ok, _, _ = as_user(learner, f"insert into public.reviews (booking_id, guide_id, learner_id, rating) values ('{bid}','{guide}','{learner}',1);")
    expect("only one review per session", not ok)
    ok, out, _ = as_user(None, "select rating||'|'||review_count from public.guide_directory;")
    expect("directory shows rating", out == "5.0|1", out)
    ok, _, _ = as_user(learner, f"update public.bookings set status='cancelled' where id='{bid}';")
    expect("completed session cannot be cancelled", not ok)

    print(f"\n{PASS} passed, {FAIL} failed")
    psql(f"drop database {DB};", db="postgres")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
