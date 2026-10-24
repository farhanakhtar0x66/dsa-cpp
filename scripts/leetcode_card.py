#!/usr/bin/env python3
"""Build static LeetCode cards from public data; no third-party packages.
--fetch refreshes the snapshot and both SVGs. Without it, rendering is offline.
--check verifies outputs against the recorded snapshot, not today's date.
"""
import argparse
from datetime import date, datetime, timedelta, timezone
from html import escape
import json
import math
from pathlib import Path
import re
import urllib.request
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
USERNAME='farhanakhtar0x66'
DIFFICULTIES=('All','Easy','Medium','Hard')
QUERY='''query Profile($username:String!,$year:Int!,$previous:Int!){
allQuestionsCount{difficulty count}
matchedUser(username:$username){username submitStatsGlobal{acSubmissionNum{difficulty count}}
current:userCalendar(year:$year){submissionCalendar}
previous:userCalendar(year:$previous){submissionCalendar}}}'''


def counts(items):
    result={item['difficulty']:item['count'] for item in items}
    if any(type(result.get(k)) is not int or result[k]<0 for k in DIFFICULTIES):
        raise ValueError('Missing or invalid difficulty totals')
    if result['All'] != sum(result[k] for k in DIFFICULTIES[1:]):
        raise ValueError('Difficulty totals do not add up')
    return {k:result[k] for k in DIFFICULTIES}


def normalize(payload,username,fetched_at):
    if payload.get('errors'):
        raise ValueError('LeetCode returned GraphQL errors: '+str(payload['errors']))
    data=payload.get('data') or {}; user=data.get('matchedUser')
    if not user or user.get('username','').lower()!=username.lower():
        raise ValueError('LeetCode user was not found; refusing to invent a zero state')
    calendar={}
    for key in ('previous','current'):
        raw=user[key]['submissionCalendar']
        raw=json.loads(raw) if isinstance(raw,str) else raw
        if not isinstance(raw,dict):raise ValueError('Invalid submission calendar')
        for timestamp,n in raw.items():
            if type(n) is not int or n<0:raise ValueError('Invalid submission count')
            day=datetime.fromtimestamp(int(timestamp),timezone.utc).date().isoformat()
            calendar[day]=max(calendar.get(day,0),n)
    return {'username':user['username'],'fetched_at':fetched_at,
            'solved':counts(user['submitStatsGlobal']['acSubmissionNum']),
            'totals':counts(data['allQuestionsCount']),'calendar':dict(sorted(calendar.items())),
            'calendar_timezone':'UTC','source':'https://leetcode.com/u/'+username+'/'}


def activity(calendar,today):
    start=today-timedelta(days=364)
    visible={date.fromisoformat(d):n for d,n in calendar.items() if n>0 and start<=date.fromisoformat(d)<=today}
    run=best=0;day=start
    while day<=today:
        run=run+1 if day in visible else 0;best=max(best,run);day+=timedelta(days=1)
    day=today if calendar.get(today.isoformat(),0)>0 else today-timedelta(days=1)
    current=0
    while calendar.get(day.isoformat(),0)>0:
        current+=1;day-=timedelta(days=1)
    return {'current':current,'best':best,'active_days':len(visible),'submissions':sum(visible.values())}


