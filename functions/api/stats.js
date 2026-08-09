const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "public, max-age=300",
  "x-content-type-options": "nosniff",
};

export async function onRequestGet({ env }) {
  if (!env.ANALYTICS_DB) {
    return new Response(JSON.stringify({ configured: false }), {
      status: 503,
      headers: JSON_HEADERS,
    });
  }

  const [summary, countries, locations, daily] = await env.ANALYTICS_DB.batch([
    env.ANALYTICS_DB.prepare(`
      SELECT COUNT(*) AS page_views,
             COUNT(DISTINCT visitor_id) AS unique_visitors
      FROM page_views
      WHERE is_bot = 0
    `),
    env.ANALYTICS_DB.prepare(`
      SELECT country, COUNT(*) AS page_views
      FROM page_views
      WHERE is_bot = 0 AND country != 'Unknown'
      GROUP BY country
      ORDER BY page_views DESC, country ASC
    `),
    env.ANALYTICS_DB.prepare(`
      SELECT country, region, city,
             ROUND(AVG(latitude), 3) AS latitude,
             ROUND(AVG(longitude), 3) AS longitude,
             COUNT(*) AS page_views
      FROM page_views
      WHERE is_bot = 0 AND latitude IS NOT NULL AND longitude IS NOT NULL
      GROUP BY country, region, city
      ORDER BY page_views DESC
      LIMIT 100
    `),
    env.ANALYTICS_DB.prepare(`
      SELECT date(visited_at) AS date, COUNT(*) AS page_views
      FROM page_views
      WHERE is_bot = 0 AND visited_at >= datetime('now', '-29 days')
      GROUP BY date(visited_at)
      ORDER BY date ASC
    `),
  ]);

  const totals = summary.results[0] || { page_views: 0, unique_visitors: 0 };
  return new Response(JSON.stringify({
    configured: true,
    totals: {
      pageViews: totals.page_views,
      uniqueVisitors: totals.unique_visitors,
      countries: countries.results.length,
    },
    countries: countries.results,
    locations: locations.results,
    daily: daily.results,
    generatedAt: new Date().toISOString(),
  }), { headers: JSON_HEADERS });
}
