#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""京栄センター 寮付き求人サイトを作るプログラム。

使い方:
  python build.py sanitize raw.json data/jobs.json   # 元の案件一覧 → 公開してよい項目だけのデータ
  python build.py render  data/jobs.json site         # 公開用データ → サイト一式

raw.json は {"values": [[見出し行], [1行目], ...]} か、その行だけの配列。
元の案件一覧（派遣会社名・派遣先名・紹介料・応募条件を含む）は、この置き場所には置かない。
"""
import sys, os, re, json, html, hashlib, datetime, shutil, unicodedata, urllib.request

BASE = os.environ.get("SITE_BASE", "https://s-wakamatsu-dotcom.github.io/")
OUBO = "https://kyoei-ryo.netlify.app/oubo/"
LP = "https://kyoei-ryo.netlify.app/"
JST = datetime.timezone(datetime.timedelta(hours=9))
TODAY = datetime.datetime.now(JST).date()

COLS = ["agency", "name", "no", "pref", "addr", "job", "shift", "hourly", "monthly", "dorm", "dormfee",
        "age", "sex", "foreign", "tattoo", "couple", "holiday", "hours", "schedule", "bonus", "cond",
        "headcount", "fee", "feenote", "access"]

PREFS = ["北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県", "埼玉県",
         "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県",
         "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県",
         "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県", "熊本県", "大分県",
         "宮崎県", "鹿児島県", "沖縄県"]
SEIREI = {"札幌市", "仙台市", "さいたま市", "千葉市", "横浜市", "川崎市", "相模原市", "新潟市", "静岡市", "浜松市",
          "名古屋市", "京都市", "大阪市", "堺市", "神戸市", "岡山市", "広島市", "北九州市", "福岡市", "熊本市"}

# 載せない行（年齢・性別・国籍・健康・体格・社内向けの情報）
SENSITIVE = re.compile(
    r"歳|才(?![能覚])|年齢|年代|若手|若年|男性|女性|男女|女子|男子|主婦|主夫|外国|国籍|日本人|日本語|ネイティブ|タトゥー|"
    r"刺青|入れ墨|入墨|ＴＴ|TT[:：]|紹介料|マージン|手数料|ランク|営業所[:：]|お仕事No|マスタ|持病|既往|病歴|色弱|色覚|"
    r"アレルギ|てんかん|ヘルニア|腰痛|精神|喘息|ぜんそく|妊娠|身長|体重|ウエスト|ｳｴｽﾄ|BMI|視力|利き手|左利き|右利き|"
    r"制服[:：]|作業服上限|[0-9０-９]L(迄|まで)|派遣会社|派遣元|面接NG|NG[:：]|不可[:：]|担当[:：]|締切|〆切|"
    r"募集人数|充足|ステータス")
AGENCIES = ["フジアルテ", "平山", "ワールドインテック", "ワールド", "BREXA", "ブレクサ", "高木工業", "日本ケイテム", "ケイテム",
            "UTエイム", "ＵＴエイム", "NMS", "ＮＭＳ", "日本マニュファクチャリングサービス", "ウイルテック", "エヌエステック",
            "エヌエス", "ニッコー", "日研トータルソーシング", "日研", "ビート", "東洋ワーク", "DPT", "ジョブスル", "ライデル",
            "アウトソーシング", "テクノスマイル", "トーコー", "綜合キャリアオプション", "ランスタッド", "スタッフサービス"]
MAKERS = ["ロッテ", "トヨタ", "TOYOTA", "レクサス", "日産", "NISSAN", "ホンダ", "HONDA", "本田技研", "マツダ", "MAZDA", "スバル", "SUBARU",
          "スズキ", "SUZUKI", "ダイハツ", "三菱", "いすゞ", "いすず", "日野自動車", "UDトラックス", "ヤマハ", "カワサキ", "川崎重工",
          "デンソー", "DENSO", "アイシン", "AISIN", "豊田自動織機", "豊田合成", "トヨタ紡織", "ジェイテクト", "小糸製作所", "矢崎",
          "住友電装", "住友", "日立", "東芝", "パナソニック", "Panasonic", "ソニー", "SONY", "シャープ", "キヤノン", "Canon", "ニコン",
          "リコー", "エプソン", "富士フイルム", "富士通", "NEC", "村田製作所", "ムラタ", "京セラ", "TDK", "ローム", "キオクシア",
          "ルネサス", "東京エレクトロン", "SCREEN", "ディスコ", "信越", "SUMCO", "クボタ", "ヤンマー", "井関", "コマツ", "小松製作所",
          "ファナック", "安川電機", "オムロン", "キーエンス", "ダイキン", "ブリヂストン", "ブリジストン", "横浜ゴム", "住友ゴム",
          "TOYO TIRE", "旭化成", "東レ", "帝人", "花王", "資生堂", "ライオン", "ユニ・チャーム", "ユニチャーム", "日清", "明治",
          "森永", "山崎製パン", "ヤマザキ", "味の素", "キユーピー", "サントリー", "アサヒ", "キリン", "コカ・コーラ", "伊藤ハム",
          "日本ハム", "プリマハム", "LIXIL", "リクシル", "YKK", "TOTO", "IHI", "JFE", "日本製鉄", "神戸製鋼", "コベルコ", "テスラ",
          "Apple", "アップル", "アマゾン", "Amazon", "ヤマト運輸", "佐川", "日本通運", "DNP", "大日本印刷", "凸版", "TOPPAN",
          "ジヤトコ", "JATCO", "アドヴィックス", "マレリ", "カルソニック", "ボッシュ", "BOSCH", "ミネベア", "日本電産", "ニデック",
          "マキタ", "SMC", "THK", "NTN", "NSK", "日本精工", "テルモ", "オリンパス", "HOYA", "AGC", "旭硝子", "日本ガイシ",
          "日本特殊陶業", "イビデン", "太陽誘電", "アルプスアルパイン", "アルプス", "JSR", "レゾナック", "昭和電工", "プライムアース",
          "プライムプラネット", "パナソニックエナジー", "GSユアサ", "エンビジョン", "AESC"]
CARS = re.compile(r"プリウス|アルファード|ヴェルファイア|カローラ|クラウン|ヤリス|ハリアー|ランドクルーザー|ランクル|ノア|ヴォクシー|"
                  r"アクア|シエンタ|ハイエース|ＲＡＶ４|RAV4|セレナ|ノート|エクストレイル|スカイライン|リーフ|フィット|フリード|"
                  r"ステップワゴン|ヴェゼル|N-BOX|シビック|CX-[0-9]|ロードスター|フォレスター|インプレッサ|レヴォーグ|ジムニー|"
                  r"スイフト|ハスラー|タント|ムーヴ|デリカ|アウトランダー|エルフ|フォワード|レンジャー|プロフィア")
# 派遣会社から「求人媒体に載せないで」と指定されている案件は、どの欄に書かれていても載せない
NOPOST = re.compile(r"掲載.{0,6}(NG|ＮＧ|厳禁|不可|禁止|[×✕])|媒体.{0,10}(NG|ＮＧ|厳禁|不可|禁止|[×✕])")
GENERIC = {"スチール", "工場", "事業所", "製作所", "センター", "物流", "食品", "工業", "産業", "電機", "電子", "化学", "精機", "製造", "本社",
           "第一", "第二", "第三", "支店", "営業所", "倉庫", "日本", "東京", "大阪", "名古屋", "九州", "関西", "関東", "東北", "中部",
           "西日本", "東日本", "テクノ", "サービス", "ロジ", "ロジスティクス", "物流センター", "配送センター", "テック", "技研",
           "自動車", "部品", "金属", "樹脂", "化成", "精密", "機械", "製薬", "薬品", "運輸", "梱包", "株式会社", "グループ", "案件",
           "新規", "増員", "急募", "寮付き", "日勤", "夜勤", "交替", "交代", "検査", "組立", "加工", "塗装", "溶接", "機械オペ"}
SUFFIX = re.compile(r"(株式会社|有限会社|合同会社|\(株\)|（株）|㈱|\(有\)|（有）|㈲)")
TAIL = re.compile(r"(第?[0-9０-９一二三四五六七八九十]*(工場|事業所|事業場|センター|支店|営業所|本社|製造所|プラント|物流センター|"
                  r"DC|ＤＣ|倉庫|工区|棟|地区|サイト|ファクトリー))+$")

CATS = [
    (r"半導体|ウエハ|ウェハ|ウエーハ", "半導体関連の製造スタッフ"),
    (r"保全|メンテナンス|保守|技術職|エンジニア", "設備保全・技術スタッフ"),
    (r"フォークリフト|リフト作業|リフトオペ", "フォークリフト作業スタッフ"),
    (r"(自動車|車体|車両|クルマ|エンジン|トラック|バス).{0,25}(組立|組み立て|組付|組み付|取付|取り付)|"
     r"(組立|組み立て|組付|組み付).{0,25}(自動車|車体|車両|エンジン)", "自動車の組立スタッフ"),
    (r"自動車部品|車の部品|カーパーツ|車載|自動車用|自動車関連", "自動車部品の製造スタッフ"),
    (r"溶接", "溶接スタッフ"),
    (r"塗装", "塗装スタッフ"),
    (r"食品(?!包装|容器|トレー|用|パッケージ)|弁当|パン(?!フ|チ)|菓子|飲料|惣菜|冷凍食品|食肉|調味料|乳製品|チョコ", "食品の製造スタッフ"),
    (r"医薬|薬品|化粧品|医療機器|医療用", "医薬品・化粧品の製造スタッフ"),
    (r"機械オペ|マシンオペ|オペレーター|オペレータ|機械操作|マシン操作|機械OP|マシンOP|NC旋盤|マシニング", "機械オペレーター"),
    (r"電子部品|基板|コンデンサ|電池|バッテリー|液晶|コネクタ", "電子部品の製造スタッフ"),
    (r"組立|組み立て|組付|組み付", "組立スタッフ"),
    (r"加工|プレス|研磨|切削|成形|成型|鋳造|鍛造|メッキ|めっき", "部品の加工スタッフ"),
    (r"ピッキング|仕分|倉庫|入出庫|入庫|出庫", "倉庫内の軽作業スタッフ"),
    (r"検査|検品|目視", "検査スタッフ"),
]


def nfkc(s):
    """全角英数や半角カナをそろえる。丸数字（①など）は時刻とくっつくと読み違えるので残す。"""
    return "".join(c if "\u2460" <= c <= "\u2473" else unicodedata.normalize("NFKC", c) for c in str(s or ""))


def norm(s):
    return re.sub(r"[ \t\u3000]+", " ", nfkc(s).replace("\r", "")).strip()


def to_int(s):
    s = str(s or "").translate(str.maketrans("０１２３４５６７８９，", "0123456789,"))
    m = re.search(r"\d[\d,]*", s)
    if not m:
        return None
    try:
        v = int(m.group(0).replace(",", ""))
    except ValueError:
        return None
    if "万" in s and v < 1000:
        v *= 10000
    return v


def city_of(pref, addr):
    a = re.sub(r"\s+", "", nfkc(addr))
    a = re.sub(r"^[^\w]+", "", a)
    a = re.sub(r"^(〒?\d{3}-?\d{4})", "", a)
    for p in PREFS:
        if a.startswith(p):
            a = a[len(p):]
            break
    if not a:
        return None
    m = re.match(r"(大和郡山市|郡山市|郡上市|蒲郡市|小郡市)", a)
    if not m and "郡" in a[:6]:
        m = re.match(r"(.{1,5}郡.{1,6}?[町村])", a)
        if m:
            return m.group(1)
    if not m and pref == "東京都":
        m = re.match(r"(.{1,3}区)", a)
        if m:
            return m.group(1)
    if not m:
        m = re.match(r"(.{1,7}?市)", a)
        if m and a[m.end():m.end() + 1] == "市":
            m = re.match(re.escape(m.group(1)) + "市", a)
    if m:
        c = m.group(0)
        if c in SEIREI:
            k = re.match(r"(.{1,3}?区)", a[len(c):])
            if k:
                c += k.group(1)
        return c
    m = re.match(r"(.{1,6}?[町村])", a)
    return m.group(1) if m else None


def name_tokens(name):
    """案件名の欄から派遣先の社名を取り出す（【派遣】や※以降のメモは社名ではないので捨てる）。"""
    s = nfkc(name).strip()
    s = re.sub(r"【[^】]*】|\[[^\]]*\]", " ", s).strip()
    s = SUFFIX.sub(" ", s).replace("(株)", " ").replace("(有)", " ").strip()
    s = re.split(r"[※(/<@\n]", s)[0]
    parts = [p for p in re.split(r"[\s_]+", s) if p]
    out = set()
    if not parts:
        return out
    p = parts[0]
    core = TAIL.sub("", p)
    for t in (p, core):
        if len(t) >= 3 and t not in GENERIC and not re.fullmatch(r"[0-9A-Za-z]{1,3}", t):
            out.add(t)
    return out


def build_scrubber(rows):
    glob_tokens = set()
    for r in rows:
        for t in name_tokens(r["name"]):
            if len(t) >= 4:
                glob_tokens.add(t)
    words = sorted(set(AGENCIES) | set(MAKERS) | glob_tokens, key=len, reverse=True)
    place = "|".join(sorted(PREFS, key=len, reverse=True))
    def pat(w):
        if re.fullmatch(r"[ -~]+", w):  # 英字だけの社名は、単語の途中では反応させない
            return r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])"
        return re.escape(w)
    rx = re.compile("(" + "|".join(pat(w) for w in words) + r")(?![市区町村郡県駅])", re.I)
    return rx, place


DATED = re.compile(r"\d{1,2}/\d{1,2}|\d{1,2}月|入社スケジュール|入社日|赴任|開始日|期間限定|キャンペーン")
EMPTY = re.compile(r"^[\W_]*(要確認|不明|未定|なし|無し|確認中)?[\W_]*$|^(通勤|最寄り?駅?)[::]\s*(要確認|不明|未定|-)?$")


def clean_text(text, own_tokens, rx):
    """1行ずつ見て、載せない行（条件・日付・社名が入った行）を落とす。"""
    out = []
    for line in str(text or "").replace("\r", "").split("\n"):
        line = norm(line)
        if not line or EMPTY.search(line):
            continue
        if SENSITIVE.search(line) or CARS.search(line) or DATED.search(line):
            continue
        if rx.search(line) or any(t in line for t in own_tokens) or SUFFIX.search(line) or "グループ" in line:
            continue
        line = re.sub(r"https?://\S+|\b0\d{1,4}-\d{1,4}-\d{3,4}\b", "", line).strip()
        if line:
            out.append(line)
    return "\n".join(out)


def category(job):
    for pat, label in CATS:
        if re.search(pat, job):
            return label
    return "製造スタッフ"


def sanitize(values):
    head = [str(x) for x in values[0]]
    if head and head[0] == "派遣会社":
        values = values[1:]
    rows = []
    for v in values:
        v = (list(v) + [""] * len(COLS))[:len(COLS)]
        rows.append(dict(zip(COLS, [str(x).strip() for x in v])))
    rx, _ = build_scrubber(rows)
    out, seen, skip = [], set(), {}

    def drop(why):
        skip[why] = skip.get(why, 0) + 1

    for r in rows:
        if NOPOST.search("\n".join(r.values())):
            drop("媒体掲載NGの指定あり"); continue
        if re.fullmatch(r"0+", r["headcount"] or ""):
            drop("募集人数0"); continue
        head = re.sub(r"^[^\w]+", "", nfkc(r["addr"]).strip())
        for p in PREFS:  # 勤務地の欄に書かれた都道府県を優先する
            if head.startswith(p):
                r["pref"] = p
                break
        if r["pref"] not in PREFS:
            drop("都道府県なし"); continue
        city = city_of(r["pref"], r["addr"])
        if not city:
            drop("市区町村が不明"); continue
        hourly, monthly = to_int(r["hourly"]), to_int(r["monthly"])
        if hourly is not None and not (900 <= hourly <= 5000):
            hourly = None
        if monthly is not None and not (150000 <= monthly <= 900000):
            monthly = None
        if not hourly and not monthly:
            drop("給与なし"); continue
        toks = name_tokens(r["name"])
        job = clean_text(r["job"], toks, rx)
        job = re.sub(r"(…|\.\.\.)+$", "", job).strip()  # 途中で切れた文末の「…」は外す
        short = len(job) < 8
        shift = norm(r["shift"])
        if shift in ("不明", "複数あり", ""):
            shift = ""
        cat = category(job)
        if short:  # 仕事内容がほぼ空のときは、職種名から最低限の説明を付ける
            job = (job + "\n" if job else "") + "寮付きの%sのお仕事です。くわしい内容は担当者からご案内します。" % cat.replace("スタッフ", "")
        key = (r["pref"], city, cat, shift, hourly, monthly, job[:60])
        if key in seen:
            drop("重複"); continue
        seen.add(key)
        dormfee = clean_text(r["dormfee"], toks, rx)
        dormfee = "\n".join(l for l in dormfee.split("\n") if not re.search(r"[✕×✖]|寮なし|対応無|^[-－ー]+$", l))
        bonus = clean_text(r["bonus"], toks, rx)
        tags = []
        if re.search(r"寮費無料[:：]?\s*[〇○◯◎]|寮費[:：]\s*無料|^寮費無料$", r["dormfee"], re.M) and \
                not re.search(r"寮費無料[:：]?\s*[✕×△▲]", r["dormfee"]):
            tags.append("寮費無料")
        if re.search(r"祝", bonus) and re.search(r"\d", bonus) and not re.search(r"[✕×✖]|なし|無し", bonus):
            tags.append("入社祝い金あり")
        else:
            bonus = ""
        jid = hashlib.sha1("|".join([r["agency"], r["no"], r["name"], r["shift"], city]).encode()).hexdigest()[:10]
        out.append({
            "id": jid, "pref": r["pref"], "city": city, "cat": cat, "shift": shift,
            "hourly": hourly, "monthly": monthly, "job": job, "tags": tags,
            "dorm": dormfee, "bonus": bonus,
            "hours": clean_text(r["hours"], toks, rx), "holiday": clean_text(r["holiday"], toks, rx),
            "access": clean_text(r["access"], toks, rx),
        })
    ids = {}
    for j in out:  # 同じ番号が出たら枝番を付ける
        n = ids.get(j["id"], 0); ids[j["id"]] = n + 1
        if n:
            j["id"] = j["id"][:8] + "%02d" % n
    return out, skip


# ---------- ここからページ作り ----------
CSS = """:root{--ink:#1d2a33;--sub:#5b6b76;--line:#e3e8ec;--bg:#f6f8f9;--main:#0f6e8c;--accent:#f3812a;--soft:#e8f3f7}
*{box-sizing:border-box}body{margin:0;font-family:"Hiragino Sans","Noto Sans JP",Meiryo,sans-serif;color:var(--ink);background:var(--bg);line-height:1.75}
a{color:var(--main)}header{background:var(--main);color:#fff;padding:12px 16px}header a{color:#fff;text-decoration:none;font-weight:800}
.wrap{max-width:760px;margin:0 auto;padding:16px}.card{background:#fff;border-radius:16px;padding:20px;margin:14px 0;box-shadow:0 4px 18px rgba(16,42,60,.06)}
h1{font-size:22px;line-height:1.45;margin:6px 0 10px}h2{font-size:16px;margin:0 0 8px;border-left:4px solid var(--accent);padding-left:8px}
.loc{color:var(--sub);font-weight:700;font-size:14px}.tags{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}
.tag{background:var(--soft);color:var(--main);font-weight:800;font-size:12px;padding:4px 10px;border-radius:999px}
.pay{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:12px 0}.pay div{background:#fff7ef;border-radius:12px;padding:10px;text-align:center}
.pay b{display:block;font-size:22px;color:var(--accent)}.pay small{color:var(--sub);font-weight:700}
dl{display:grid;grid-template-columns:7em 1fr;gap:8px 12px;margin:0}dt{font-weight:800;color:var(--sub);font-size:14px}dd{margin:0;white-space:pre-wrap;font-size:14px}
.body{white-space:pre-wrap;font-size:14.5px}
.apply{display:block;text-align:center;background:linear-gradient(135deg,#19d36a,#06b04b);color:#fff;font-weight:900;font-size:18px;padding:16px;border-radius:14px;text-decoration:none;box-shadow:0 5px 0 #048a3a;margin:18px 0 6px}
.note{font-size:12px;color:var(--sub)}footer{font-size:12px;color:var(--sub);text-align:center;padding:24px 16px 90px}
.list a.item{display:block;background:#fff;border-radius:14px;padding:14px 16px;margin:10px 0;text-decoration:none;color:var(--ink);box-shadow:0 3px 12px rgba(16,42,60,.06)}
.list .t{font-weight:800}.list .m{color:var(--accent);font-weight:900}.prefs{display:flex;flex-wrap:wrap;gap:8px}.prefs a{background:#fff;border:1px solid var(--line);border-radius:999px;padding:6px 12px;text-decoration:none;font-weight:700;font-size:14px}
.dock{position:fixed;left:0;right:0;bottom:0;background:rgba(255,255,255,.96);padding:10px 16px;box-shadow:0 -4px 16px rgba(0,0,0,.08)}.dock .apply{margin:0;font-size:16px;padding:12px}
"""
FOOT = ("<footer>株式会社京栄センター（有料職業紹介事業 許可番号 23-ユ-301956）<br>"
        "ご紹介は無料です。求職者の方から手数料をいただくことはありません。<br>"
        "掲載内容は毎日更新しています。募集が終了した求人は掲載を終了します。</footer>")
e = html.escape


def yen(n):
    return "{:,}円".format(n)


def man(n):
    return "%d万円" % round(n / 10000)


def title_of(j):
    return "%s（寮付き%s）" % (j["cat"], "・" + j["shift"] if j["shift"] else "")


def pay_line(j):
    p = []
    if j["hourly"]:
        p.append("時給" + yen(j["hourly"]))
    if j["monthly"]:
        p.append("月収例" + man(j["monthly"]))
    return "／".join(p)


def page(title, desc, canon, body, ld=None, head_link="./"):
    ldtag = ""
    if ld:
        ldtag = '<script type="application/ld+json">%s</script>' % json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
    return ('<!doctype html><html lang="ja"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>%s</title><meta name=\"description\" content=\"%s\"><link rel=\"canonical\" href=\"%s\">%s"
            '<link rel="stylesheet" href="%sstyle.css"></head><body>'
            '<header><a href="%s">京栄センター 寮付きのお仕事</a></header><main class="wrap">%s</main>%s</body></html>'
            ) % (e(title), e(desc), e(canon), ldtag, head_link, head_link, body, FOOT)


def item(j, prefix=""):
    tags = "".join('<span class="tag">%s</span>' % e(t) for t in j["tags"])
    return ('<a class="item" href="%sjob/%s.html"><div class="loc">📍 %s%s%s</div><div class="t">%s</div>'
            '<div class="m">%s</div><div class="tags">%s</div></a>'
            ) % (prefix, j["id"], e(j["pref"]), e(j["city"]), "・" + e(j["shift"]) if j["shift"] else "",
                 e(title_of(j)), e(pay_line(j)), tags)


def job_page(j, posted):
    t = title_of(j)
    pc = "p%02d.html" % (PREFS.index(j["pref"]) + 1)
    url = BASE + "job/%s.html" % j["id"]
    apply_url = OUBO + "?from=job_" + j["id"]
    desc_parts = ["<p>%s</p>" % e(j["job"]).replace("\n", "<br>")]
    for label, k in (("寮", "dorm"), ("特典", "bonus"), ("勤務時間", "hours"), ("休日", "holiday")):
        if j[k]:
            desc_parts.append("<p>【%s】<br>%s</p>" % (label, e(j[k]).replace("\n", "<br>")))
    if j["hourly"]:
        sal = {"@type": "QuantitativeValue", "value": j["hourly"], "unitText": "HOUR"}
    else:
        sal = {"@type": "QuantitativeValue", "value": j["monthly"], "unitText": "MONTH"}
    ld = {"@context": "https://schema.org/", "@type": "JobPosting", "title": t,
          "description": "".join(desc_parts), "datePosted": posted,
          "validThrough": (TODAY + datetime.timedelta(days=30)).isoformat() + "T23:59:59+09:00",
          "employmentType": "TEMPORARY",
          "hiringOrganization": {"@type": "Organization", "name": "株式会社京栄センター", "sameAs": LP},
          "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": j["city"],
                                                        "addressRegion": j["pref"], "addressCountry": "JP"}},
          "identifier": {"@type": "PropertyValue", "name": "京栄センター", "value": j["id"]},
          "directApply": False,
          "baseSalary": {"@type": "MonetaryAmount", "currency": "JPY", "value": sal}}
    pay = ""
    if j["hourly"]:
        pay += "<div><small>時給</small><b>%s</b></div>" % yen(j["hourly"])
    if j["monthly"]:
        pay += "<div><small>月収例</small><b>%s</b></div>" % man(j["monthly"])
    tags = "".join('<span class="tag">%s</span>' % e(x) for x in j["tags"])
    dl = "<dt>勤務地</dt><dd>%s%s%s</dd>" % (e(j["pref"]), e(j["city"]),
                                          "\n最寄り・通勤：" + e(j["access"]).replace("\n", "／") if j["access"] else "")
    for label, k in (("勤務形態", "shift"), ("勤務時間", "hours"), ("休日", "holiday"), ("寮", "dorm"), ("特典", "bonus")):
        if j[k]:
            dl += "<dt>%s</dt><dd>%s</dd>" % (label, e(j[k]))
    body = (
        '<div class="card"><div class="loc">📍 %s%s</div><h1>%s</h1><div class="tags">%s</div><div class="pay">%s</div>'
        '<a class="apply" href="%s">この求人について相談する（無料）</a>'
        '<p class="note">6つの質問に答えると、担当者がLINEまたはお電話でご案内します。</p></div>'
        '<div class="card"><h2>お仕事の内容</h2><div class="body">%s</div></div>'
        '<div class="card"><h2>募集要項</h2><dl>%s</dl></div>'
        '<div class="card"><h2>京栄センターについて</h2><p>寮付きのお仕事専門の職業紹介会社です。赴任の交通費、荷物の送料、'
        '携帯が止まっている方の手続きなど、働き始めるまでをまとめてサポートします。紹介先の会社名は、ご相談のあとに担当者からお伝えします。</p>'
        '<p><a href="../%s">%sのほかの寮付き求人を見る</a></p></div>'
        '<div class="dock"><a class="apply" href="%s">LINE・電話で無料相談</a></div>'
    ) % (e(j["pref"]), e(j["city"]), e(t), tags, pay, e(apply_url), e(j["job"]), dl, pc, e(j["pref"]), e(apply_url))
    title = "%s｜%s%s｜%s 寮付き｜京栄センター" % (t, j["pref"], j["city"], pay_line(j).split("／")[0])
    desc = "%s%sの%s。%s。寮付き。ご紹介は無料です。" % (j["pref"], j["city"], t, pay_line(j).replace("／", "、"))
    return page(title, desc, url, body, ld, "../")


def render(jobs, out):
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "job"))
    posted = {}
    try:  # 前回までの掲載開始日を引き継ぐ
        with urllib.request.urlopen(BASE + "posted.json", timeout=20) as r:
            posted = json.loads(r.read().decode("utf-8"))
    except Exception:
        posted = {}
    newposted = {}
    jobs.sort(key=lambda j: -(j["monthly"] or (j["hourly"] or 0) * 168))
    for j in jobs:
        d = posted.get(j["id"]) or TODAY.isoformat()
        newposted[j["id"]] = d
        with open(os.path.join(out, "job", j["id"] + ".html"), "w", encoding="utf-8") as f:
            f.write(job_page(j, d))
    by = {}
    for j in jobs:
        by.setdefault(j["pref"], []).append(j)
    urls = [BASE]
    for p in PREFS:
        if p not in by:
            continue
        pc = "p%02d.html" % (PREFS.index(p) + 1)
        body = '<h1>%sの寮付きのお仕事（%d件）</h1><div class="list">%s</div><p><a href="./">ほかの都道府県を見る</a></p>' % (
            e(p), len(by[p]), "".join(item(j) for j in by[p]))
        with open(os.path.join(out, pc), "w", encoding="utf-8") as f:
            f.write(page("%sの寮付き求人（%d件）｜京栄センター" % (p, len(by[p])),
                         "%sの寮付きのお仕事%d件。工場・倉庫のお仕事を中心に掲載。ご紹介は無料です。" % (p, len(by[p])),
                         BASE + pc, body))
        urls.append(BASE + pc)
    prefs = "".join('<a href="p%02d.html">%s（%d）</a>' % (PREFS.index(p) + 1, e(p), len(by[p])) for p in PREFS if p in by)
    body = ('<h1>寮付きのお仕事を探す</h1><p>全国の寮付きのお仕事を%d件掲載しています。ご紹介は無料です。</p>'
            '<div class="card"><h2>都道府県から探す</h2><div class="prefs">%s</div></div>'
            '<h2>月収の高いお仕事</h2><div class="list">%s</div>') % (len(jobs), prefs, "".join(item(j) for j in jobs[:80]))
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(page("寮付きのお仕事を探す｜京栄センター",
                     "全国の寮付きのお仕事を%d件掲載。赴任の交通費や携帯の手続きまでサポート。ご紹介は無料です。" % len(jobs), BASE, body))
    with open(os.path.join(out, "404.html"), "w", encoding="utf-8") as f:
        f.write(page("この求人は掲載を終了しました｜京栄センター", "この求人は掲載を終了しました。", BASE + "404.html",
                     '<div class="card"><h1>この求人は掲載を終了しました</h1><p>募集が終わったか、内容が変わった可能性があります。</p>'
                     '<p><a href="%s">ほかの寮付きのお仕事を見る</a></p></div>' % BASE, None, BASE))
    urls += [BASE + "job/%s.html" % j["id"] for j in jobs]
    with open(os.path.join(out, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u in urls:
            f.write("<url><loc>%s</loc><lastmod>%s</lastmod></url>\n" % (e(u), TODAY.isoformat()))
        f.write("</urlset>\n")
    with open(os.path.join(out, "robots.txt"), "w") as f:
        f.write("User-agent: *\nAllow: /\nSitemap: %ssitemap.xml\n" % BASE)
    with open(os.path.join(out, "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS)
    with open(os.path.join(out, "posted.json"), "w") as f:
        json.dump(newposted, f)
    open(os.path.join(out, ".nojekyll"), "w").close()
    return len(jobs), len(by)


def main():
    mode = sys.argv[1]
    if mode == "sanitize":
        raw = json.load(open(sys.argv[2], encoding="utf-8"))
        values = raw["values"] if isinstance(raw, dict) else raw
        jobs, skip = sanitize(values)
        os.makedirs(os.path.dirname(os.path.abspath(sys.argv[3])), exist_ok=True)
        json.dump(jobs, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        print("載せる求人:", len(jobs), "／ 載せない内訳:", json.dumps(skip, ensure_ascii=False))
    elif mode == "render":
        jobs = json.load(open(sys.argv[2], encoding="utf-8"))
        if len(jobs) < 300:
            sys.exit("求人が%d件しかありません。データの取り込みに失敗した可能性があるので、公開を止めます。" % len(jobs))
        n, p = render(jobs, sys.argv[3])
        print("求人ページ %d件、都道府県ページ %d件を作りました。" % (n, p))


if __name__ == "__main__":
    main()
