-- Restrict which columns of `users` a client can write directly. In particular,
-- `is_premium` must never be client-writable — otherwise any signed-in user could grant
-- themselves Premium with a single `.update({ is_premium: true })` call, since the RLS
-- policy on `users` only checks `id = auth.uid()`, not which columns changed. The real
-- flip happens server-side in the revenuecat-webhook Edge Function (using the service
-- role) when RevenueCat confirms a purchase. `invite_code` is similarly excluded so a
-- user can't mint a fresh code and abandon the one they've already shared.

revoke update on public.users from authenticated;
grant update (display_name, avatar_emoji, avatar_color, avatar_url, notification_time, notifications_enabled, timezone)
  on public.users to authenticated;
