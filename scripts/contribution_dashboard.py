"""Render an activity dashboard from GitHub's public contribution calendar.

The public page provides dates and accessible count labels. Fail closed if its
markup changes; keep the last good SVG rather than displaying fabricated data.
"""
import re
import os
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree

class Calendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}
        self.labels = {}
        self.key = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "td" and a.get("data-date") and a.get("id") and "data-level" in a:
            self.days[a["id"]] = a["data-date"]
        if tag == "tool-tip" and a.get("for", "").startswith("contribution-day-component"):
            self.key = a["for"]
            self.labels[self.key] = ""
    def handle_data(self, data):
        if self.key:
            self.labels[self.key] += data
    def handle_endtag(self, tag):
        if tag == "tool-tip":
            self.key = None

def fetch_calendar():
    owner = os.environ["PROFILE_OWNER"]
    if not re.fullmatch(r"[A-Za-z0-9-]+", owner):
        raise ValueError("Invalid owner")
    request = Request(f"https://github.com/users/{owner}/contributions", headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US"})
    with urlopen(request, timeout=30) as response:
        parser = Calendar()
        parser.feed(response.read().decode("utf-8"))
    values = {}
    for key, day in parser.days.items():
        label = parser.labels.get(key, "").strip()
        match = re.search(r"([\d,]+) contributions?", label)
        if match:
            count = int(match.group(1).replace(",", ""))
        elif "No contributions" in label:
            count = 0
        else:
            raise ValueError("Missing or unrecognized contribution label")
        values[date.fromisoformat(day)] = count
    if not 350 <= len(values) <= 380:
        raise ValueError("Unexpected calendar length")
    days = sorted(values)
    if any(b-a != timedelta(days=1) for a,b in zip(days,days[1:])):
        raise ValueError("Calendar dates are not contiguous")
    return values

def render(values):
    days = sorted(values)
    total = sum(values.values())
    streak = longest = run = 0
    for day in days:
        run = run + 1 if values[day] else 0
        longest = max(longest, run)
    end = len(days)-1
    if not values[days[end]]: end -= 1
    while end >= 0 and values[days[end]]:
        streak += 1
        end -= 1
    recent = days[-60:]
    counts = [values[d] for d in recent]
    maximum = max(1, max(counts))
    step = 828 / (len(recent)-1)
    pts = [(36+i*step, 246-116*v/maximum) for i,v in enumerate(counts)]
    points = " ".join(f"{x:.2f},{y:.2f}" for x,y in pts)
    area = f"36,246 {points} 864,246"
    def t(x,y,v,size=14,color="#b3c5df",weight=400,anchor="start"):
        return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{v}</text>'
    head = '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="300" viewBox="0 0 900 300" role="img" aria-label="GitHub contribution activity and streaks"><title>GitHub contribution activity and streaks</title><defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#101a32"/><stop offset="1" stop-color="#080e1d"/></linearGradient><linearGradient id="line"><stop stop-color="#49ddff"/><stop offset="1" stop-color="#aa91ff"/></linearGradient></defs><rect x="1" y="1" width="898" height="298" rx="18" fill="url(#bg)" stroke="#35435e"/><g font-family="Arial,Helvetica,sans-serif">'
    body = t(28,35,"CONTRIBUTION ACTIVITY",19,"#75defe",700)+t(872,35,"GITHUB CALENDAR",11,"#a2b3cf",700,"end")
    for x,v,label in [(28,total,"Contributions / past year"),(320,streak,"Current streak / days"),(614,longest,"Longest streak / days")]:
        body += f'<rect x="{x}" y="48" width="258" height="65" rx="10" fill="#17243b" stroke="#314461"/>'+t(x+14,76,f"{v:,}",24,"#f4f8ff",700)+t(x+14,98,label,12)
    for y in (130,159,188,217,246):
        body += f'<path d="M36 {y}H864" stroke="#34435c" stroke-opacity=".7"/>'
    body += f'<polygon points="{area}" fill="#51c6ff" fill-opacity=".12"/><polyline points="{points}" stroke="url(#line)" stroke-width="2.5" fill="none" stroke-linejoin="round"/>'
    for i in (0,14,29,44,59):
        x,_=pts[i]
        body+=t(x,270,recent[i].strftime("%b %d"),11,"#a2b3cf",400,"start" if i==0 else "end" if i==59 else "middle")
    body+=t(28,289,"Daily contributions · last 60 days · native GitHub calendar",10,"#94a7c5")+t(872,289,days[-1].isoformat(),10,"#94a7c5",400,"end")
    return head+body+"</g></svg>\n"

if __name__ == "__main__":
    output = render(fetch_calendar())
    ElementTree.fromstring(output)
    Path("assets/contribution-dashboard.svg").write_text(output, encoding="utf-8")
