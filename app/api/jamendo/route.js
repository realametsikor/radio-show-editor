export async function GET() {
  const clientId = process.env.JAMENDO_CLIENT_ID;

  if (!clientId) {
    return Response.json(
      { error: "JAMENDO_CLIENT_ID is not configured" },
      { status: 500 }
    );
  }

  const res = await fetch(
    `https://api.jamendo.com/v3.0/tracks/?client_id=${clientId}&format=json&limit=10&tags=ambient`
  );

  if (!res.ok) {
    return Response.json(
      { error: "Failed to fetch tracks from Jamendo" },
      { status: res.status }
    );
  }

  const data = await res.json();

  return Response.json(data.results);
}
