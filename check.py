#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Googleに載ったかどうかを毎朝たしかめて、結果を site/keisai.html と site/keisai.json に残す。

使い方: python check.py site
Search Console の情報を「鍵なし」のつなぎ方で読むだけ（何も書き換えない）。失敗しても公開は止めない。
"""
import os, sys, json, re, datetime, hashlib, html, urllib.request, urllib.parse

BASE = "https://s-wakamatsu-dotcom.github.io/"
SAMPLE = 40   # 1日に調べる求人ページの数（毎日ちがうページを見る）
KEEP = 120    # 残す日数
JST = datetime.timezone(datetime.timedelta(hours=9))


def load_history():
    try:
        with urllib.request.urlopen(BASE + "keisai.json", timeout=20) as r:
            return json.load(r)
    except Exception:
        return []


def job_urls(site):
    try:
        x = open(os.path.join(site, "sitemap.xml"), encoding="utf-8").read()
    except Exception:
        return []
    return [u for u in re.findall(r"<loc>([^<]+)</loc>", x) if "/job/" in u]


def measure(site, today):
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    s = AuthorizedSession(creds)
    enc = urllib.parse.quote(BASE, safe="")
    row = {"date": today.isoformat(), "errors": []}

    # 1) サイトマップ（Googleが求人の一覧を受け取ったか）
    r = s.get("https://www.googleapis.com/webmasters/v3/sites/%s/sitemaps/%s" % (enc, urllib.parse.quote(BASE + "sitemap.xml", safe="")))
    if r.status_code == 200:
        d = r.json()
        row["sitemap_read"] = d.get("lastDownloaded", "")[:10]
        row["sitemap_urls"] = sum(int(c.get("submitted", 0)) for c in d.get("contents", []))
        row["sitemap_errors"] = int(d.get("errors", 0))
    else:
        row["errors"].append("サイトマップ %d %s" % (r.status_code, r.text[:120].replace("\n", " ")))

    # 2) 検索に出た回数（直近28日。Google側の集計は2〜3日おくれる）
    body = {"startDate": (today - datetime.timedelta(days=28)).isoformat(), "endDate": today.isoformat()}
    q = "https://www.googleapis.com/webmasters/v3/sites/%s/searchAnalytics/query" % enc
    r = s.post(q, json=body)
    if r.status_code == 200:
        rows = r.json().get("rows", [])
        row["imp"] = int(sum(x.get("impressions", 0) for x in rows))
        row["clk"] = int(sum(x.get("clicks", 0) for x in rows))
    else:
        row["errors"].append("検索回数 %d %s" % (r.status_code, r.text[:120].replace("\n", " ")))
    r = s.post(q, json=dict(body, dimensions=["searchAppearance"]))
    if r.status_code == 200:
        job_imp = job_clk = 0
        for x in r.json().get("rows", []):
            if "JOB" in x["keys"][0].upper():
                job_imp += x.get("impressions", 0)
                job_clk += x.get("clicks", 0)
        row["job_imp"], row["job_clk"] = int(job_imp), int(job_clk)

    # 3) 求人ページを抜き取りで調べる（Googleに登録されたか／求人として読めているか）
    urls = job_urls(site)
    urls.sort(key=lambda u: hashlib.sha1((today.isoformat() + u).encode()).hexdigest())
    seen = idx = rich = bad = 0
    states = {}
    for u in urls[:SAMPLE]:
        r = s.post("https://searchconsole.googleapis.com/v1/urlInspection/index:inspect",
                   json={"inspectionUrl": u, "siteUrl": BASE, "languageCode": "ja"})
        if r.status_code != 200:
            row["errors"].append("ページ確認 %d %s" % (r.status_code, r.text[:120].replace("\n", " ")))
            break
        res = r.json().get("inspectionResult", {})
        seen += 1
        ix = res.get("indexStatusResult", {})
        st = ix.get("coverageState", "不明")
        states[st] = states.get(st, 0) + 1
        if ix.get("verdict") == "PASS":
            idx += 1
        rr = res.get("richResultsResult", {})
        if rr:
            if rr.get("verdict") == "PASS":
                rich += 1
            elif rr.get("verdict") == "FAIL":
                bad += 1
    row.update(sample=seen, indexed=idx, rich_ok=rich, rich_ng=bad, states=states, total=len(urls))
    return row


def verdict(row):
    if row.get("job_imp", 0) > 0:
        return "A", "求人検索の枠に出ています"
    if row.get("rich_ok", 0) > 0:
        return "B", "Googleに登録され、求人としても読めています（枠に出るのを待つ段階）"
    if row.get("indexed", 0) > 0 or row.get("imp", 0) > 0:
        return "C", "Googleに登録され始めました（求人の枠はまだ）"
    if row.get("sample"):
        return "D", "まだ載っていません（Googleが読みに来るのを待っている段階）"
    return "?", "確認できませんでした"


def page(hist):
    e = html.escape
    last = hist[-1]
    rows = []
    for h in reversed(hist):
        est = "-"
        if h.get("sample"):
            est = "約%d件" % round(h.get("total", 0) * h.get("indexed", 0) / h["sample"])
        rows.append("<tr><td>%s</td><td>%s</td><td>%s／%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            e(h["date"]), e(h.get("label", "")), h.get("indexed", "-"), h.get("sample", "-"), est,
            h.get("rich_ok", "-"), h.get("rich_ng", "-"),
            "%s回／%s回" % (h.get("job_imp", "-"), h.get("job_clk", "-")),
            "%s回／%s回" % (h.get("imp", "-"), h.get("clk", "-"))))
    st = "、".join("%s %d件" % (e(k), v) for k, v in sorted(last.get("states", {}).items(), key=lambda x: -x[1])) or "-"
    err = ""
    if last.get("errors"):
        err = "<p class=w>確認中に出たエラー：%s</p>" % e(" ／ ".join(last["errors"][:3]))
    return """<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Google掲載チェック</title>
