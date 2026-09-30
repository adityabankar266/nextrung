// Test double for supabase-js: serves fixture rows and records writes (window.__writes).
(function () {
  const now = Date.now(), H = 3600e3;
  const iso = ms => new Date(ms).toISOString();
  const ROLE = localStorage.getItem('mockRole') || 'guide';
  const IDS = { guide: 'g1', learner: 'l1', admin: 'a1' };
  const me = IDS[ROLE];
  const DB = {
    profiles: [
      { id: 'g1', role: 'guide', full_name: 'Rahul Deshmukh', created_at: iso(now - 50 * H) },
      { id: 'g2', role: 'guide', full_name: 'Meera Shah', created_at: iso(now - 20 * H) },
      { id: 'g3', role: 'guide', full_name: 'Karan Rao', created_at: iso(now - 10 * H) },
      { id: 'l1', role: 'learner', full_name: 'Akash Mehta', created_at: iso(now - 30 * H) },
      { id: 'a1', role: 'admin', full_name: 'Aditya Bankar', created_at: iso(now - 90 * H) }
    ],
    contacts: [{ user_id: 'g1', email: 'rahul@example.com', phone: '9800000000' }, { user_id: 'g2', email: 'meera@example.com' },
               { user_id: 'g3', email: 'karan@example.com' }, { user_id: 'l1', email: 'akash@example.com' }, { user_id: 'a1', email: 'a@example.com' }],
    guide_profiles: [
      { user_id: 'g1', headline: 'Senior Business Analyst', field: 'Business Analysis', years_experience: '5–10 years', bio: 'Nine years in ERP and supply chain.', linkedin_url: 'https://linkedin.com/in/rahul', availability: 'Both', is_verified: true, is_rejected: false, created_at: iso(now - 50 * H) },
      { user_id: 'g2', headline: 'QA Lead', field: 'Quality Assurance', years_experience: '10–15 years', bio: 'Automation.', linkedin_url: 'https://linkedin.com/in/meera', availability: 'Weekends', is_verified: false, is_rejected: false, created_at: iso(now - 20 * H) },
      { user_id: 'g3', headline: 'Dev', field: 'Software Development', years_experience: '3–5 years', bio: '', linkedin_url: null, availability: 'Both', is_verified: false, is_rejected: true, created_at: iso(now - 10 * H) }
    ],
    learner_profiles: [{ user_id: 'l1', career_stage: 'Final-year student', field: 'Business Analysis', goal: 'Crack interviews' }],
    services: [
      { id: 's1', guide_id: 'g1', title: 'Mock panel with scorecard', description: 'BA case round', duration_min: 60, price_inr: 999, is_active: true, created_at: iso(now) },
      { id: 's2', guide_id: 'g1', title: 'Career roadmap session', description: '', duration_min: 45, price_inr: 1499, is_active: true, created_at: iso(now) }
    ],
    bookings: [
      { id: 'b1', learner_id: 'l1', guide_id: 'g1', service_id: 's1', service_title: 'Mock panel with scorecard', price_inr: 999, duration_min: 60, scheduled_at: iso(now + 48 * H), status: 'requested', learner_note: 'BA interview next week.', guide_note: '', meeting_link: null, created_at: iso(now - 2 * H) },
      { id: 'b2', learner_id: 'l1', guide_id: 'g1', service_id: 's2', service_title: 'Career roadmap session', price_inr: 1499, duration_min: 45, scheduled_at: iso(now + 72 * H), status: 'accepted', learner_note: '', guide_note: '', meeting_link: 'https://meet.google.com/abc-defg-hij', created_at: iso(now - 5 * H) },
      { id: 'b3', learner_id: 'l1', guide_id: 'g1', service_id: 's1', service_title: 'Mock panel with scorecard', price_inr: 999, duration_min: 60, scheduled_at: iso(now - 72 * H), status: 'completed', learner_note: '', guide_note: '', meeting_link: null, created_at: iso(now - 100 * H) }
    ],
    scorecards: [{ booking_id: 'b3', criteria: [{ name: 'Problem framing', score: 4 }, { name: 'Communication', score: 3 }], overall: 3.5, note: 'Good structure.', fixes: '1. Slow down' }],
    reviews: [],
    guide_directory: [{ guide_id: 'g1', full_name: 'Rahul Deshmukh', headline: 'Senior Business Analyst', field: 'Business Analysis', years_experience: '5–10 years', bio: 'Nine years in ERP and supply chain.', linkedin_url: 'https://linkedin.com/in/rahul', availability: 'Both', from_price: 999, rating: null, review_count: 0 }]
  };
  window.__writes = [];

  function query(table) {
    let rows = (DB[table] || []).slice(), op = 'select', payload = null, single = false, head = false, countOpt = null;
    const q = {
      select(cols, opts) { if (opts && opts.head) head = true; if (opts && opts.count) countOpt = true; return q; },
      eq(c, v) { rows = rows.filter(r => r[c] === v); return q; },
      in(c, vs) { rows = rows.filter(r => vs.includes(r[c])); return q; },
      order() { return q; }, limit(n) { rows = rows.slice(0, n); return q; },
      single() { single = true; return q; }, maybeSingle() { single = true; return q; },
      update(p) { op = 'update'; payload = p; return q; },
      insert(p) { op = 'insert'; payload = p; return q; },
      upsert(p) { op = 'upsert'; payload = p; return q; },
      delete() { op = 'delete'; return q; },
      then(res, rej) {
        let out;
        if (op !== 'select') {
          const filterIds = rows.map(r => r.id || r.user_id || r.booking_id);
          window.__writes.push({ table, op, payload, rows: op === 'insert' ? [] : filterIds });
          out = { data: null, error: null };
        } else if (head) out = { data: null, count: rows.length, error: null };
        else out = { data: single ? (rows[0] || null) : rows, error: null };
        return Promise.resolve(out).then(res, rej);
      }
    };
    return q;
  }
  const user = { id: me, email: me + '@example.com' };
  window.supabase = {
    createClient() {
      return {
        from: query,
        auth: {
          getSession: async () => ({ data: { session: localStorage.getItem('mockSignedOut') ? null : { user } } }),
          onAuthStateChange() { return { data: { subscription: { unsubscribe() {} } } }; },
          signUp: async (x) => { window.__writes.push({ table: 'auth', op: 'signUp', payload: x }); return { data: { user: { identities: [{}] }, session: null }, error: null }; },
          signInWithPassword: async () => ({ error: null }), signOut: async () => ({}),
          resetPasswordForEmail: async () => ({ error: null }), updateUser: async () => ({ error: null })
        }
      };
    }
  };
})();
