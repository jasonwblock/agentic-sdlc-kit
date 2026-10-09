#!/usr/bin/env python3
"""One front door for issues, whatever holds them. Prints normalized JSON.

  issue.py get <ref>                                   one issue, with comments
  issue.py list <source> [--team|--project KEY] [--state NAME] [--label NAME] [--limit N]
  issue.py comment <ref> <body | ->                    add a comment ("-" reads stdin)
  issue.py status <ref> <state name>                   move it (Linear state, Jira transition, GitHub open/closed)

A <ref> can be:
  Linear   ENG-123 · https://linear.app/<org>/issue/ENG-123/...            needs LINEAR_API_KEY
  Jira     ENG-123 · https://<site>/browse/ENG-123                         needs JIRA_BASE_URL plus
                                                                           JIRA_EMAIL + JIRA_API_TOKEN (Cloud) or JIRA_PAT (Server/DC)
  GitHub   #123 · owner/repo#123 · https://github.com/owner/repo/issues/123   uses the gh CLI
  Local    path/to/file.json#ID · .md#ID · .csv#ID · .db/.sqlite#ID         read-only
A prefix forces the source: linear:ENG-1, jira:ENG-1, github:#12, file:TASKS.md#T-4.
A bare KEY-123 or 123 uses the "Tracker:" line in CLAUDE.md (linear | jira | github | file:<path>).
<source> for list: linear, jira, github, or file:<path>.

Every issue comes back as:
  {source, id, title, body, url, state, labels, comments[{author, created, body}],
   parent, children[{id, title, state}], branch, writable}
"""
import base64
import csv
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

KEY_RE = r"([A-Za-z][A-Za-z0-9_]*)-(\d+)"


def die(msg, code=1):
    sys.stderr.write(msg.rstrip() + "\n")
    sys.exit(code)


def out(obj):
    print(json.dumps(obj, indent=2, default=str))


def issue(source, id, title, body="", url=None, state=None, labels=(), comments=(), parent=None,
          children=(), branch=None, writable=True):
    return {"source": source, "id": id, "title": title, "body": body or "", "url": url, "state": state,
            "labels": list(labels), "comments": list(comments), "parent": parent, "children": list(children),
            "branch": branch, "writable": writable}