def fetch(username=USERNAME):
    now=datetime.now(timezone.utc)
    def request_years(year):
        body={'query':QUERY,'variables':{'username':username,'year':year,'previous':year-1}}
        req=urllib.request.Request('https://leetcode.com/graphql/',data=json.dumps(body).encode(),
            headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0 (compatible; PublicProfileCard/1.0)',
                     'Referer':'https://leetcode.com/u/'+username+'/'})
        with urllib.request.urlopen(req,timeout=30) as response:payload=json.load(response)
        return normalize(payload,username,now.isoformat(timespec='seconds'))
    snapshot=request_years(now.year)
    oldest=now.year-1
    # If an uninterrupted streak reaches our fetched boundary, load older years
    # until its real starting gap is known. A January rollover must not truncate it.
    while True:
        today=now.date();run=activity(snapshot['calendar'],today)['current']
        latest=today if snapshot['calendar'].get(today.isoformat(),0)>0 else today-timedelta(days=1)
        first=latest-timedelta(days=run-1) if run else None
        if first!=date(oldest,1,1):break
        older=request_years(oldest-1)
        for day,n in older['calendar'].items():
            snapshot['calendar'][day]=max(snapshot['calendar'].get(day,0),n)
        oldest-=2
    snapshot['calendar']=dict(sorted(snapshot['calendar'].items()))
    return snapshot


def validate(snapshot):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',snapshot['username']):raise ValueError('Invalid username')
    counts([{'difficulty':k,'count':v} for k,v in snapshot['solved'].items()])
    counts([{'difficulty':k,'count':v} for k,v in snapshot['totals'].items()])
    if any(snapshot['solved'][k]>snapshot['totals'][k] for k in DIFFICULTIES):raise ValueError('Solved count exceeds catalog total')
    if snapshot.get('calendar_timezone')!='UTC':raise ValueError('Calendar must use UTC day buckets')
    dt=datetime.fromisoformat(snapshot['fetched_at'])
    if dt.tzinfo is None:raise ValueError('Snapshot timestamp must include a timezone')
    for day,n in snapshot['calendar'].items():
        date.fromisoformat(day)
        if type(n) is not int or n<0:raise ValueError('Invalid calendar count')
    return dt.astimezone(timezone.utc)


