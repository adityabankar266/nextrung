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
    print("schema loaded")

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
    print("bookings")
    svc = psql(f"select id from public.services where guide_id='{guide}' order by title limit 1;").stdout.strip()
    when = "now() + interval '3 days'"
    ok, bid, err = as_user(learner, f"insert into public.bookings (learner_id, guide_id, service_id, scheduled_at, status, price_inr) "
                                    f"values ('{learner}','{guide}','{svc}', {when}, 'completed', 1) returning id;")
    expect("learner can request a booking", ok, err)
    bid = bid.splitlines()[0] if bid else ""
    r = psql(f"select status, price_inr from public.bookings where id='{bid}';").stdout.strip()
    expect("status and price come from the server, not the form", r == "requested|1200", r)
    ok, _, err = as_user(learner, f"insert into public.bookings (learner_id, guide_id, service_id, scheduled_at) "
                                  f"values ('{other}','{guide}','{svc}', {when});")
    expect("cannot book on behalf of someone else", not ok)
    ok, _, err = as_user(learner, f"insert into public.bookings (learner_id, guide_id, service_id, scheduled_at) "
                                  f"values ('{learner}','{guide}','{svc}', now() + interval '10 minutes');")
    expect("cannot book a slot in the next 2 hours", not ok)
    svc2 = psql(f"insert into public.services (guide_id,title,price_inr) values ('{guide2}','Test service',500) returning id;").stdout.strip().splitlines()[0]
    ok, _, err = as_user(learner, f"insert into public.bookings (learner_id, guide_id, service_id, scheduled_at) "
                                  f"values ('{learner}','{guide2}','{svc2}', {when});")
    expect("cannot book an unverified guide", not ok)

    ok, out, _ = as_user(other, f"select count(*) from public.bookings where id='{bid}';")
    expect("outsiders cannot see a booking", out == "0", out)
    ok, out, _ = as_user(guide, f"select career_stage from public.learner_profiles where user_id='{learner}';")
    expect("guide can see learner details after a booking", out == "Final-year student", out)
    ok, _, _ = as_user(learner, f"update public.bookings set status='accepted' where id='{bid}';")
    expect("learner cannot accept their own request", not ok)
    ok, _, _ = as_user(guide, f"update public.bookings set price_inr=1 where id='{bid}';")
    expect("guide cannot change the price", not ok)
    ok, _, err = as_user(guide, f"update public.bookings set status='accepted', meeting_link='https://meet.google.com/abc-defg-hij' where id='{bid}';")
    expect("guide can accept and add a meeting link", ok, err)
    ok, _, _ = as_user(guide, f"update public.bookings set meeting_link='javascript:alert(1)' where id='{bid}';")
    expect("meeting link must be https", not ok)

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

    # --- double booking ---------------------------------------------------------
    print("double booking")
    t = "date_trunc('hour', now()) + interval '5 days'"
    b1 = as_user(learner, f"insert into public.bookings (learner_id, guide_id, service_id, scheduled_at) values ('{learner}','{guide}','{svc}', {t}) returning id;")[1].splitlines()[0]
    l2 = signup("kavya@example.com", {"role": "learner", "full_name": "Kavya"})
    b2 = as_user(l2, f"insert into public.bookings (learner_id, guide_id, service_id, scheduled_at) values ('{l2}','{guide}','{svc}', {t}) returning id;")[1].splitlines()[0]
    as_user(guide, f"update public.bookings set status='accepted' where id='{b1}';")
    ok, _, err = as_user(guide, f"update public.bookings set status='accepted' where id='{b2}';")
    expect("guide cannot accept two sessions at the same time", not ok and "bookings_no_double_accept" in err, err)
    ok, _, err = as_user(l2, f"update public.bookings set status='cancelled' where id='{b2}';")
    expect("learner can cancel a request", ok, err)

    print(f"\n{PASS} passed, {FAIL} failed")
    psql(f"drop database {DB};", db="postgres")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
