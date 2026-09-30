-- Update 6 (30 Sep 2026): learners can see the UPI ID of the guide they need to pay.
-- A learner sees a guide's UPI ID only for their own sessions that the guide has accepted
-- or completed. Everyone else's payout details stay private.
-- Run once in Supabase: SQL Editor -> New query -> paste -> Run. Safe to run again.

create or replace function public.my_payment_details()
returns table (booking_id uuid, upi text)
language sql stable security definer set search_path = public as $$
  select b.id, c.payout_upi
    from public.bookings b
    join public.contacts c on c.user_id = b.guide_id
   where b.learner_id = auth.uid()
     and b.status in ('accepted', 'completed')
     and c.payout_upi is not null;
$$;

revoke all on function public.my_payment_details() from public, anon;
grant execute on function public.my_payment_details() to authenticated;