<style>body{font-family:system-ui,sans-serif;max-width:980px;margin:24px auto;padding:0 16px;color:#222;line-height:1.7}
h1{font-size:20px}.v{font-size:22px;font-weight:700;padding:14px 16px;background:#f2f6ff;border-left:6px solid #2b6be4;margin:12px 0}
table{border-collapse:collapse;width:100%%;font-size:13px}th,td{border:1px solid #ddd;padding:6px 8px;text-align:left}th{background:#f5f5f5}
.w{color:#b00}.s{color:#666;font-size:13px}</style></head><body>
<h1>Google掲載チェック（毎朝自動で更新）</h1>
<div class=v>%s 時点：%s</div>
<p>抜き取りで調べた求人ページの状態：%s</p>%s
<p class=s>見かた：毎朝ちがう%d件の求人ページを抜き取ってGoogleに問い合わせています。「求人枠に出た回数」が1回以上になれば、Googleしごと検索に載った合図です。回数の集計はGoogle側で2〜3日おくれます。</p>
<table><tr><th>日付</th><th>判定</th><th>登録済み／調べた数</th><th>全体の見込み</th><th>求人として読めた</th><th>求人の書き方エラー</th><th>求人枠に出た回数／クリック</th><th>検索全体 出た回数／クリック</th></tr>
%s</table></body></html>""" % (e(last["date"]), e(last.get("label", "")), st, err, SAMPLE, "\n".join(rows))


def main():
    site = sys.argv[1]
    hist = load_history()
    today = datetime.datetime.now(JST).date()
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            row = measure(site, today)
        except Exception as ex:
            row = {"date": today.isoformat(), "errors": ["%s %s" % (type(ex).__name__, str(ex)[:150])]}
        row["grade"], row["label"] = verdict(row)
        hist = [h for h in hist if h.get("date") != row["date"]] + [row]
        print("掲載チェック:", row["label"])
        print(json.dumps({k: v for k, v in row.items() if k != "label"}, ensure_ascii=False))
        summ = os.environ.get("GITHUB_STEP_SUMMARY")
        if summ:
            with open(summ, "a", encoding="utf-8") as f:
                f.write("### Google掲載チェック\n%s：**%s**\n\n登録済み %s／%s件 ・ 求人枠に出た回数 %s回\n" % (
                    row["date"], row["label"], row.get("indexed", "-"), row.get("sample", "-"), row.get("job_imp", "-")))
    else:
        print("Googleとのつなぎ込みが未設定なので、掲載チェックはしません。")
    hist = hist[-KEEP:]
    with open(os.path.join(site, "keisai.json"), "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False)
    if hist:
        with open(os.path.join(site, "keisai.html"), "w", encoding="utf-8") as f:
            f.write(page(hist))


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:  # チェックの失敗で公開を止めない
        print("掲載チェックでエラー:", type(ex).__name__, str(ex)[:200])
