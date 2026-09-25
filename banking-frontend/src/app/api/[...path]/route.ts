import { NextRequest, NextResponse } from "next/server";
const root = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
async function boundedBody(request: NextRequest) {
  const reader = request.body?.getReader();
  if (!reader) return undefined;
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 6 * 1024 * 1024) {
        await reader.cancel();
        throw new RangeError("Upload is too large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const result = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return result;
}
async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  if (path.some((p) => !/^[a-zA-Z0-9_-]+$/.test(p)))
    return NextResponse.json({ detail: "Invalid API path" }, { status: 400 });
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const token = request.headers.get("authorization");
  if (token) headers.set("Authorization", token);
  try {
    const upstream = await fetch(
      `${root}/api/v1/${path.join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        body: request.method === "GET" ? undefined : await boundedBody(request),
        cache: "no-store",
        signal: AbortSignal.timeout(20000),
        redirect: "error",
      },
    );
    return new NextResponse(
      upstream.status === 204 ? null : await upstream.arrayBuffer(),
      {
        status: upstream.status,
        headers: {
          "Content-Type":
            upstream.headers.get("content-type") || "application/octet-stream",
          ...(upstream.headers.get("content-disposition")
            ? {
                "Content-Disposition": upstream.headers.get(
                  "content-disposition",
                )!,
              }
            : {}),
          "X-Content-Type-Options": "nosniff",
          "Cache-Control": "no-store",
        },
      },
    );
  } catch (error) {
    if (error instanceof RangeError)
      return NextResponse.json(
        { detail: "Each identity file must be 5 MB or smaller." },
        { status: 413 },
      );
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
