// Supabase Edge Function: delete-account
//
// Permanently deletes the calling user's account. Invoked from the app with the
// user's own JWT (Settings → Delete Account); the function verifies that JWT, then
// uses the service role to delete the auth.users row. Every other table (public.users,
// streaks, question_attempts, puzzle_attempts, friendships) cascades via `on delete
// cascade` foreign keys, so nothing needs to be deleted manually here.
//
// Deploy: supabase functions deploy delete-account

import { createClient } from 'jsr:@supabase/supabase-js@2';

Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return json({ error: 'Method not allowed' }, 405);
  }

  const authHeader = req.headers.get('Authorization');
  if (!authHeader) {
    return json({ error: 'Missing Authorization header' }, 401);
  }

  // Verify the caller's JWT using the anon key + their own token (never trust a
  // user-supplied id — only ever delete the account the JWT actually belongs to).
  const userClient = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_ANON_KEY')!, {
    global: { headers: { Authorization: authHeader } },
  });
  const {
    data: { user },
    error: userError,
  } = await userClient.auth.getUser();
  if (userError || !user) {
    return json({ error: 'Invalid session' }, 401);
  }

  const adminClient = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  );
  const { error: deleteError } = await adminClient.auth.admin.deleteUser(user.id);
  if (deleteError) {
    return json({ error: deleteError.message }, 500);
  }

  return json({ ok: true }, 200);
});

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
