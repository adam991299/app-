export const dynamic = "force-dynamic";

export function GET(): Response {
  return Response.json({ service: "web", status: "ok", time: new Date().toISOString() });
}
