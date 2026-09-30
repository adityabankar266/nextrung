// Test double for supabase-js: serves fixture rows and records writes (window.__writes).
(function () {
  const now = Date.now(), H = 3600e3;
  const iso = ms => new Date(ms).toISOString();
  // 12:00 IST (+ extra hours) on the day that is `days` from today, so slots never straddle midnight
  const noon = (days, plus = 0) => {
    const ymd = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date(now + days * 24 * H));
    return iso(new Date(ymd + 'T12:00:00+05:30').getTime() + plus * H);
  };
  const ROLE = localStorage.getItem('mockRole') || 'guide';
  const IDS = { guide: 'g1', learner: 'l1', admin: 'a1' };
  const me = IDS[ROLE];
  const DB = {
    profiles: [
      { id: 'g1', role: 'guide', full_name: 'Rahul Deshmukh', created_at: iso(now - 50 * H), avatar_url: null },
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
      { user_id: 'a1', headline: 'Senior BA', field: 'Business Analysis', years_experience: '5–10 years', bio: '', linkedin_url: 'https://linkedin.com/in/a', availability: 'Both', is_verified: true, is_rejected: false, created_at: iso(now - 90 * H) },
      { user_id: 'g3', headline: 'Dev', field: 'Software Development', years_experience: '3–5 years', bio: '', linkedin_url: null, availability: 'Both', is_verified: false, is_rejected: true, created_at: iso(now - 10 * H) }
    ],
    learner_profiles: [{ user_id: 'l1', career_stage: 'Final-year student', field: 'Business Analysis', goal: 'Crack interviews' }],
    services: [
      { id: 's1', guide_id: 'g1', title: 'Mock panel with scorecard', description: 'BA case round', duration_min: 60, price_inr: 999, is_active: true, created_at: iso(now) },
      { id: 's2', guide_id: 'g1', title: 'Career roadmap session', description: '', duration_min: 45, price_inr: 1499, is_active: true, created_at: iso(now) }
    ],
    bookings: [
      { id: 'b1', learner_id: 'l1', guide_id: 'g1', service_id: 's1', service_title: 'Mock panel with scorecard', price_inr: 999, duration_min: 60, slot_id: 'sl1', scheduled_at: noon(2), status: 'requested', last_rescheduled_by: 'learner', learner_note: 'BA interview next week.', guide_note: '', meeting_link: null, created_at: iso(now - 2 * H) },
      { id: 'b2', learner_id: 'l1', guide_id: 'g1', service_id: 's2', service_title: 'Career roadmap session', price_inr: 1499, duration_min: 45, slot_id: 'sl2', scheduled_at: localStorage.getItem('mockSoon') ? iso(now + 10 * 60e3) : noon(3), status: 'accepted', learner_note: '', guide_note: '', meeting_link: 'https://meet.google.com/abc-defg-hij', created_at: iso(now - 5 * H) },
      { id: 'b3', learner_id: 'l1', guide_id: 'g1', service_id: 's1', service_title: 'Mock panel with scorecard', price_inr: 999, duration_min: 60, scheduled_at: iso(now - 72 * H), status: 'completed', learner_note: '', guide_note: '', meeting_link: null, created_at: iso(now - 100 * H) }
    ],
    scorecards: [{ booking_id: 'b3', criteria: [{ name: 'Problem framing', score: 4 }, { name: 'Communication', score: 3 }], overall: 3.5, note: 'Good structure.', fixes: '1. Slow down' }],
    reviews: [],
    availability_slots: [
      { id: 'sl1', guide_id: 'g1', starts_at: noon(2) },
      { id: 'sl2', guide_id: 'g1', starts_at: noon(3) },
      { id: 'sl3', guide_id: 'g1', starts_at: noon(4) },
      { id: 'sl4', guide_id: 'g1', starts_at: noon(5) },
      { id: 'sl5', guide_id: 'g1', starts_at: noon(5, 1) }
    ],
    guide_directory: [
      { guide_id: 'g4', full_name: 'Neha Kulkarni', headline: 'Analytics Manager', field: 'Data Analytics', years_experience: '5–10 years', bio: 'Eight years in retail and FMCG analytics. I run SQL rounds and case interviews for analyst roles.', linkedin_url: null, availability: 'Weekday evenings', from_price: 999, rating: 4.9, review_count: 23 },
      { guide_id: 'g5', full_name: 'Arjun Mehra', headline: 'Engineering Lead', field: 'Software Development', years_experience: '10–15 years', bio: 'Backend and system design interviews for product companies. Ex-hiring manager.', linkedin_url: null, availability: 'Weekends', from_price: 1499, rating: 4.8, review_count: 31 },
      { guide_id: 'g6', full_name: 'Priya Iyer', headline: 'QA Manager', field: 'Quality Assurance', years_experience: '10–15 years', bio: 'Automation, test strategy and QA-to-BA career switches.', linkedin_url: null, availability: 'Both', from_price: 899, rating: 4.7, review_count: 18 },
      { guide_id: 'g7', full_name: 'Sameer Joshi', headline: 'Brand Manager', field: 'Marketing', years_experience: '5–10 years', bio: 'FMCG brand launches in Tier-2 cities; go-to-market case rounds.', linkedin_url: null, availability: 'Weekday evenings', from_price: 899, rating: 4.6, review_count: 12 },
      { guide_id: 'g8', full_name: 'Vandana Gupta', headline: 'Delivery Head', field: 'Leadership', years_experience: '15+ years', bio: 'Built and led teams of 60+. Promotion prep and first-time manager coaching.', linkedin_url: null, availability: 'Both', from_price: 1999, rating: 4.9, review_count: 27 },
      { guide_id: 'g1', full_name: 'Rahul Deshmukh', headline: 'Senior Business Analyst', field: 'Business Analysis', years_experience: '5–10 years', bio: 'Nine years in ERP and supply chain.', linkedin_url: 'https://linkedin.com/in/rahul', availability: 'Both', from_price: 999, rating: 4.8, review_count: 37 }]
  };
  window.__writes = [];

  function query(table) {
    let rows = (DB[table] || []).slice(), op = 'select', payload = null, single = false, head = false, countOpt = null;
    const q = {
      select(cols, opts) { if (opts && opts.head) head = true; if (opts && opts.count) countOpt = true; return q; },
      eq(c, v) { rows = rows.filter(r => r[c] === v); return q; },
      in(c, vs) { rows = rows.filter(r => vs.includes(r[c])); return q; },
      gte(c, v) { rows = rows.filter(r => r[c] >= v); return q; },
      order() { return q; }, limit(n) { rows = rows.slice(0, n); return q; },
      single() { single = true; return q; }, maybeSingle() { single = true; return q; },
      update(p) { op = 'update'; payload = p; return q; },
      insert(p) { op = 'insert'; payload = p; return q; },
      upsert(p, o) { op = 'upsert'; payload = p; window.__lastUpsertOptions = o; return q; },
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
        storage: { from(bucket) { return {
          upload: async (path, blob, opts) => { window.__writes.push({ table: 'storage', op: 'upload', payload: { bucket, path, type: blob && blob.type, upsert: opts && opts.upsert }, rows: [] }); return { data: { path }, error: null }; },
          getPublicUrl: path => ({ data: { publicUrl: `https://example.supabase.co/storage/v1/object/public/${bucket}/${path}` } }),
          remove: async paths => { window.__writes.push({ table: 'storage', op: 'remove', payload: paths, rows: [] }); return { error: null }; }
        }; } },
        rpc(fn, args) {
          if (fn === 'open_slots') {
            const taken = DB.bookings.filter(b => ['requested', 'accepted', 'completed'].includes(b.status)).map(b => b.slot_id);
            return Promise.resolve({ data: DB.availability_slots.filter(x => x.guide_id === args.p_guide && !taken.includes(x.id)), error: null });
          }
          if (fn === 'my_payment_details') {
            return Promise.resolve({ data: DB.bookings.filter(b => b.learner_id === user.id && ['accepted', 'completed'].includes(b.status)).map(b => ({ booking_id: b.id, upi: 'rahul.d@okicici' })), error: null });
          }
          window.__writes.push({ table: 'rpc', op: fn, payload: args, rows: [] });
          return Promise.resolve({ data: null, error: null });
        },
        auth: {
          getSession: async () => ({ data: { session: localStorage.getItem('mockSignedOut') ? null : { user } } }),
          onAuthStateChange() { return { data: { subscription: { unsubscribe() {} } } }; },
          signUp: async (x) => { window.__writes.push({ table: 'auth', op: 'signUp', payload: x }); return { data: { user: { identities: [{}] }, session: null }, error: null }; },
          signInWithPassword: async () => ({ error: null }), signOut: async () => ({}),
          updateUserRecorded: true,
          resetPasswordForEmail: async () => ({ error: null }),
          updateUser: async (x) => { window.__writes.push({ table: 'auth', op: 'updateUser', payload: x, rows: [] }); return { error: null }; }
        }
      };
    }
  };
})();
