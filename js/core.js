// Shared helpers for every NextRung page: Supabase client, formatting, header state.
(function () {
  const cfg = window.NEXTRUNG_CONFIG || {};
  const hasValues = cfg.SUPABASE_URL && cfg.SUPABASE_ANON_KEY &&
    !cfg.SUPABASE_URL.startsWith('YOUR_') && !cfg.SUPABASE_ANON_KEY.startsWith('YOUR_');
  const sb = hasValues && window.supabase
    ? window.supabase.createClient(cfg.SUPABASE_URL, cfg.SUPABASE_ANON_KEY, {
        auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: 'implicit' }
      })
    : null;

  const NR = {
    sb,
    ready: !!sb,
    FIELDS: ['Software Development', 'Business Analysis', 'Quality Assurance', 'Data Analytics', 'Marketing', 'Leadership'],
    STAGES: ['Final-year student', 'Recent graduate', '1–3 years experience', '3–8 years experience', '8+ years experience'],
    EXPERIENCE: ['3–5 years', '5–10 years', '10–15 years', '15+ years'],
    AVAILABILITY: ['Weekday evenings', 'Weekends', 'Both'],
    PLATFORM_FEE: 0.15,

    esc(s) {
      return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    },
    inr(n) { return '₹' + Number(n || 0).toLocaleString('en-IN'); },
    when(ts) {
      return new Intl.DateTimeFormat('en-IN', {
        weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
        hour: 'numeric', minute: '2-digit', timeZone: 'Asia/Kolkata'
      }).format(new Date(ts)) + ' IST';
    },
    initials(name) {
      const p = String(name || '?').trim().split(/\s+/);
      return ((p[0] || '?')[0] + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase();
    },
    one(x) { return Array.isArray(x) ? x[0] : x; },
    options(list, selected) {
      return list.map(v => `<option${v === selected ? ' selected' : ''}>${NR.esc(v)}</option>`).join('');
    },
    safeUrl(u) {
      return /^https:\/\//i.test(u || '') ? u : '';
    },

    toast(msg, bad) {
      document.querySelectorAll('.toast').forEach(t => t.remove());
      const t = document.createElement('div');
      t.className = 'toast' + (bad ? ' bad' : '');
      t.setAttribute('role', 'status');
      t.textContent = msg;
      document.body.appendChild(t);
      setTimeout(() => t.remove(), bad ? 6000 : 3500);
    },

    // Turn database and auth errors into sentences people can act on.
    explain(err) {
      const m = (err && (err.message || err.error_description || String(err))) || 'Something went wrong.';
      if (/bookings_no_double_accept/.test(m)) return 'You already have a session accepted at that time. Decline this one or cancel the other first.';
      if (/Invalid login credentials/i.test(m)) return 'Email or password is incorrect.';
      if (/Email not confirmed/i.test(m)) return 'Please confirm your email first. Check your inbox for the link from NextRung.';
      if (/already registered|already been registered/i.test(m)) return 'An account with this email already exists. Sign in instead.';
      if (/Password should be at least/i.test(m)) return 'Use a password with at least 8 characters.';
      if (/rate limit|too many/i.test(m)) return 'Too many attempts. Wait a minute and try again.';
      if (/meeting_link/.test(m)) return 'The meeting link must start with https://';
      if (/Failed to fetch|NetworkError/i.test(m)) return 'Could not reach the server. Check your connection and try again.';
      return m.replace(/^ERROR:\s*/, '');
    },

    async user() {
      if (!sb) return null;
      const { data } = await sb.auth.getSession();
      return data.session ? data.session.user : null;
    },

    async profile(uid) {
      const { data, error } = await sb.from('profiles').select('id, role, full_name').eq('id', uid).single();
      if (error) throw error;
      return data;
    },

    // Send people to the login page and bring them back afterwards.
    loginUrl(extra) {
      const next = encodeURIComponent(location.pathname.split('/').pop() + location.search);
      return `login.html?next=${next}${extra ? '&' + extra : ''}`;
    },

    notReadyHtml() {
      return `<div class="notice">The database isn't connected yet. Add your Supabase URL and anon key to <code>js/config.js</code> (see the README).</div>`;
    },

    // Header buttons change when someone is signed in.
    async header() {
      const slot = document.querySelector('[data-auth-slot]');
      if (!slot) return;
      const u = await NR.user();
      if (u) {
        slot.innerHTML = `<a class="btn ghost sm" href="dashboard.html">Dashboard</a>
          <button class="btn sm" type="button" data-signout>Sign out</button>`;
        slot.querySelector('[data-signout]').addEventListener('click', async () => {
          await sb.auth.signOut();
          location.href = 'index.html';
        });
      } else {
        slot.innerHTML = `<a class="btn ghost sm" href="login.html">Sign in</a>
          <a class="btn sm" href="login.html?mode=signup">Join</a>`;
      }
    }
  };

  window.NR = NR;
  document.addEventListener('DOMContentLoaded', () => { NR.header().catch(() => {}); });
})();