def http_json(method, url, headers, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", "Accept": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        die(f"{method} {url} -> HTTP {e.code}: {e.read().decode(errors='replace')[:500]}")
    except urllib.error.URLError as e:
        die(f"{method} {url} -> {e.reason}")


# ---------------------------------------------------------------- resolving a ref

def project_dir():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def configured_tracker():
    path = os.path.join(project_dir(), "CLAUDE.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^\s*[-*]?\s*Tracker:\s*`?([^`\s]+)`?", line)
                if m:
                    value = m.group(1)
                    # "none", or a template placeholder like <linear or {{TRACKER}}, means not configured
                    return None if value.lower() == "none" or value[0] in "<{" else value
    return None


def resolve(ref):
    """-> (source, locator). locator: 'KEY-N' (linear/jira), (repo|None, n) (github), (path, id|None) (file)."""
    ref = ref.strip()
    m = re.match(r"^(linear|jira|github|file):(.*)$", ref)
    if m:
        forced, rest = m.groups()
        return locate(forced, rest)
    if re.match(r"^https?://", ref):
        u = urllib.parse.urlparse(ref)
        if u.netloc.endswith("linear.app"):
            m = re.search(r"/issue/" + KEY_RE, u.path)
            if m:
                return "linear", f"{m.group(1).upper()}-{m.group(2)}"
        if u.netloc.endswith("github.com"):
            m = re.match(r"^/([^/]+/[^/]+)/(?:issues|pull)/(\d+)", u.path)
            if m:
                return "github", (m.group(1), int(m.group(2)))
        m = re.search(r"/browse/" + KEY_RE, u.path) or re.search(r"selectedIssue=" + KEY_RE, u.query)
        if m:
            return "jira", f"{m.group(1).upper()}-{m.group(2)}"
        die(f"Can't tell which tracker this URL belongs to: {ref}")
    m = re.match(r"^(?:([\w.-]+/[\w.-]+))?#(\d+)$", ref)
    if m:
        return "github", (m.group(1), int(m.group(2)))
    path, _, frag = ref.partition("#")
    if os.path.isfile(path):
        return "file", (path, frag or None)
    tracker = configured_tracker()
    if tracker:
        if tracker.startswith("file:"):
            return "file", (tracker[5:], ref)
        return locate(tracker, ref)
    if re.fullmatch(KEY_RE, ref):
        have_linear = bool(os.environ.get("LINEAR_API_KEY"))
        have_jira = bool(os.environ.get("JIRA_BASE_URL"))
        if have_linear != have_jira:
            return ("linear" if have_linear else "jira"), ref.upper()
        die(f"'{ref}' could be Linear or Jira. Add 'Tracker: linear' (or jira) to CLAUDE.md, or pass the issue's URL.")
    die(f"Not an issue reference I recognise: {ref}\n\n" + __doc__)


def locate(source, rest):
    rest = rest.strip()
    if source in ("linear", "jira"):
        m = re.search(KEY_RE, rest)
        if not m:
            die(f"Not a {source} issue key: {rest}")
        return source, f"{m.group(1).upper()}-{m.group(2)}"
    if source == "github":
        m = re.match(r"^(?:([\w.-]+/[\w.-]+))?#?(\d+)$", rest)
        if not m:
            die(f"Not a GitHub issue: {rest}")
        return "github", (m.group(1), int(m.group(2)))
    if source == "file":
        path, _, frag = rest.partition("#")
        return "file", (path, frag or None)
    die(f"Unknown tracker '{source}' (linear | jira | github | file:<path>)")


# ---------------------------------------------------------------- Linear

LINEAR_FIELDS = """id identifier title description url branchName state { name type } team { id key }
  labels { nodes { name } } parent { identifier title } children { nodes { identifier title state { name } } }
  attachments { nodes { title url } }"""


def linear_gql(query, variables=None):
    token = os.environ.get("LINEAR_API_KEY")
    if not token:
        die("LINEAR_API_KEY is not set (Linear > Settings > Security & access > personal API keys).")
    data = http_json("POST", "https://api.linear.app/graphql", {"Authorization": token},
                     {"query": query, "variables": variables or {}})
    if data.get("errors"):
        die("Linear API error: " + "; ".join(e.get("message", "?") for e in data["errors"]))
    return data["data"]


def linear_find(key, fields=LINEAR_FIELDS):
    team, num = key.rsplit("-", 1)
    q = "query($k:String!,$n:Float!){ issues(filter:{ team:{ key:{ eq:$k } }, number:{ eq:$n } }){ nodes{ %s } } }" % fields
    nodes = linear_gql(q, {"k": team, "n": float(num)})["issues"]["nodes"]
    if not nodes:
        die(f"No Linear issue {key} (or the API key can't see it).")
    return nodes[0]


def linear_get(key):
    n = linear_find(key)
    comments = linear_gql("query($id:String!){ issue(id:$id){ comments(first:50){ nodes{ body createdAt user{ name } } } } }",
                          {"id": n["id"]})["issue"]["comments"]["nodes"]
    body = n["description"] or ""
    if n["attachments"]["nodes"]:
        body += "\n\nAttachments:\n" + "\n".join(f"- {a['title']}: {a['url']}" for a in n["attachments"]["nodes"])
    return issue("linear", n["identifier"], n["title"], body, n["url"], n["state"]["name"],
                 [l["name"] for l in n["labels"]["nodes"]],
                 sorted(({"author": (c["user"] or {}).get("name"), "created": c["createdAt"], "body": c["body"]} for c in comments),
                        key=lambda c: c["created"]),
                 (n["parent"] or {}).get("identifier"),
                 [{"id": c["identifier"], "title": c["title"], "state": c["state"]["name"]} for c in n["children"]["nodes"]],
                 n["branchName"])


def linear_list(team, state, label, limit):
    if not team:
        die("list linear needs --team KEY")
    f = {"team": {"key": {"eq": team.upper()}}}
    f["state"] = {"name": {"eqIgnoreCase": state}} if state else {"type": {"nin": ["completed", "canceled"]}}
    if label:
        f["labels"] = {"name": {"eqIgnoreCase": label}}
    q = "query($f:IssueFilter,$n:Int){ issues(filter:$f, first:$n, orderBy:createdAt){ nodes{ identifier title url state{ name } labels{ nodes{ name } } } } }"
    return [{"source": "linear", "id": n["identifier"], "title": n["title"], "url": n["url"], "state": n["state"]["name"],
             "labels": [l["name"] for l in n["labels"]["nodes"]]}
            for n in linear_gql(q, {"f": f, "n": limit})["issues"]["nodes"]]


def linear_comment(key, body):
    n = linear_find(key, "id identifier")
    r = linear_gql("mutation($i:CommentCreateInput!){ commentCreate(input:$i){ success comment{ url } } }",
                   {"i": {"issueId": n["id"], "body": body}})["commentCreate"]
    return {"id": key, "success": r["success"], "url": (r.get("comment") or {}).get("url")}


def linear_status(key, name):
    n = linear_find(key, "id identifier team { id } state { name }")
    states = linear_gql("query($id:String!){ team(id:$id){ states{ nodes{ id name } } } }", {"id": n["team"]["id"]})["team"]["states"]["nodes"]
    match = [s for s in states if s["name"].lower() == name.lower()]
    if not match:
        die(f"No state '{name}'. States: " + ", ".join(s["name"] for s in states))
    r = linear_gql("mutation($id:String!,$i:IssueUpdateInput!){ issueUpdate(id:$id, input:$i){ success } }",
                   {"id": n["id"], "i": {"stateId": match[0]["id"]}})["issueUpdate"]
    return {"id": key, "from": n["state"]["name"], "to": match[0]["name"], "success": r["success"]}


# ---------------------------------------------------------------- Jira

def jira_base():
    base = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
    if not base:
        die("JIRA_BASE_URL is not set (e.g. https://yourco.atlassian.net).")
    return base


def jira_headers():
    if os.environ.get("JIRA_PAT"):
        return {"Authorization": "Bearer " + os.environ["JIRA_PAT"]}
    email, token = os.environ.get("JIRA_EMAIL"), os.environ.get("JIRA_API_TOKEN")
    if not (email and token):
        die("Set JIRA_EMAIL and JIRA_API_TOKEN (Jira Cloud) or JIRA_PAT (Server/Data Center).")
    return {"Authorization": "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()}


def jira_get(key):
    fields = "summary,description,status,labels,issuetype,parent,subtasks,comment,attachment"
    d = http_json("GET", f"{jira_base()}/rest/api/2/issue/{key}?fields={fields}", jira_headers())
    f = d["fields"]
    body = f.get("description") or ""
    if f.get("attachment"):
        body += "\n\nAttachments:\n" + "\n".join(f"- {a['filename']}: {a['content']}" for a in f["attachment"])
    labels = list(f.get("labels") or [])
    if f.get("issuetype"):
        labels.insert(0, f["issuetype"]["name"])
    comments = [{"author": (c.get("author") or {}).get("displayName"), "created": c.get("created"), "body": c.get("body")}
                for c in (f.get("comment") or {}).get("comments", [])]
    return issue("jira", d["key"], f.get("summary"), body, f"{jira_base()}/browse/{d['key']}",
                 (f.get("status") or {}).get("name"), labels, comments, (f.get("parent") or {}).get("key"),
                 [{"id": s["key"], "title": s["fields"]["summary"], "state": s["fields"]["status"]["name"]} for s in f.get("subtasks") or []])


def jira_list(project, state, label, limit):
    if not project:
        die("list jira needs --project KEY")
    jql = f'project = "{project}"'
    jql += f' AND status = "{state}"' if state else " AND statusCategory != Done"
    if label:
        jql += f' AND labels = "{label}"'
    jql += " ORDER BY created DESC"
    qs = urllib.parse.urlencode({"jql": jql, "maxResults": limit, "fields": "summary,status,labels"})
    try:  # Cloud's current search; Server/DC only has the v2 one
        d = http_json("GET", f"{jira_base()}/rest/api/3/search/jql?{qs}", jira_headers())
    except SystemExit:
        d = http_json("GET", f"{jira_base()}/rest/api/2/search?{qs}", jira_headers())
    return [{"source": "jira", "id": i["key"], "title": i["fields"]["summary"], "url": f"{jira_base()}/browse/{i['key']}",
             "state": i["fields"]["status"]["name"], "labels": i["fields"].get("labels") or []} for i in d.get("issues", [])]


def jira_comment(key, body):
    d = http_json("POST", f"{jira_base()}/rest/api/2/issue/{key}/comment", jira_headers(), {"body": body})
    return {"id": key, "success": True, "url": f"{jira_base()}/browse/{key}?focusedCommentId={d.get('id')}"}


def jira_status(key, name):
    ts = http_json("GET", f"{jira_base()}/rest/api/2/issue/{key}/transitions", jira_headers())["transitions"]
    match = [t for t in ts if name.lower() in (t["name"].lower(), t["to"]["name"].lower())]
    if not match:
        die(f"No transition to '{name}'. Available: " + ", ".join(f"{t['name']} -> {t['to']['name']}" for t in ts))
    http_json("POST", f"{jira_base()}/rest/api/2/issue/{key}/transitions", jira_headers(), {"transition": {"id": match[0]["id"]}})
    return {"id": key, "to": match[0]["to"]["name"], "success": True}


# ---------------------------------------------------------------- GitHub (gh CLI)

def gh(*args):
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        die("The gh CLI isn't installed.")
    if r.returncode != 0:
        die(f"gh {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def gh_repo(repo):
    return ["--repo", repo] if repo else []


def github_get(loc):
    repo, n = loc
    d = json.loads(gh("issue", "view", str(n), *gh_repo(repo), "--json", "number,title,body,url,state,labels,comments"))
    return issue("github", f"#{d['number']}" if not repo else f"{repo}#{d['number']}", d["title"], d["body"], d["url"], d["state"],
                 [l["name"] for l in d["labels"]],
                 [{"author": (c.get("author") or {}).get("login"), "created": c.get("createdAt"), "body": c.get("body")} for c in d["comments"]])


def github_list(repo, state, label, limit):
    args = ["issue", "list", *gh_repo(repo), "--limit", str(limit), "--json", "number,title,url,state,labels"]
    if label:
        args += ["--label", label]
    if state and state.lower() in ("open", "closed", "all"):
        args += ["--state", state.lower()]
    return [{"source": "github", "id": f"#{i['number']}", "title": i["title"], "url": i["url"], "state": i["state"],
             "labels": [l["name"] for l in i["labels"]]} for i in json.loads(gh(*args))]


def github_comment(loc, body):
    repo, n = loc
    url = gh("issue", "comment", str(n), *gh_repo(repo), "--body", body).strip()
    return {"id": f"#{n}", "success": True, "url": url}


def github_status(loc, name):
    repo, n = loc
    if name.lower() in ("closed", "close", "done"):
        gh("issue", "close", str(n), *gh_repo(repo))
    elif name.lower() in ("open", "reopen", "reopened"):
        gh("issue", "reopen", str(n), *gh_repo(repo))
    else:
        die(f"GitHub issues are only open or closed; '{name}' isn't supported. Skip the status update.", 3)
    return {"id": f"#{n}", "to": name.lower(), "success": True}


# ---------------------------------------------------------------- local files (read-only)

ID_KEYS = ("id", "key", "identifier", "number", "ref", "issue_id", "task_id")
TITLE_KEYS = ("title", "summary", "name", "subject")
BODY_KEYS = ("description", "body", "details", "notes", "content", "text")
STATE_KEYS = ("status", "state")
LABEL_KEYS = ("labels", "tags", "type")


def pick(row, keys):
    lower = {str(k).lower(): v for k, v in row.items()}
    for k in keys:
        if lower.get(k) not in (None, ""):
            return lower[k]
    return None


def row_issue(row, path):
    labels = pick(row, LABEL_KEYS)
    if isinstance(labels, str):
        labels = [s.strip() for s in re.split(r"[,;]", labels) if s.strip()]
    extra = {k: v for k, v in row.items()
             if str(k).lower() not in ID_KEYS + TITLE_KEYS + BODY_KEYS + STATE_KEYS + LABEL_KEYS and v not in (None, "", [], {})}
    body = pick(row, BODY_KEYS) or ""
    if extra:
        body = (str(body) + "\n\nOther fields:\n" + json.dumps(extra, indent=2, default=str)).strip()
    return issue("file", str(pick(row, ID_KEYS)), pick(row, TITLE_KEYS), str(body), path, pick(row, STATE_KEYS),
                 labels or [], writable=False)


def json_rows(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        for k in ("issues", "items", "tasks", "tickets", "backlog", "stories"):
            if isinstance(data.get(k), list):
                return data[k]
        lists = [v for v in data.values() if isinstance(v, list) and v and isinstance(v[0], dict)]
        if lists:
            return lists[0]
        if all(isinstance(v, dict) for v in data.values()):  # {"BL-1": {...}, ...}
            return [{"id": k, **v} for k, v in data.items()]
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    die(f"Can't find a list of issues in {path}.")


def csv_rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sqlite_rows(path):
    con = sqlite3.connect(f"file:{os.path.abspath(path)}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    def score(t):
        cols = {r[1].lower() for r in con.execute(f'PRAGMA table_info("{t}")')}
        return (t.lower() in ("issues", "tasks", "tickets", "items", "backlog"), bool(cols & set(ID_KEYS)), bool(cols & set(TITLE_KEYS)))
    best = max(tables, key=score, default=None)
    if not best or not all(score(best)[1:]):
        die(f"No table in {path} looks like issues (needs an id and a title column). Tables: {', '.join(tables)}")
    return [dict(r) for r in con.execute(f'SELECT * FROM "{best}"')]


def md_issues(path):
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    found, i = [], 0
    while i < len(lines):
        line = lines[i]
        h = re.match(r"^(#{1,6})\s+(.*)$", line)
        c = re.match(r"^\s*[-*]\s+\[( |x|X)\]\s+(.*)$", line)
        idm = re.search(r"\b" + KEY_RE + r"\b|#(\d+)\b", (h or c).group(2)) if (h or c) else None
        if h and idm:
            level, j = len(h.group(1)), i + 1
            while j < len(lines) and not re.match(r"^#{1,%d}\s" % level, lines[j]):
                j += 1
            body = "\n".join(lines[i + 1:j]).strip()
            st = re.search(r"^\s*[-*]?\s*\**Status\**:\s*(.+)$", body, re.M | re.I)
            found.append((idm.group(0), h.group(2), body, st.group(1).strip() if st else None))
            i += 1  # keep scanning inside the section: nested headings and checklist items are issues too
            continue
        if c and idm:
            found.append((idm.group(0), c.group(2), "", "done" if c.group(1).lower() == "x" else "open"))
        i += 1
    return [issue("file", id_, re.sub(r"^[\s:–—-]+|[\s:–—-]+$", "", title.replace(id_, "", 1)) or title, body, path, st, writable=False)
            for id_, title, body, st in found]


def file_issues(path):
    if not os.path.isfile(path):
        die(f"No such file: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        return [row_issue(r, path) for r in json_rows(path)]
    if ext == ".csv":
        return [row_issue(r, path) for r in csv_rows(path)]
    if ext in (".db", ".sqlite", ".sqlite3"):
        return [row_issue(r, path) for r in sqlite_rows(path)]
    if ext in (".md", ".markdown", ".txt"):
        return md_issues(path)
    die(f"Unsupported file type '{ext}'. Read the file yourself and normalize the issue to this script's JSON shape.")


def file_get(loc):
    path, id_ = loc
    if not id_:
        die("Give the issue's id after '#', e.g. TASKS.md#T-4.")
    for it in file_issues(path):
        if it["id"] and it["id"].lower().lstrip("#") == id_.lower().lstrip("#"):
            return it
    die(f"No issue '{id_}' in {path}.")


def file_list(path, state, label, limit):
    rows = file_issues(path)
    if state:
        rows = [r for r in rows if str(r["state"] or "").lower() == state.lower()]
    else:
        rows = [r for r in rows if str(r["state"] or "").lower() not in ("done", "closed", "completed", "canceled", "cancelled", "resolved")]
    if label:
        rows = [r for r in rows if label.lower() in (str(l).lower() for l in r["labels"])]
    return [{k: r[k] for k in ("source", "id", "title", "url", "state", "labels")} for r in rows[:limit]]


# ---------------------------------------------------------------- commands

def cmd_get(ref):
    source, loc = resolve(ref)
    out({"linear": linear_get, "jira": jira_get, "github": github_get, "file": file_get}[source](loc))


def cmd_list(args):
    if not args:
        die("list needs a source: linear, jira, github, or file:<path>")
    source, rest = args[0], args[1:]
    opts = {"--team": None, "--project": None, "--repo": None, "--state": None, "--label": None, "--limit": "50"}
    it = iter(rest)
    for a in it:
        if a not in opts:
            die(f"Unknown option {a}")
        opts[a] = next(it, None)
    limit = int(opts["--limit"])
    if source == "linear":
        out(linear_list(opts["--team"] or opts["--project"], opts["--state"], opts["--label"], limit))
    elif source == "jira":
        out(jira_list(opts["--project"] or opts["--team"], opts["--state"], opts["--label"], limit))
    elif source == "github":
        out(github_list(opts["--repo"], opts["--state"], opts["--label"], limit))
    elif source.startswith("file:"):
        out(file_list(source[5:], opts["--state"], opts["--label"], limit))
    else:
        die(f"Unknown source '{source}'")


def cmd_write(kind, ref, value):
    source, loc = resolve(ref)
    if source == "file":
        die("Local issue files are read-only here. If the file has a status or notes field, edit it yourself; "
            "never write to a database without asking the user.", 3)
    if kind == "comment":
        if value == "-":
            value = sys.stdin.read()
        if not value.strip():
            die("Empty comment.")
        out({"linear": linear_comment, "jira": jira_comment, "github": github_comment}[source](loc, value))
    else:
        out({"linear": linear_status, "jira": jira_status, "github": github_status}[source](loc, value))


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        die(__doc__, 0 if argv else 2)
    cmd, rest = argv[0], argv[1:]
    if cmd == "get" and len(rest) == 1:
        cmd_get(rest[0])
    elif cmd == "list":
        cmd_list(rest)
    elif cmd in ("comment", "status") and len(rest) == 2:
        cmd_write(cmd, rest[0], rest[1])
    else:
        die(__doc__, 2)


if __name__ == "__main__":
    main(sys.argv[1:])
