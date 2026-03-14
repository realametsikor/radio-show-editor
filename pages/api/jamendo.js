export default async function handler(req, res) {

  const clientId = process.env.JAMENDO_CLIENT_ID;

  const response = await fetch(
    `https://api.jamendo.com/v3.0/tracks/?client_id=${clientId}&format=json&limit=10&tags=ambient`
  );

  const data = await response.json();

  res.status(200).json(data.results);
}
