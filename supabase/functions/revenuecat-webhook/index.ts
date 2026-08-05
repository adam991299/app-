// Supabase Edge Function: revenuecat-webhook
//
// RevenueCat calls this server-to-server whenever a subscription event happens
// (purchase, renewal, cancellation, expiration, billing issue, etc). It's the only
// place `public.users.is_premium` gets written — see 0008_users_column_privileges.sql,
// which deliberately blocks the client from writing that column itself.
//
// Setup:
//   1. Deploy: supabase functions deploy revenuecat-webhook --no-verify-jwt
//   2. In RevenueCat: Project Settings → Integrations → Webhooks → add this function's
//      URL, and set an "Authorization header value" — copy that same value into:
//      supabase secrets set REVENUECAT_WEBHOOK_SECRET=<the value you set in RevenueCat>
//
// RevenueCat sends `app_user_id`, which we set to the Supabase auth user id via
// `Purchases.configure({ appUserID })` / `Purchases.logIn()` in lib/revenuecat.ts — so
// event.app_user_id here is directly usable as the `users.id` to update.

import { createClient } from 'jsr:@supabase/supabase-js@2';

const ENTITLEMENT_GRANTING_EVENTS = new Set([
  'INITIAL_PURCHASE',
  'RENEWAL',
  'UNCANCELLATION',
  'PRODUCT_CHANGE',
  'TRANSFER',
]);

const ENTITLEMENT_REVOKING_EVENTS = new Set(['EXPIRATION', 'CANCELLATION', 'BILLING_ISSUE']);

Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return json({ error: 'Method not allowed' }, 405);
  }

  const expectedSecret = Deno.env.get('REVENUECAT_WEBHOOK_SECRET');
  const providedSecret = req.headers.get('Authorization');
  if (!expectedSecret || providedSecret !== `Bearer ${expectedSecret}`) {
    return json({ error: 'Unauthorized' }, 401);
  }

  let body: { event?: { type?: string; app_user_id?: string } };
  try {
    body = await req.json();
  } catch {
    return json({ error: 'Invalid JSON body' }, 400);
  }

  const event = body.event;
  if (!event?.type || !event.app_user_id) {
    return json({ error: 'Missing event.type or event.app_user_id' }, 400);
  }

  // Ignore anything that isn't an entitlement grant/revoke (test events, etc) — 2xx so
  // RevenueCat doesn't retry.
  if (!ENTITLEMENT_GRANTING_EVENTS.has(event.type) && !ENTITLEMENT_REVOKING_EVENTS.has(event.type)) {
    return json({ ok: true, ignored: event.type }, 200);
  }

  const isPremium = ENTITLEMENT_GRANTING_EVENTS.has(event.type);
  const supabase = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!);

  const { error } = await supabase.from('users').update({ is_premium: isPremium }).eq('id', event.app_user_id);
  if (error) {
    return json({ error: error.message }, 500);
  }

  return json({ ok: true, user_id: event.app_user_id, is_premium: isPremium }, 200);
});

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
