#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""増えた求人・終わった求人を、その日のうちにGoogleへ知らせる（Indexing API）。

使い方: python notify.py diff.json
鍵ファイルは使わず、GitHubの自動実行だけに許可した「鍵なし」のつなぎ方で認証する。失敗しても公開は止めない。
"""
import os, sys, json

LIMIT = 180  # Googleの初期の上限は1日200件。余裕を見て180件まで

def main():
    diff = json.load(open(sys.argv[1], encoding="utf-8"))
    print("増えた求人 %d件 ／ 終わった求人 %d件" % (len(diff["added"]), len(diff["removed"])))
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("Googleとのつなぎ込みが未設定なので、通知はしません。")
        return
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/indexing"])
    s = AuthorizedSession(creds)
    # 終わった求人を先に知らせる（検索に残り続けるのを防ぐほうが大事）
    items = [(u, "URL_DELETED") for u in diff["removed"]] + [(u, "URL_UPDATED") for u in diff["added"]]
    if not items and diff.get("sample"):  # 増減がない日は、つながっているかの確認として1件だけ送る
        items = [(diff["sample"], "URL_UPDATED")]
        print("増減がないので、確認用に1件だけ送ります。")
    ok = ng = 0
    for url, kind in items[:LIMIT]:
        r = s.post("https://indexing.googleapis.com/v3/urlNotifications:publish", json={"url": url, "type": kind})
        if r.status_code == 200:
            ok += 1
        else:
            ng += 1
            if ng <= 3:
                print("通知に失敗:", r.status_code, r.text[:200].replace("\n", " "))
            if r.status_code in (401, 403, 429):
                break
    print("Googleへ通知: 成功 %d件 ／ 失敗 %d件 ／ 今日は送らなかった分 %d件" % (ok, ng, max(0, len(items) - ok - ng)))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 通知の失敗で公開を止めない
        print("通知でエラー:", type(e).__name__, str(e)[:200])
