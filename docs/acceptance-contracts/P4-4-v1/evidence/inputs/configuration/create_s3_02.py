# -*- coding: utf-8 -*-
# create_s3_02: 权限已授予后的正式创建流程（P4-4 S3 凭据）
# 步骤:
#   1. 只读确认两个 R2 桶存在
#   2. 创建两套账户自有 token（各自严格限单桶, Item Read + Item Write）
#   3. GET 回读校验 scope 精确匹配
#   4. 用派生的 S3 凭据做真实 SigV4 ListObjectsV2 实测
#   5. 值写入 private/（仅当前用户 ACL），公共记录不含任何 secret 值
# 秘密值绝不 print。
import json, pathlib, hashlib, hmac, datetime, urllib.request, urllib.error, urllib.parse
from getpass import getuser

BASE = pathlib.Path(".cache/p44-cred-20261019")
PRIV = BASE / "private"
PRIV.mkdir(parents=True, exist_ok=True)

cfg = json.loads(pathlib.Path(
    r"app/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json"
).read_text(encoding="utf-8"))
token = cfg["secrets"]["CLOUDFLARE_API_TOKEN"]
acc = cfg["secrets"]["CLOUDFLARE_ACCOUNT_ID"]

AK_WRITE = "2efd5506f9c8494dacb1fa10a3e7d5b6"   # Workers R2 Storage Bucket Item Write
AK_READ = "6a018a9f2fc74eb6b293b0c548f38b39"    # Workers R2 Storage Bucket Item Read

JOBS = [
    {
        "key": "production",
        "name": "e-track-firmware-production-s3-ci-20261019",
        "bucket": "e-track-firmware-production-releases",
    },
    {
        "key": "rehearsal",
        "name": "e-track-firmware-rehearsal-s3-ci-20261019",
        "bucket": "e-track-firmware-p41-test-releases",
    },
]

def call(method, url, body=None):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", "Bearer " + token)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}

def sigv4_headers(akid, secret, host, path, query):
    t = datetime.datetime.utcnow()
    amzdate = t.strftime("%Y%m%dT%H%M%SZ")
    datestamp = t.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(b"").hexdigest()
    cq = "&".join(
        urllib.parse.quote(k, safe="") + "=" + urllib.parse.quote(str(v), safe="")
        for k, v in sorted(query.items()))
    ch = "host:" + host + "\nx-amz-content-sha256:" + payload_hash + "\nx-amz-date:" + amzdate + "\n"
    sh = "host;x-amz-content-sha256;x-amz-date"
    cr = "GET\n" + path + "\n" + cq + "\n" + ch + "\n" + sh + "\n" + payload_hash
    scope = datestamp + "/auto/s3/aws4_request"
    sts = "AWS4-HMAC-SHA256\n" + amzdate + "\n" + scope + "\n" + hashlib.sha256(cr.encode()).hexdigest()
    def hh(key, msg):
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()
    k = hh(("AWS4" + secret).encode(), datestamp)
    k = hh(k, "auto"); k = hh(k, "s3"); k = hh(k, "aws4_request")
    sig = hmac.new(k, sts.encode(), hashlib.sha256).hexdigest()
    return {
        "Authorization": "AWS4-HMAC-SHA256 Credential=" + akid + "/" + scope
            + ", SignedHeaders=" + sh + ", Signature=" + sig,
        "x-amz-date": amzdate,
        "x-amz-content-sha256": payload_hash,
    }

def s3_test(akid, secret, bucket):
    host = acc + ".r2.cloudflarestorage.com"
    path = "/" + bucket
    hdrs = sigv4_headers(akid, secret, host, path, {"list-type": "2", "max-keys": 1})
    req = urllib.request.Request("https://" + host + path + "?list-type=2&max-keys=1")
    for k, v in hdrs.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        try:
            e.read()
        except Exception:
            pass
        return e.code

out_pub = {"createdAt": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
           "account_id": acc, "jobs": {}}
out_priv = {"createdAt": out_pub["createdAt"], "account_id": acc, "credentials": {}}

# ---- 1. 桶存在性（只读） ----
s, r = call("GET", "https://api.cloudflare.com/client/v4/accounts/" + acc + "/r2/buckets?per_page=100")
names = set()
if isinstance(r, dict) and r.get("success"):
    names = {b.get("name") for b in ((r.get("result") or {}).get("buckets") or [])}
