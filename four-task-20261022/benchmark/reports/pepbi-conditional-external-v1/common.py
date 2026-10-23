"""Utilities for the 27-candidate conditional fixed-weight evaluation."""
import csv
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
DATA=ROOT/'data/pepbi-external-audit-20261023'
RUN=ROOT/'runs/pepbi-conditional-external-v1'
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    return h.hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf-8')
def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))
def csvwrite(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
