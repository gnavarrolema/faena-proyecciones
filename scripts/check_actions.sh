#!/bin/bash
curl -s "https://api.github.com/repos/gnavarrolema/faena-proyecciones/actions/runs?per_page=5" \
  -H "Accept: application/vnd.github+json" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
runs = data.get('workflow_runs', [])
if not runs:
    print('No runs found or repo is private (need auth)')
    sys.exit(0)
for r in runs[:5]:
    msg = r['head_commit']['message'].split('\n')[0][:55]
    print(f\"{r['created_at']}  [{r['status']:10}] [{str(r['conclusion']):10}]  {r['name']:4}  {msg}\")
"
