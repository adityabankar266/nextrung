"""Browser checks for the NextRung pages using a stand-in for Supabase (tests/mock-supabase.js).

Run: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 tests/ui_check.py
"""
import functools, http.server, os, socketserver, sys, threading
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK = open(os.path.join(ROOT, "tests", "mock-supabase.js")).read()
SHOTS = os.environ.get("SHOTS", "/tmp")
PORT = int(os.environ.get("PORT", "8765"))
results = []


def check(name, cond, detail=""):
    results.append(cond)
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else f"  {detail}"))


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
    handler.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def page_for(browser, role, errors):
    ctx = browser.new_context(viewport={"width": 390, "height": 900}, device_scale_factor=1)
    ctx.add_init_script(f"localStorage.setItem('mockRole', '{role}');")
    ctx.route("**/supabase.js", lambda r: r.fulfill(status=200, content_type="text/javascript", body=MOCK))
    ctx.route("https://fonts.googleapis.com/**", lambda r: r.abort())
    ctx.route("https://fonts.gstatic.com/**", lambda r: r.abort())
    p = ctx.new_page()
    p.on("pageerror", lambda e: errors.append(f"{role}: {e}"))
    p.on("console", lambda m: errors.append(f"{role} console: {m.text}") if m.type == "error" else None)
    return p


def writes(p):
    return p.evaluate("window.__writes")