out_pub["buckets_seen"] = sorted(names)
print("[1] R2 buckets visible:", len(names))
for j in JOBS:
    mark = "OK" if j["bucket"] in names else "MISSING"
    print("    ", j["bucket"], "->", mark)
    if mark == "MISSING":
        raise SystemExit("bucket missing: " + j["bucket"])

# ---- 2. 创建 + 3. 回读校验 + 4. S3 实测 ----
for j in JOBS:
    res_name = "com.cloudflare.edge.r2.bucket." + acc + "_default_" + j["bucket"]
    body = {
        "name": j["name"],
        "policies": [{
            "effect": "allow",
            "resources": {res_name: "*"},
            "permission_groups": [{"id": AK_READ}, {"id": AK_WRITE}],
        }],
    }
    s, r = call("POST", "https://api.cloudflare.com/client/v4/accounts/" + acc + "/tokens", body=body)
    print("[2]", j["key"], "create: HTTP", s)
    if s not in (200, 201):
        errs = [(e.get("code"), (e.get("message") or "")[:100]) for e in (r.get("errors") or [])] if isinstance(r, dict) else []
        print("    FAILED:", errs)
        raise SystemExit("create failed for " + j["key"])
    res = r["result"]
    tid, tval = res["id"], res["value"]

    s2, r2 = call("GET", "https://api.cloudflare.com/client/v4/accounts/" + acc + "/tokens/" + tid)
    pol = (r2.get("result") or {}).get("policies") or []
    got_res = set()
    got_pg = set()
    for p in pol:
        for rk in (p.get("resources") or {}):
            got_res.add(rk)
        for pg in (p.get("permission_groups") or []):
            got_pg.add(pg.get("id"))
    status = (r2.get("result") or {}).get("status")
    scope_ok = (got_res == {res_name} and got_pg == {AK_READ, AK_WRITE} and status == "active")
    print("[3]", j["key"], "scope check:", "PASS" if scope_ok else "FAIL",
          "| resources:", sorted(got_res), "| groups:", sorted(g for g in got_pg if g),
          "| status:", status)

    akid = tid
    secret = hashlib.sha256(tval.encode()).hexdigest()
    code = s3_test(akid, secret, j["bucket"])
    print("[4]", j["key"], "S3 SigV4 ListObjectsV2: HTTP", code)

    out_priv["credentials"][j["key"]] = {
        "token_id_access_key_id": akid,
        "token_value": tval,
        "secret_access_key_sha256": secret,
        "bucket": j["bucket"],
        "resource_scope": res_name,
        "gh_env": "firmware-production" if j["key"] == "production" else "firmware-rehearsal",
    }
    out_pub["jobs"][j["key"]] = {
        "http_create": s, "token_id": tid, "name": j["name"],
        "bucket": j["bucket"], "resource_scope": res_name,
        "scope_check": "PASS" if scope_ok else "FAIL",
        "s3_sigv4_listobjects_http": code,
        "value_masked": (tval[:6] + "..." + str(len(tval)) + "chars"),
        "gh_env": "firmware-production" if j["key"] == "production" else "firmware-rehearsal",
                    "gh_secret_names": ["TRACE_R2_ACCESS_KEY_ID", "TRACE_R2_SECRET_ACCESS_KEY"]
            if j["key"] == "production" else
            ["FIRMWARE_REHEARSAL_TRACE_R2_ACCESS_KEY_ID", "FIRMWARE_REHEARSAL_TRACE_R2_SECRET_ACCESS_KEY"],
    }

# ---- 5. 落盘 ----
(PRIV / "p44-s3-credentials-20261019.json").write_text(
    json.dumps(out_priv, ensure_ascii=False, indent=2), encoding="utf-8")
(BASE / "create-s3-02.json").write_text(
    json.dumps(out_pub, ensure_ascii=False, indent=2), encoding="utf-8")
# gh 写入用的平铺值文件（不打印）
c = out_priv["credentials"]
(PRIV / "production_access_key_id.txt").write_text(c["production"]["token_id_access_key_id"], encoding="utf-8")
(PRIV / "production_secret_access_key.txt").write_text(c["production"]["secret_access_key_sha256"], encoding="utf-8")
(PRIV / "rehearsal_access_key_id.txt").write_text(c["rehearsal"]["token_id_access_key_id"], encoding="utf-8")
(PRIV / "rehearsal_secret_access_key.txt").write_text(c["rehearsal"]["secret_access_key_sha256"], encoding="utf-8")
print("[5] saved private: " + str(PRIV / "p44-s3-credentials-20261019.json"))
print("    saved public : " + str(BASE / "create-s3-02.json"))
