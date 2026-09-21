"""Render the scan into a single self-contained index.html for GitHub Pages."""
import datetime as dt
import json

from jinja2 import Template

import config

# Simple line icons. Stroke uses currentColor so they follow the theme.
ICONS = {
    "backpack": (
        '<path d="M6 9a6 6 0 0 1 12 0v10a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9Z"/>'
        '<path d="M9 9V6a3 3 0 0 1 6 0v3"/>'
        '<path d="M9 14h6"/>'
    ),
    "cabin": (
        '<rect x="5" y="8" width="14" height="13" rx="2"/>'
        '<path d="M9 8V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3"/>'
        '<path d="M12 3v1"/><path d="M9 21v1"/><path d="M15 21v1"/>'
    ),
    "checked": (
        '<rect x="3" y="7" width="18" height="14" rx="2"/>'
        '<path d="M8 7V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v3"/>'
        '<path d="M3 12h18"/>'
    ),
}

TEMPLATE = Template(
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TLV to Nuremberg</title>
<style>
  :root{
    --bg:#f6f7f9; --card:#fff; --ink:#15181d; --muted:#666e7a; --line:#e3e6ea;
    --accent:#1a6cff; --good:#0a7d4a; --good-bg:#e6f6ee; --warn:#8a6100; --off:#c3c8cf;
  }
  @media (prefers-color-scheme:dark){ :root:not([data-theme="light"]){
    --bg:#101317; --card:#181c22; --ink:#e8eaed; --muted:#9aa3ad; --line:#2a2f37;
    --accent:#63a0ff; --good:#4ade9a; --good-bg:#12291f; --warn:#e0b44a; --off:#4a515b;
  }}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);padding-block:28px;padding-left:16px;padding-right:16px;
       font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  .wrap{max-width:1080px;margin:0 auto}
  h1{font-size:22px;margin:0 0 4px}
  .sub{color:var(--muted);font-size:13px;margin-bottom:18px}
  .bar{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:18px}
  .stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;flex:1;min-width:140px}
  .stat b{display:block;font-size:20px}
  .stat span{color:var(--muted);font-size:12px}
  .tablewrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:12px}
  table{border-collapse:collapse;width:100%;min-width:760px;font-size:14px}
  th,td{padding:11px 12px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
  th{font-size:12px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.03em;
     cursor:pointer;user-select:none;position:sticky;top:0;background:var(--card)}
  th[data-sort]:after{content:" \\2195";opacity:.35}
  tbody tr:last-child td{border-bottom:0}
  tbody tr:hover{background:color-mix(in srgb,var(--accent) 6%,transparent)}
  .price{font-weight:700;font-size:15px}
  tr.cheap{background:var(--good-bg)}
  tr.cheap .price{color:var(--good)}
  .pill{display:inline-block;font-size:11px;padding:2px 7px;border-radius:99px;
        border:1px solid var(--line);color:var(--muted);margin-left:6px}
  .pill.bus{color:var(--warn);border-color:currentColor}
  .bags{display:flex;gap:7px;align-items:center}
  .bag{position:relative;display:inline-flex;cursor:help;line-height:0}
  .bag svg{width:21px;height:21px;fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
  .bag.yes svg{stroke:var(--good)}
  .bag.no svg{stroke:var(--off)}
  .bag.no:after{content:"";position:absolute;left:1px;right:1px;top:50%;height:1.6px;
                background:var(--off);transform:rotate(-38deg)}
  .tip{position:absolute;bottom:130%;left:50%;transform:translateX(-50%);width:238px;
       background:var(--ink);color:var(--card);padding:9px 11px;border-radius:8px;font-size:12px;
       line-height:1.45;white-space:normal;opacity:0;pointer-events:none;transition:opacity .12s;z-index:9}
  .bag:hover .tip,.bag:focus-visible .tip{opacity:1}
  .tip b{display:block;margin-bottom:3px}
  .note{color:var(--muted);font-size:12.5px;margin-top:16px}
  .note code{background:var(--card);border:1px solid var(--line);padding:1px 5px;border-radius:4px}
  .empty{padding:28px;text-align:center;color:var(--muted)}
  .spark{display:block;margin-top:6px}
  a{color:var(--accent)}
  @media(max-width:560px){ h1{font-size:19px} .stat b{font-size:17px} }
</style>
</head>
<body>
<div class="wrap">
  <h1>{{ origin }} &rarr; {{ destination }} &middot; June 2027</h1>
  <div class="sub">
    Round trip, 1 adult, economy &middot; outbound {{ outbound_dates|join(" or ") }},
    return {{ return_dates|join(" or ") }}<br>
    Max {{ max_stops }} stop &middot; layover &le; {{ max_layover }} min &middot;
    {% if arrive_by %}arrives by {{ arrive_by }}:00{% else %}any time of day{% endif %} &middot; flights only &middot;
    no connections in {{ blocked|join(", ") }}
  </div>

  <div class="bar">
    <div class="stat"><b>{{ "{:,}".format(cheapest) if cheapest else "&mdash;" }} &#8362;</b>
      <span>cheapest now</span></div>
    <div class="stat"><b>{{ "{:,}".format(all_time_low) if all_time_low else "&mdash;" }} &#8362;</b>
      <span>lowest ever seen</span>
      {% if spark %}<svg class="spark" width="100%" height="24" viewBox="0 0 100 24"
        preserveAspectRatio="none"><polyline points="{{ spark }}" fill="none"
        stroke="var(--accent)" stroke-width="1.6"/></svg>{% endif %}</div>
    <div class="stat"><b>{{ offers|length }}</b><span>options matching your rules</span></div>
    <div class="stat"><b>{{ "{:,}".format(threshold) }} &#8362;</b><span>alert threshold</span></div>
  </div>

  <div class="tablewrap">
  {% if offers %}
  <table id="t">
    <thead><tr>
      <th data-sort="num">Price</th>
      <th>Airline</th>
      <th>Route</th>
      <th>Dates</th>
      <th>Depart</th>
      <th>Arrive</th>
      <th data-sort="num">Layover</th>
      <th data-sort="num">Duration</th>
      <th>Baggage</th>
      <th></th>
    </tr></thead>
    <tbody>
    {% for o in offers %}
      <tr class="{{ 'cheap' if o.price < threshold else '' }}">
        <td class="price" data-v="{{ o.price }}">{{ "{:,}".format(o.price) }} &#8362;</td>
        <td>{{ o.airlines|join(", ") or "&mdash;" }}</td>
        <td>{{ origin }}&rarr;{% for l in o.layovers %}{{ l.airport_code or l.airport_name }}&rarr;{% endfor %}{{ destination }}
          {% if o.ground_mode %}<span class="pill bus">Flight + {{ o.ground_mode }}</span>{% endif %}</td>
        <td>{{ o.outbound_date[5:] }} &rarr; {{ o.return_date[5:] }}</td>
        <td>{{ o.depart_time }}</td>
        <td>{{ o.arrive_time }}</td>
        <td data-v="{{ o.max_layover_minutes }}">{{ o.layover_summary }}</td>
        <td data-v="{{ o.duration_minutes }}">{{ o.duration }}</td>
        <td><div class="bags">
          {% for key, label, bag in [("backpack","Backpack / personal item",o.backpack),
                                     ("cabin","Cabin trolley",o.cabin),
                                     ("checked","Checked bag",o.checked)] %}
          <span class="bag {{ 'yes' if bag.included else 'no' }}" tabindex="0">
            <svg viewBox="0 0 24 24">{{ icons[key] }}</svg>
            <span class="tip"><b>{{ label }}</b>{{ bag.note }}
              {% if bag.source == "policy" %} <i>(policy, not live-quoted)</i>{% endif %}</span>
          </span>
          {% endfor %}
        </div></td>
        <td><a href="{{ o.booking_url }}" target="_blank" rel="noopener">Book</a></td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}
    <div class="empty">
      <p><b>No fares matched your rules on this scan.</b></p>
      {% if rejected %}<p>Rejected: {% for k,v in rejected.items() %}{{ v }} {{ k }}{{ ", " if not loop.last }}{% endfor %}.</p>{% endif %}
      <p>Relax a rule in <code>config.py</code> if this persists.</p>
    </div>
  {% endif %}
  </div>

  <p class="note">
    Updated {{ updated }} &middot; source: Google Flights &middot; prices are round-trip
    totals for 1 adult in {{ currency }}.<br>
    Baggage: hover an icon for the cheapest fare that includes that bag. Google
    re-prices to a different fare brand when a bag is requested, so these are real
    fare totals, not add-on fees.
    {% if rejected and offers %}<br>Filtered out this scan:
      {% for k,v in rejected.items() %}{{ v }} {{ k }}{{ ", " if not loop.last }}{% endfor %}.{% endif %}
  </p>
</div>
<script>
document.querySelectorAll('th[data-sort]').forEach(function(th,i){
  th.addEventListener('click',function(){
    var tb=th.closest('table').tBodies[0], idx=[].indexOf.call(th.parentNode.children,th);
    var dir=th.dataset.dir==='a'?-1:1; th.dataset.dir=dir===1?'a':'d';
    [].slice.call(tb.rows).sort(function(x,y){
      var a=+x.cells[idx].dataset.v, b=+y.cells[idx].dataset.v; return (a-b)*dir;
    }).forEach(function(r){tb.appendChild(r)});
  });
});
</script>
</body>
</html>"""
)


def _sparkline(history, width=100, height=24):
    pts = [h["min_price"] for h in history][-40:]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1
    step = width / (len(pts) - 1)
    return " ".join(
        f"{i * step:.1f},{height - (p - lo) / span * (height - 3) - 1.5:.1f}"
        for i, p in enumerate(pts)
    )


def render(offers, state, rejected=None, path=None):
    path = path or config.OUTPUT_HTML
    html = TEMPLATE.render(
        offers=offers,
        icons=ICONS,
        rejected=rejected or {},
        origin=config.ORIGIN,
        destination=config.DESTINATION,
        outbound_dates=config.OUTBOUND_DATES,
        return_dates=config.RETURN_DATES,
        max_stops=config.MAX_STOPS,
        max_layover=config.MAX_LAYOVER_MINUTES,
        arrive_by=config.LATEST_ARRIVAL_HOUR,
        blocked=sorted(config.BLOCKED_COUNTRIES),
        currency=config.CURRENCY,
        threshold=config.PRICE_THRESHOLD_NIS,
        cheapest=min((o.price for o in offers), default=None),
        all_time_low=state.get("all_time_low"),
        spark=_sparkline(state.get("history", [])),
        updated=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path
