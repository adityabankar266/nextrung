"""Capture product screenshots for the pitch deck using the Supabase stand-in (sample data).

Run: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 tests/capture_screens.py OUT_DIR
"""
import functools, http.server, os, socketserver, sys, threading
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK = open(os.path.join(ROOT, "tests", "mock-supabase.js")).read()
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/shots"
PORT = int(os.environ.get("PORT", "8850"))
os.makedirs(OUT, exist_ok=True)


def serve():
    socketserver.TCPServer.allow_reuse_address = True
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
    h.log_message = lambda *a: None
    s = socketserver.TCPServer(("127.0.0.1", PORT), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def page(b, role, w=1280, h=800, signed_out=False):
    ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, color_scheme="light")
    ctx.add_init_script(f"localStorage.setItem('mockRole','{role}');" + ("localStorage.setItem('mockSignedOut','1');" if signed_out else ""))
    ctx.route("**/supabase.js", lambda r: r.fulfill(status=200, content_type="text/javascript", body=MOCK))
    ctx.route("https://fonts.googleapis.com/**", lambda r: r.abort())
    ctx.route("https://fonts.gstatic.com/**", lambda r: r.abort())
    return ctx.new_page()


def shot(p, name, full=False):
    p.wait_for_timeout(500)
    p.screenshot(path=os.path.join(OUT, name + ".png"), full_page=full)
    print("saved", name)


srv = serve()
base = f"http://127.0.0.1:{PORT}"
with sync_playwright() as pw:
    b = pw.chromium.launch()

    p = page(b, "learner", signed_out=True)
    p.goto(base + "/index.html"); shot(p, "01-home")
    p.evaluate("document.getElementById('services').scrollIntoView()"); shot(p, "02-services")
    p.evaluate("document.getElementById('fields').scrollIntoView()"); shot(p, "03-fields")

    p = page(b, "learner", signed_out=True)
    p.goto(base + "/guides.html"); p.wait_for_selector(".guide"); shot(p, "04-directory")

    p = page(b, "learner", h=900)
    p.goto(base + "/guides.html?id=g1"); p.wait_for_selector("#bk-slots [data-day]")
    p.click("text=Career roadmap session"); p.click("#bk-slots [data-day] >> nth=1"); p.click("#bk-slots [data-slot] >> nth=0")
    p.evaluate("document.querySelector('#bk-slots').scrollIntoView({block:'center'})"); shot(p, "05-booking")

    p = page(b, "learner")
    p.goto(base + "/dashboard.html"); p.wait_for_selector("text=Upcoming"); shot(p, "06-learner-sessions")
    p.click("[data-tab=scorecards]"); shot(p, "07-learner-scorecards")
    p.click("[data-tab=plan]"); shot(p, "08-learner-plan")

    p = page(b, "guide")
    p.goto(base + "/dashboard.html"); p.wait_for_selector("text=Requests"); shot(p, "09-guide-requests")
    p.click("[data-tab=availability]"); shot(p, "10-guide-availability")
    p.click("[data-tab=plan]"); shot(p, "11-guide-payouts")

    p = page(b, "admin")
    p.goto(base + "/dashboard.html"); p.wait_for_selector("text=To verify"); shot(p, "12-admin")

    p = page(b, "learner", w=390, h=844, signed_out=True)
    p.goto(base + "/index.html"); shot(p, "13-mobile-home")
    p = page(b, "learner", w=390, h=844)
    p.goto(base + "/guides.html?id=g1"); p.wait_for_selector("#bk-slots [data-day]")
    p.click("#bk-slots [data-day] >> nth=0"); p.evaluate("document.querySelector('#bk-slots').scrollIntoView({block:'center'})"); shot(p, "14-mobile-booking")
    b.close()
srv.shutdown()
