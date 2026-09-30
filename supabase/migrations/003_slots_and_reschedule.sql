-- Update 3 (30 Sep 2026): bookable time slots managed by guides, and rescheduling.
-- Run once in Supabase: SQL Editor -> New query -> paste -> Run. Safe to run again.
--
-- What changes
--   * Guides publish date-wise time slots (availability_slots).
--   * Learners book one of those slots; a slot can only be taken by one active booking.
--   * Slots must be in the future; bookings must be at least 2 hours ahead.
--   * Either side can reschedule an upcoming session to another free slot of the same guide.
--     When the learner reschedules, the guide has to accept again.

-- ---------- Slots ------------------------------------------------------------

create table if not exists public.availability_slots (
  id          uuid primary key default gen_random_uuid(),
  guide_id    uuid not null references public.guide_profiles(user_id) on delete cascade,
  starts_at   timestamptz not null,
  created_at  timestamptz not null default now(),
  unique (guide_id, starts_at)
);
create index if not exists availability_slots_guide_time on public.availability_slots (guide_id, starts_at);
alter table public.availability_slots enable row level security;

-- ---------- Booking columns ----------------------------------------------------

alter table public.bookings
  add column if not exists slot_id uuid references public.availability_slots(id) on delete set null,
  add column if not exists reschedule_count int not null default 0,
  add column if not exists last_rescheduled_by text check (last_rescheduled_by in ('learner','guide','admin'));

-- one active booking per slot (also stops two people grabbing the same slot at once)
create unique index if not exists bookings_one_per_slot
  on public.bookings (slot_id) where status in ('requested','accepted','completed');

-- ---------- Rules ----------------------------------------------------------------

-- is this slot free for booking (ignoring one booking, used when rescheduling)?
create or replace function public.slot_is_free(p_slot uuid, p_except uuid default null)
returns boolean language sql stable security definer set search_path = public as $$
  select not exists (select 1 from public.bookings b
                     where b.slot_id = p_slot and b.status in ('requested','accepted','completed')
                       and (p_except is null or b.id <> p_except))
$$;

create or replace function public.prepare_booking()
returns trigger language plpgsql security definer set search_path = public as $$
declare s record; sl record;
begin
  if new.learner_id is distinct from auth.uid() and not public.is_trusted() then
    raise exception 'You can only book sessions for yourself.';
  end if;
  if new.learner_id = new.guide_id then
    raise exception 'You cannot book a session with yourself.';
  end if;
  select sv.* into s from public.services sv
    join public.guide_profiles g on g.user_id = sv.guide_id
   where sv.id = new.service_id and sv.guide_id = new.guide_id
     and sv.is_active and g.is_verified;
  if not found then
    raise exception 'This service is not available for booking.';
  end if;
  if new.slot_id is null then
    raise exception 'Choose one of the available time slots.';
  end if;
  select * into sl from public.availability_slots where id = new.slot_id and guide_id = new.guide_id;
  if not found then
    raise exception 'That time slot is no longer available. Please choose another.';
  end if;
  if sl.starts_at < now() + interval '2 hours' then
    raise exception 'Choose a slot at least 2 hours from now.';
  end if;
  if not public.slot_is_free(new.slot_id) then
    raise exception 'That time slot has just been taken. Please choose another.';
  end if;
  new.scheduled_at  := sl.starts_at;
  new.service_title := s.title;
  new.price_inr     := s.price_inr;
  new.duration_min  := s.duration_min;
  new.status        := 'requested';
  new.meeting_link  := null;
  new.guide_note    := '';
  new.reschedule_count := 0;
  new.last_rescheduled_by := null;
  return new;
end $$;

