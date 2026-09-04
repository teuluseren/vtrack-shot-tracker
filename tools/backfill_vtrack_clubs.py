#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, re, sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

PACKAGE_NAME="02ce737d-b4f8-4bbb-92b2-1355681ff1e8_qbntr2denpnae"
TS_RE=re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")

def iso(s:str)->str:return datetime.strptime(s,"%Y-%m-%d %H:%M:%S.%f").isoformat(timespec="milliseconds")

def iter_json_blocks(path:Path):
    collecting=False;buf=[];depth=0;ts=None
    with path.open('r',encoding='utf-8',errors='replace') as f:
        for line in f:
            line=line.rstrip('\r\n')
            if not collecting:
                m=TS_RE.match(line)
                if m and ('[SEND]' in line or '[RECEIVE]' in line) and '{' in line:
                    collecting=True;ts=m.group('ts');first=line[line.find('{'):];buf=[first];depth=first.count('{')-first.count('}')
                    if depth!=0: continue
                else: continue
            else:
                buf.append(line);depth+=line.count('{')-line.count('}')
                if depth>0: continue
            raw='\n'.join(buf);collecting=False;buf=[];depth=0
            try:obj=json.loads(raw)
            except json.JSONDecodeError:continue
            yield iso(ts),obj

def main():
    ap=argparse.ArgumentParser(description='Backfill GSPro club/player state onto existing VTrack archive shots.')
    ap.add_argument('--db',type=Path,default=Path.home()/"Documents"/"VTrackArchive"/"vtrack_shots.sqlite3")
    ap.add_argument('--apply',action='store_true',help='Actually update the database. Without this flag, only report what would change.')
    a=ap.parse_args()
    local=os.environ.get('LOCALAPPDATA')
    if not local: raise SystemExit('LOCALAPPDATA is not set.')
    logs_root=Path(local)/'Packages'/PACKAGE_NAME/'LocalState'/'LAON PEOPLE'/'VTrackToolKit'/'AppLogs'
    logs=sorted(logs_root.rglob('GSProJsonClient_*.log'),key=lambda p:p.stat().st_mtime)
    if not logs: raise SystemExit(f'No GSPro logs found under {logs_root}')
    if not a.db.is_file(): raise SystemExit(f'Database not found: {a.db}')
    mapping:dict[str,dict[str,Any]]={}
    for path in logs:
        player:dict[str,Any]={}
        for ts,obj in iter_json_blocks(path):
            p=obj.get('Player')
            if isinstance(p,dict):
                for k in ('Club','Handed','DistanceToTarget','Surface'):
                    if k in p and p[k] is not None: player[k]=p[k]
            opts=obj.get('ShotDataOptions') or {}
            if opts.get('ContainsBallData') is True and obj.get('BallData') and player.get('Club'):
                mapping[ts]=dict(player)
    cx=sqlite3.connect(a.db)
    cols={r[1] for r in cx.execute('PRAGMA table_info(shots)')}
    add={'club':'TEXT','player_handed':'TEXT','distance_to_target':'REAL','surface':'TEXT','player_state_time':'TEXT'}
    if a.apply:
        for col,t in add.items():
            if col not in cols: cx.execute(f'ALTER TABLE shots ADD COLUMN {col} {t}')
        cx.commit();cols|=add.keys()
    elif 'club' not in cols:
        print('NOTE: club columns are not in the DB yet; collector v4 will add them. Use --apply to let this tool add them now.')
    matched=0;would_update=0
    for ts,p in mapping.items():
        row=cx.execute('SELECT id'+(',club' if 'club' in cols else '')+' FROM shots WHERE shot_time=?',(ts,)).fetchone()
        if not row: continue
        matched+=1
        current=row[1] if len(row)>1 else None
        if not current:
            would_update+=1
            if a.apply:
                cx.execute('UPDATE shots SET club=?,player_handed=?,distance_to_target=?,surface=?,player_state_time=? WHERE id=?',
                           (p.get('Club'),p.get('Handed'),p.get('DistanceToTarget'),p.get('Surface'),ts,row[0]))
    if a.apply: cx.commit()
    cx.close()
    print(f'GSPro shot packets with cached club: {len(mapping)}')
    print(f'Exact database timestamp matches:    {matched}')
    print(f'{"Updated" if a.apply else "Would update"} previously blank clubs: {would_update}')
    if not a.apply: print('Dry run only. Re-run with --apply if the counts look reasonable.')

if __name__=='__main__':main()
