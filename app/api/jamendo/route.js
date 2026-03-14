export async function GET() {

  const clientId = process.env.JAMENDO_CLIENT_ID;

  const res = await fetch(
    `https://api.jamendo.com/v3.0/tracks/?client_id=${clientId}&format=json&limit=10&tags=ambient`
  );

  const data = await res.json();

  return Response.json(data.results);
}
