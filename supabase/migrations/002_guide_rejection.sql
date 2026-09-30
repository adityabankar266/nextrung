-- Update 2 (30 Sep 2026): lets admins reject a guide application.
-- Run once in Supabase: SQL Editor -> New query -> paste -> Run. Safe to run again.

alter table public.guide_profiles
  add column if not exists is_rejected boolean not null default false;

create or replace function public.guard_guide_profile()
returns trigger language plpgsql as $$
begin
  if not public.is_trusted() then
    new.is_verified := old.is_verified;
    new.is_rejected := old.is_rejected;
  end if;
  if new.is_verified then new.is_rejected := false; end if;
  new.user_id := old.user_id;
  return new;
end $$;
