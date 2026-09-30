-- Update 4 (30 Sep 2026): profile photos and payout details.
-- Run once in Supabase: SQL Editor -> New query -> paste -> Run. Safe to run again.

-- ---------- Profile photo ------------------------------------------------------
-- Only photos stored in this project's "avatars" bucket are accepted, never outside links.
alter table public.profiles
  add column if not exists avatar_url text
  check (avatar_url is null or avatar_url ~ '^https://[^/]+/storage/v1/object/public/avatars/');

-- ---------- Guide payout details (private) -------------------------------------------
alter table public.contacts
  add column if not exists payout_upi text
  check (payout_upi is null or payout_upi ~ '^[A-Za-z0-9._-]{2,64}@[A-Za-z][A-Za-z0-9]{1,63}$');

-- ---------- Directory shows the photo ---------------------------------------------------
create or replace view public.guide_directory with (security_invoker = true) as
select g.user_id as guide_id,
       p.full_name,
       g.headline,
       g.field,
       g.years_experience,
       g.bio,
       g.linkedin_url,
       g.availability,
       (select min(s.price_inr) from public.services s where s.guide_id = g.user_id and s.is_active) as from_price,
       (select round(avg(r.rating)::numeric, 1) from public.reviews r where r.guide_id = g.user_id) as rating,
       (select count(*) from public.reviews r where r.guide_id = g.user_id) as review_count,
       p.avatar_url
  from public.guide_profiles g
  join public.profiles p on p.id = g.user_id
 where g.is_verified;
grant select on public.guide_directory to anon, authenticated;

-- ---------- Photo storage ---------------------------------------------------------------
-- Public bucket: anyone can view a photo by its link; only the owner can add or change it.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('avatars', 'avatars', true, 2097152, array['image/jpeg','image/png','image/webp'])
on conflict (id) do update
  set public = true, file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

-- each person may only write inside a folder named after their own user id
drop policy if exists "avatars: read own" on storage.objects;
drop policy if exists "avatars: upload own" on storage.objects;
drop policy if exists "avatars: update own" on storage.objects;
drop policy if exists "avatars: delete own" on storage.objects;

create policy "avatars: read own" on storage.objects for select to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "avatars: upload own" on storage.objects for insert to authenticated
  with check (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "avatars: update own" on storage.objects for update to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text)
  with check (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "avatars: delete own" on storage.objects for delete to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);