def render(snapshot,mobile=False):
    fetched=validate(snapshot);today=fetched.date();stats=activity(snapshot['calendar'],today)
    w,h=(340,500) if mobile else (920,490)
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title desc">',
         '<title id="title">LeetCode activity — '+escape(snapshot['username'])+'</title>',
         f'<desc id="desc">{snapshot["solved"]["All"]} accepted problems. Current submission streak {stats["current"]} days. Heatmap counts all submissions in UTC, not only accepted solutions. Snapshot {escape(snapshot["fetched_at"])}.</desc>',
         '<style>text{font-family:ui-monospace,"SFMono-Regular",Consolas,"Liberation Mono",monospace;fill:#cdd6f4}</style>',
         f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="12" fill="#181825" stroke="#45475a"/>']
    def text(value,x,y,size=14,color='#cdd6f4',anchor='start'):
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" style="fill:{color}">{escape(str(value))}</text>')
    def rect(x,y,width,height,color,rx=0):
        out.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{rx}" fill="{color}"/>')
    text('$ dsa --leetcode',24,33,18,'#b4befe')
    text(snapshot['username'],24 if mobile else w-26,57 if mobile else 33,13,'#a6adc8','start' if mobile else 'end')
    cx,cy,r=(67,148,43) if mobile else (108,150,61)
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#313244" stroke-width="7"/>')
    fraction=snapshot['solved']['All']/max(snapshot['totals']['All'],1)
    if fraction:
        circumference=2*math.pi*r
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#b4befe" stroke-width="7" stroke-linecap="round" stroke-dasharray="{fraction*circumference:.2f} {circumference:.2f}" transform="rotate(-90 {cx} {cy})"/>')
    text(snapshot['solved']['All'],cx,cy+10,34 if mobile else 42,anchor='middle')
    text('accepted',cx,cy+29,11,'#a6adc8','middle')
    x=133 if mobile else 231;right=w-27;barwidth=right-x
    for i,(difficulty,color) in enumerate(zip(DIFFICULTIES[1:],('#a6e3a1','#f9e2af','#f38ba8'))):
        y=(102 if mobile else 100)+i*45
        text(difficulty,x,y,15 if mobile else 15,color)
        solved,total=snapshot['solved'][difficulty],snapshot['totals'][difficulty]
        text(f'{solved} / {total}',right,y,12 if mobile else 14,'#a6adc8','end')
        rect(x,y+11,barwidth,5,'#313244',2)
        if solved:rect(x,y+11,max(2,barwidth*solved/max(total,1)),5,color,2)
    rect(24,235,w-48,1,'#313244')
    for label,value,x in zip((('Current streak','Best · year','Active days') if mobile else ('Current streak','Best · past year','Active days · year')),(stats['current'],stats['best'],stats['active_days']),((24,134,244) if mobile else (28,330,630))):
        text(label,x,259,11 if mobile else 13,'#a6adc8')
        text(f'{value} days',x,285,18 if mobile else 23,'#b4befe')
    text('Submission activity · past year',24 if mobile else 28,320 if mobile else 311,12 if mobile else 14)
    start=today-timedelta(days=364);gridstart=start-timedelta(days=(start.weekday()+1)%7)
    gx,gy,stride,size=(24,343,5.6,4) if mobile else (61,328,15,11)
    palette=('#313244','#45475a','#585b70','#7f849c','#b4befe')
    for col in range(53):
        for row in range(7):
            day=gridstart+timedelta(days=col*7+row)
            if not start<=day<=today:continue
            n=snapshot['calendar'].get(day.isoformat(),0)
            level=0 if n==0 else 1 if n<3 else 2 if n<6 else 3 if n<10 else 4
            out.append(f'<rect x="{gx+col*stride:g}" y="{gy+row*stride:g}" width="{size}" height="{size}" rx="1" fill="{palette[level]}"><title>{day.isoformat()}: {n} submissions</title></rect>')
    if not mobile:
        for row,label in ((1,'M'),(3,'W'),(5,'F')):text(label,36,gy+row*stride+10,10,'#a6adc8')
    dates_y=411 if mobile else 451
    text(start.strftime('%d %b %Y'),gx,dates_y,10,'#a6adc8')
    text(today.strftime('%d %b %Y'),w-27,dates_y,10,'#a6adc8','end')
    if mobile:
        text('Heatmap & streak count all submissions.',24,439,11,'#a6adc8')
        text('Accepted totals count unique problems.',24,455,11,'#a6adc8')
    else:text('Heatmap & streak: all submissions · UTC days · accepted totals: unique problems',28,474,11,'#a6adc8')
    stamp=fetched.astimezone(ZoneInfo('Asia/Kolkata')).strftime('%d %b %Y, %H:%M IST')
    text('Updated '+stamp,24,480,10,'#9399b2') if mobile else text('Updated '+stamp,w-28,56,10,'#9399b2','end')
    return '\n'.join(out)+'\n</svg>\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group()
    group.add_argument('--fetch',action='store_true');group.add_argument('--check',action='store_true')
    args=parser.parse_args()
    try:
        snapshot=fetch() if args.fetch else json.loads((ROOT/'data/leetcode.json').read_text())
        validate(snapshot)
        outputs={'data/leetcode.json':json.dumps(snapshot,indent=2,ensure_ascii=False)+'\n',
                 'assets/leetcode.svg':render(snapshot),'assets/leetcode-mobile.svg':render(snapshot,True)}
        stale=[]
        for name,content in outputs.items():
            path=ROOT/name
            if args.check:
                if not path.exists() or path.read_text()!=content:stale.append(name)
            else:
                path.parent.mkdir(parents=True,exist_ok=True)
                temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(content,encoding='utf-8');temp.replace(path)
        if stale:parser.exit(1,'Stale LeetCode assets: '+', '.join(stale)+'\n')
        print('LeetCode assets match the recorded snapshot.' if args.check else 'Updated public LeetCode snapshot and static cards.')
    except (ValueError,KeyError,OSError) as exc:
        parser.exit(1,'LeetCode refresh failed; last committed snapshot remains available: '+str(exc)+'\n')

if __name__=='__main__':main()
