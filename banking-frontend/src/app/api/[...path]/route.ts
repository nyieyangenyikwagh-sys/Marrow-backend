import { NextRequest, NextResponse } from "next/server";
const root = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  if (path.some((p) => !/^[a-zA-Z0-9_-]+$/.test(p)))
    return NextResponse.json({ detail: "Invalid API path" }, { status: 400 });
  const headers = new Headers({ "Content-Type": "application/json" });
  const token = request.headers.get("authorization");
  if (token) headers.set("Authorization", token);
  try {
    const upstream = await fetch(
      `${root}/api/v1/${path.join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        body: request.method === "GET" ? undefined : await request.text(),
        cache: "no-store",
        signal: AbortSignal.timeout(20000),
        redirect: "error",
      },
    );
    return new NextResponse(
      upstream.status === 204 ? null : await upstream.text(),
      {
        status: upstream.status,
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
        },
      },
    );
  } catch {
    return NextResponse.json(
      {
        detail:
          "The banking service is unavailable. Check that the API is running and try again.",
      },
      { status: 503 },
    );
  }
}
export { proxy as GET, proxy as POST, proxy as PATCH };