create or replace function public.guard_booking()
returns trigger language plpgsql as $$
declare me uuid := auth.uid();
begin
  if public.is_trusted() then return new; end if;
  -- set only inside reschedule_booking(), which does its own checks
  if current_setting('nextrung.reschedule', true) = 'on' then return new; end if;

  if new.learner_id is distinct from old.learner_id or new.guide_id is distinct from old.guide_id
     or new.service_id is distinct from old.service_id or new.service_title is distinct from old.service_title
     or new.price_inr is distinct from old.price_inr or new.duration_min is distinct from old.duration_min
     or new.scheduled_at is distinct from old.scheduled_at or new.created_at is distinct from old.created_at
     or new.slot_id is distinct from old.slot_id or new.reschedule_count is distinct from old.reschedule_count
     or new.last_rescheduled_by is distinct from old.last_rescheduled_by then
    raise exception 'Use Reschedule to change the time of a session.';
  end if;

  if me = old.guide_id then
    if new.learner_note is distinct from old.learner_note then
      raise exception 'Only the learner can edit their note.';
    end if;
    if new.status is distinct from old.status and not (
         (old.status = 'requested' and new.status in ('accepted','declined'))
      or (old.status = 'accepted'  and new.status in ('completed','cancelled'))) then
      raise exception 'A booking cannot move from % to %.', old.status, new.status;
    end if;
  elsif me = old.learner_id then
    if new.meeting_link is distinct from old.meeting_link or new.guide_note is distinct from old.guide_note then
      raise exception 'Only the guide can change the meeting link or guide note.';
    end if;
    if new.status is distinct from old.status and not
       (old.status in ('requested','accepted') and new.status = 'cancelled') then
      raise exception 'You can only cancel a requested or accepted booking.';
    end if;
  else
    raise exception 'Not allowed.';
  end if;
  return new;
end $$;

-- Free future slots for one guide. Shows times only, never who booked what.
create or replace function public.open_slots(p_guide uuid)
returns table (id uuid, starts_at timestamptz)
language sql stable security definer set search_path = public as $$
  select s.id, s.starts_at
    from public.availability_slots s
   where s.guide_id = p_guide
     and s.starts_at >= now() + interval '2 hours'
     and (exists (select 1 from public.guide_profiles g where g.user_id = p_guide and g.is_verified)
          or p_guide = auth.uid() or public.is_admin())
     and public.slot_is_free(s.id)
   order by s.starts_at
$$;

-- Move an upcoming session to another free slot of the same guide.
create or replace function public.reschedule_booking(p_booking uuid, p_slot uuid)
returns public.bookings
language plpgsql security definer set search_path = public as $$
declare
  b  public.bookings;
  sl public.availability_slots;
  by_whom text;
begin
  select * into b from public.bookings where id = p_booking for update;
  if not found then raise exception 'Booking not found.'; end if;

  if auth.uid() = b.learner_id then by_whom := 'learner';
  elsif auth.uid() = b.guide_id then by_whom := 'guide';
  elsif public.is_admin() then by_whom := 'admin';
  else raise exception 'Not allowed.';
  end if;

  if b.status not in ('requested','accepted') then
    raise exception 'Only upcoming sessions can be rescheduled.';
  end if;
  select * into sl from public.availability_slots where id = p_slot and guide_id = b.guide_id;
  if not found then raise exception 'That time slot is not available. Please choose another.'; end if;
  if sl.starts_at < now() + interval '2 hours' then
    raise exception 'Choose a slot at least 2 hours from now.';
  end if;
  if not public.slot_is_free(p_slot, b.id) then
    raise exception 'That time slot has just been taken. Please choose another.';
  end if;

  perform set_config('nextrung.reschedule', 'on', true);
  update public.bookings
     set slot_id = p_slot,
         scheduled_at = sl.starts_at,
         -- a learner's change needs the guide's OK again; a guide's or admin's change stands
         status = case when by_whom = 'learner' then 'requested' else b.status end,
         reschedule_count = b.reschedule_count + 1,
         last_rescheduled_by = by_whom
   where id = b.id
   returning * into b;
  perform set_config('nextrung.reschedule', 'off', true);
  return b;
end $$;

-- ---------- Access -----------------------------------------------------------------

drop policy if exists slots_read on public.availability_slots;
drop policy if exists slots_insert on public.availability_slots;
drop policy if exists slots_delete on public.availability_slots;

-- guides see and manage their own slots; learners see free times through open_slots()
create policy slots_read on public.availability_slots for select
  using (guide_id = auth.uid() or public.is_admin());
create policy slots_insert on public.availability_slots for insert
  with check (guide_id = auth.uid() and starts_at > now());
create policy slots_delete on public.availability_slots for delete
  using (guide_id = auth.uid() and public.slot_is_free(id));

grant select, insert, delete on public.availability_slots to authenticated;
revoke all on function public.reschedule_booking(uuid, uuid) from public, anon;
grant execute on function public.reschedule_booking(uuid, uuid) to authenticated;
grant execute on function public.open_slots(uuid) to anon, authenticated;