def main():
    httpd = serve()
    base = f"http://127.0.0.1:{PORT}"
    errors = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()

        print("admin")
        p = page_for(b, "admin", errors)
        p.goto(base + "/dashboard.html"); p.wait_for_selector("text=To verify")
        p.screenshot(path=f"{SHOTS}/admin.png", full_page=True)
        check("pending guide shows Accept and Reject", p.locator("[data-panel=pending] >> text=Accept").count() == 1 and p.locator("[data-panel=pending] >> text=Reject").count() == 1)
        p.click("[data-panel=pending] [data-act=reject]")
        check("reject asks for confirmation", p.locator("#modal >> text=Reject this application?").is_visible())
        check("nothing saved before confirming", len(writes(p)) == 0)
        p.click("#cf-yes"); p.wait_for_timeout(300)
        w = writes(p)
        check("confirming rejects the guide", w and w[-1]["payload"] == {"is_verified": False, "is_rejected": True} and w[-1]["rows"] == ["g2"], w)
        p.click("[data-tab=bookings]"); p.wait_for_timeout(200)
        check("admin sees Accept and Reject on a new booking", p.locator("[data-panel=bookings] [data-act=bk-accept]").count() == 1 and p.locator("[data-panel=bookings] [data-act=bk-reject]").count() == 1)
        p.click("[data-panel=bookings] [data-act=bk-accept]"); p.wait_for_timeout(300)
        w = writes(p)
        check("admin can accept a booking, with a video link", w and w[-1]["payload"]["status"] == "accepted" and w[-1]["payload"]["meeting_link"].startswith("https://meet.jit.si/NextRung-") and w[-1]["rows"] == ["b1"], w)
        p.click("[data-tab=bookings]"); p.wait_for_timeout(200)
        p.click("[data-panel=bookings] [data-act=bk-reject]")
        check("admin booking reject asks for confirmation", p.locator("#modal >> text=Reject this booking?").is_visible())
        p.click("#cf-yes"); p.wait_for_timeout(300)
        check("confirming rejects the booking", writes(p)[-1]["payload"] == {"status": "declined"})
        p.click("[data-tab=rejected]"); p.wait_for_timeout(200)
        check("rejected tab lists rejected guide", p.locator("[data-panel=rejected] >> text=Karan Rao").is_visible())
        p.screenshot(path=f"{SHOTS}/admin-rejected.png", full_page=True)
        p.click("[data-switch=guide]"); p.wait_for_selector("text=Back to admin")
        check("admin can open own guide dashboard", p.locator("[data-tab=availability]").count() == 1)
        p.click("[data-switch=admin]"); p.wait_for_selector("text=To verify")
        check("and switch back to admin", p.locator("[data-switch=guide]").count() == 1)

        print("guide")
        p = page_for(b, "guide", errors)
        p.goto(base + "/dashboard.html"); p.wait_for_selector("text=Requests")
        p.screenshot(path=f"{SHOTS}/guide-requests.png", full_page=True)
        panel = p.locator("[data-panel=requests]")
        check("request shows chosen service", panel.locator("dd >> text=Mock panel with scorecard").is_visible())
        check("request shows date and time", panel.locator("dt >> text=Date & time").is_visible())
        check("request has Reject button", panel.locator("[data-act=decline] >> text=Reject").is_visible())
        p.click("[data-panel=requests] [data-act=decline]")
        check("reject request asks for confirmation", p.locator("#modal >> text=Reject this request?").is_visible())
        p.click("#modal [data-close] >> nth=1"); p.wait_for_timeout(200)
        check("Keep it cancels without saving", len(writes(p)) == 0 and not p.locator("#modal").is_visible())
        p.click("[data-panel=requests] [data-act=accept]"); p.wait_for_timeout(300)
        w = writes(p)
        check("guide accept without a link creates a video link", w and w[-1]["payload"]["status"] == "accepted" and w[-1]["payload"]["meeting_link"].startswith("https://meet.jit.si/"), w)
        p.goto(base + "/dashboard.html"); p.wait_for_selector("text=Requests")
        p.click("[data-panel=requests] [data-act=decline]"); p.click("#cf-yes"); p.wait_for_timeout(300)
        w = writes(p)
        check("confirming rejects the request", w and w[-1]["payload"] == {"status": "declined"} and w[-1]["rows"] == ["b1"], w)
        p.click("[data-tab=upcoming]"); p.wait_for_timeout(200)
        p.click("[data-panel=upcoming] [data-act=start]")
        check("Start session opens placeholder", p.locator("#modal >> text=coming soon").is_visible())
        p.screenshot(path=f"{SHOTS}/guide-start.png")
        p.click("#modal [data-close] >> nth=0"); p.wait_for_timeout(200)
        p.click("[data-panel=upcoming] [data-act=resched]"); p.wait_for_selector("#rs-slots [data-slot]")
        check("guide reschedule shows only free slots", p.locator("#rs-slots [data-day]").count() == 2, p.locator("#rs-slots [data-day]").count())
        p.click("#rs-save"); p.wait_for_timeout(200)
        check("reschedule needs a new time", p.locator(".toast >> text=Choose a new date and time.").is_visible())
        p.click("#rs-slots [data-day] >> nth=0"); p.click("#rs-slots [data-slot] >> nth=0"); p.click("#rs-save"); p.wait_for_timeout(300)
        w = writes(p)
        check("guide reschedule calls the server", w and w[-1]["op"] == "reschedule_booking" and w[-1]["payload"] == {"p_booking": "b2", "p_slot": "sl3"}, w)
        p.click("[data-tab=availability]"); p.wait_for_timeout(200)
        p.screenshot(path=f"{SHOTS}/guide-availability.png", full_page=True)
        check("availability shows booked and free slots", p.locator("[data-panel=availability] .chip.booked").count() == 2 and p.locator("[data-panel=availability] [data-act=del-slot]").count() == 3)
        tomorrow = p.evaluate("new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata'}).format(new Date(Date.now()+864e5))")
        p.fill("#sl-date", tomorrow)
        p.click("#sl-times [data-time='18:00']"); p.click("#sl-times [data-time='19:00']")
        p.select_option("#sl-repeat", "4")
        p.click("#slot-form button[type=submit]"); p.wait_for_timeout(300)
        w = writes(p)
        check("adding 2 times for 4 weeks creates 8 slots", w and w[-1]["op"] == "upsert" and len(w[-1]["payload"]) == 8, w[-1] if w else w)
        p.click("[data-tab=availability]"); p.wait_for_timeout(200)
        p.click("[data-panel=availability] [data-act=del-slot] >> nth=0"); p.wait_for_timeout(300)
        check("guide can remove a free slot", writes(p)[-1]["op"] == "delete")

        p.click("[data-tab=plan]"); p.wait_for_timeout(200)
        check("guide plan shows fee and payout form", p.locator("[data-panel=plan] h3 >> text=Payout details").is_visible() and p.locator("[data-panel=plan] h3 >> text=Earnings history").is_visible())
        p.fill("#upi-id", "not valid"); p.click("#upi-form button[type=submit]"); p.wait_for_timeout(200)
        check("UPI ID is validated", p.locator(".toast >> text=valid UPI ID").is_visible())
        p.fill("#upi-id", "rahul.d@okicici"); p.click("#upi-form button[type=submit]"); p.wait_for_timeout(300)
        check("valid UPI ID is saved", writes(p)[-1]["payload"] == {"payout_upi": "rahul.d@okicici"}, writes(p)[-1])
        p.screenshot(path=f"{SHOTS}/guide-plan.png", full_page=True)
        p.click("[data-tab=profile]"); p.wait_for_timeout(200)
        png = os.path.join(SHOTS, "face.png")
        p.evaluate("() => new Promise(r => { const c = document.createElement('canvas'); c.width = 600; c.height = 400; const x = c.getContext('2d'); x.fillStyle = '#2563EB'; x.fillRect(0,0,600,400); r(c.toDataURL('image/png')); })")
        import base64
        data = p.evaluate("() => { const c = document.createElement('canvas'); c.width = 600; c.height = 400; const x = c.getContext('2d'); x.fillStyle = '#2563EB'; x.fillRect(0,0,600,400); return c.toDataURL('image/png').split(',')[1]; }")
        open(png, "wb").write(base64.b64decode(data))
        p.set_input_files("#ph-file", png); p.wait_for_timeout(800)
        w = writes(p)
        up = [x for x in w if x["table"] == "storage" and x["op"] == "upload"]
        check("photo upload goes to the user's own folder as a JPEG", up and up[-1]["payload"]["path"] == "g1/avatar.jpg" and up[-1]["payload"]["type"] == "image/jpeg", up)
        check("profile is updated with the photo link", any(x["table"] == "profiles" and "avatar_url" in (x["payload"] or {}) for x in w))
        p.fill("#pw-new", "longpassword1"); p.fill("#pw-confirm", "different"); p.click("#pw-form button[type=submit]"); p.wait_for_timeout(200)
        check("password change needs matching passwords", p.locator(".toast >> text=don't match").is_visible())
        p.fill("#pw-confirm", "longpassword1"); p.click("#pw-form button[type=submit]"); p.wait_for_timeout(300)
        check("password change is sent", writes(p)[-1]["op"] == "updateUser")
        p.screenshot(path=f"{SHOTS}/guide-profile.png", full_page=True)

        print("learner")
        p = page_for(b, "learner", errors)
        p.goto(base + "/dashboard.html"); p.wait_for_selector("text=Sessions")
        check("learner sees Start session on accepted booking", p.locator("[data-act=start]").count() == 1)
        check("learner can reschedule upcoming sessions", p.locator("[data-act=resched]").count() == 2)
        p.click("[data-tab=plan]"); p.wait_for_timeout(200)
        check("learner plan shows payment history and options", p.locator("[data-panel=plan] h3 >> text=Payment history").is_visible() and p.locator("[data-panel=plan] h3 >> text=Payment options").is_visible())
        check("payment history lists each session", p.locator("[data-panel=plan] .pay-row").count() == 3, p.locator("[data-panel=plan] .pay-row").count())
        p.screenshot(path=f"{SHOTS}/learner-plan.png", full_page=True)
        p.click("[data-tab=sessions]"); p.wait_for_timeout(200)
        p.click("[data-act=resched] >> nth=0"); p.wait_for_selector("#rs-slots [data-slot]")
        p.click("#rs-slots [data-slot] >> nth=0"); p.click("#rs-save"); p.wait_for_timeout(300)
        w = writes(p)
        check("learner reschedule calls the server", w and w[-1]["op"] == "reschedule_booking", w)
        p.goto(base + "/guides.html?id=g1"); p.wait_for_selector("#book-form")
        radios = p.locator("input[name=bk-svc]")
        check("booking shows only free dates", p.locator("#bk-slots [data-day]").count() == 2, p.locator("#bk-slots [data-day]").count())
        check("services shown as radio buttons", radios.count() == 2)
        p.screenshot(path=f"{SHOTS}/book.png", full_page=True)
        p.click("#book-form button[type=submit]"); p.wait_for_timeout(200)
        check("must choose a service", p.locator(".toast >> text=Choose a service first.").is_visible())
        p.click("text=Career roadmap session")
        p.click("#book-form button[type=submit]"); p.wait_for_timeout(200)
        check("must choose a time slot", p.locator(".toast >> text=Choose a date and time slot.").is_visible())
        p.click("#bk-slots [data-day] >> nth=1"); p.click("#bk-slots [data-slot] >> nth=1")
        p.screenshot(path=f"{SHOTS}/book-slots.png", full_page=True)
        p.click("#book-form button[type=submit]"); p.wait_for_timeout(300)
        w = writes(p)
        check("booking uses the chosen service and slot", w and w[-1]["op"] == "insert" and w[-1]["payload"]["service_id"] == "s2" and w[-1]["payload"]["slot_id"] == "sl5", w)

        print("sign-up")
        p = page_for(b, "learner", errors)
        p.add_init_script("localStorage.setItem('mockSignedOut','1')")
        p.goto(base + "/login.html?mode=signup&role=guide"); p.wait_for_selector("#form-signup")
        p.fill("#su-name", "Test Guide"); p.fill("#su-email", "t@example.com"); p.fill("#su-pass", "longpassword")
        p.click("#form-signup button[type=submit]")
        check("guide sign-up blocks missing field", "Choose your field" in p.inner_text("#msg-signup"), p.inner_text("#msg-signup"))
        p.select_option("#su-field", "Business Analysis"); p.fill("#su-headline", "Senior BA"); p.select_option("#su-exp", "5–10 years")
        p.fill("#su-li", "linkedin.com/in/test"); p.select_option("#su-avail", "Both")
        p.click("#form-signup button[type=submit]")
        check("guide sign-up requires a price", "price" in p.inner_text("#msg-signup"), p.inner_text("#msg-signup"))
        p.fill("#su-price", "1200"); p.click("#form-signup button[type=submit]"); p.wait_for_timeout(300)
        w = writes(p)
        meta = w[-1]["payload"]["options"]["data"] if w else {}
        check("complete guide sign-up is sent", meta.get("linkedin_url") == "https://linkedin.com/in/test" and meta.get("price_inr") == "1200", meta)
        p.goto(base + "/login.html?mode=signup"); p.wait_for_selector("#form-signup")
        p.fill("#su-name", "Test Learner"); p.fill("#su-email", "l@example.com"); p.fill("#su-pass", "longpassword")
        p.select_option("#su-field", "Marketing"); p.select_option("#su-stage", "Recent graduate")
        p.click("#form-signup button[type=submit]")
        check("learner sign-up requires a goal", "goal" in p.inner_text("#msg-signup"), p.inner_text("#msg-signup"))
        p.screenshot(path=f"{SHOTS}/signup.png", full_page=True)

        overflow = []
        for path in ["/index.html", "/guides.html", "/dashboard.html", "/login.html"]:
            q = page_for(b, "guide", errors); q.goto(base + path); q.wait_for_timeout(500)
            if q.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"): overflow.append(path)
        check("no sideways scrolling on phones", not overflow, overflow)
        b.close()

    real_errors = [e for e in errors if "fonts" not in e and "ERR_FAILED" not in e and "Failed to load resource" not in e]
    check("no script errors", not real_errors, real_errors)
    httpd.shutdown()
    print(f"\n{sum(results)} passed, {len(results) - sum(results)} failed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
