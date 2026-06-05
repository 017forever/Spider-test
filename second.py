from flask import Flask, request, jsonify, make_response
import requests as req_lib
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import random
import os
import json

app = Flask(__name__)

# ──────────────────────────────────────────
# Firebase 初始化
# ──────────────────────────────────────────
if os.path.exists("serviceAccountKey.json"):
    cred = credentials.Certificate("serviceAccountKey.json")
else:
    firebase_config = os.getenv("FIREBASE_CONFIG")
    cred_dict = json.loads(firebase_config)
    cred = credentials.Certificate(cred_dict)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()
# ──────────────────────────────────────────
# 類型關鍵字對照表
# ──────────────────────────────────────────
GENRE_KEYWORDS = {
    "異世界": ["異世界", "轉生", "召喚", "穿越", "史萊姆", "魔王", "勇者", "迷宮"],
    "戀愛":   ["戀愛", "婚", "喜歡", "告白", "同居", "青梅", "女友", "男友", "愛"],
    "戰鬥":   ["英雄", "戰鬥", "討伐", "獵人", "格鬥", "決戰", "最強", "無敵"],
    "校園":   ["學校", "高中", "大學", "學園", "社團", "學生", "班"],
    "科幻":   ["機器人", "科技", "未來", "宇宙", "石紀", "STONE", "DR."],
    "奇幻":   ["魔法", "精靈", "龍", "騎士", "魔導", "咒術", "芙莉蓮"],
    "懸疑":   ["偵探", "推理", "謀殺", "秘密", "真相", "謎"],
    "運動":   ["足球", "籃球", "排球", "棒球", "競技", "少年"],
}

# 同義詞對照（使用者說「打架」→ 對應「戰鬥」）
GENRE_ALIAS = {
    "打架": "戰鬥", "熱血": "戰鬥",
    "穿越": "異世界", "轉生": "異世界",
    "愛情": "戀愛", "浪漫": "戀愛",
    "魔法": "奇幻", "冒險": "奇幻",
    "推理": "懸疑", "偵探": "懸疑",
    "體育": "運動",
    "高中": "校園", "學校": "校園",
    "機器人": "科幻", "宇宙": "科幻",
}

DAY_MAP = {"0": "日", "1": "一", "2": "二", "3": "三", "4": "四", "5": "五", "6": "六"}


def auto_genre(title: str) -> list:
    genres = []
    for genre, keywords in GENRE_KEYWORDS.items():
        if any(kw in title for kw in keywords):
            genres.append(genre)
    return genres if genres else ["其他"]


def parse_views(text: str) -> int:
    text = text.replace(",", "").strip()
    if "萬" in text:
        return int(float(text.replace("萬", "")) * 10000)
    elif "億" in text:
        return int(float(text.replace("億", "")) * 100000000)
    return int(text) if text.isdigit() else 0


def normalize_genre(genre_input: str) -> str:
    """把使用者輸入的類型詞標準化"""
    return GENRE_ALIAS.get(genre_input.strip(), genre_input.strip())


# ──────────────────────────────────────────
# 路由 0：首頁  GET /
# ──────────────────────────────────────────
@app.route("/")
def index():
    R  = "<h1>歡迎進入動畫推薦網站</h1>"
    R += "<a href='/crawl'>更新動畫資料</a><br><hr>"
    R += "<a href='/all'>查看全部動畫</a><br><hr>"
    R += "<a href='/hot'>近期熱播排行</a><br><hr>"
    R += "<a href='/new'>本季新番</a><br><hr>"
    R += "<a href='/random'>隨機推薦動畫</a><br><hr>"
    R += "<a href='/search'>查詢動漫</a><br><hr>"
    return R


@app.route("/all")
def all_anime():
    docs = db.collection("本季新番").get()
    R = "<h1>全部動畫</h1>"
    R += "<a href='/'>← 回首頁</a><br><hr>"
    for doc in docs:
        d = doc.to_dict()
        genre_str = "、".join(d.get("genre", ["其他"]))
        R += f"<b>{d.get('title','未知')}</b>　類型：{genre_str}　"
        R += f"集數：{d.get('episode','未知')}　人氣：{d.get('views','未知')}<br>"
        if d.get("link"):
            R += f"<a href='{d['link']}' target='_blank'>▶ 前往觀看</a>"
        R += "<hr>"
    return R


@app.route("/hot")
def hot():
    docs = db.collection("熱門排行").order_by("rank").limit(10).get()
    R = "<h1>近期熱播排行 🏆</h1>"
    R += "<a href='/'>← 回首頁</a><br><hr>"
    for doc in docs:
        d = doc.to_dict()
        R += f"第 {d.get('rank','?')} 名　<b>{d.get('title','未知')}</b>　"
        R += f"人氣：{d.get('views','未知')}<br>"
        if d.get("link"):
            R += f"<a href='{d['link']}' target='_blank'>▶ 前往觀看</a>"
        R += "<hr>"
    return R


@app.route("/new")
def new_anime():
    docs = db.collection("本季新番").get()
    R = "<h1>本季新番 🎌</h1>"
    R += "<a href='/'>← 回首頁</a><br><hr>"
    for doc in docs:
        d = doc.to_dict()
        genre_str = "、".join(d.get("genre", ["其他"]))
        R += f"<b>{d.get('title','未知')}</b>　類型：{genre_str}<br>"
        R += f"更新：星期{d.get('day','?')} {d.get('hour','')}　集數：{d.get('episode','未知')}<br>"
        if d.get("link"):
            R += f"<a href='{d['link']}' target='_blank'>▶ 前往觀看</a>"
        R += "<hr>"
    return R


@app.route("/random")
def random_anime():
    all_docs = [doc.to_dict() for doc in db.collection("本季新番").get()]
    R = "<h1>隨機推薦動畫 🎲</h1>"
    R += "<a href='/'>← 回首頁</a>　<a href='/random'>再推薦一部</a><br><hr>"
    if not all_docs:
        R += "目前沒有資料，請先執行 <a href='/crawl'>更新動畫資料</a>"
        return R
    pick = random.choice(all_docs)
    genre_str = "、".join(pick.get("genre", ["其他"]))
    R += f"<h2>{pick.get('title','未知')}</h2>"
    R += f"類型：{genre_str}<br>"
    R += f"集數：{pick.get('episode','未知')}<br>"
    R += f"人氣：{pick.get('views','未知')}<br>"
    R += f"更新：星期{pick.get('day','?')} {pick.get('hour','')}<br>"
    if pick.get("link"):
        R += f"<a href='{pick['link']}' target='_blank'>▶ 前往觀看</a>"
    return R


@app.route("/search")
def search():
    keyword = request.args.get("q", "").strip()   # 網址帶參數：/search?q=咒術
    R = "<h1>查詢動漫 🔍</h1>"
    R += "<a href='/'>← 回首頁</a><br><hr>"
    R += "<form method='get'>關鍵字：<input name='q' value='" + keyword + "'>"
    R += "<button type='submit'>搜尋</button></form><hr>"

    if not keyword:
        R += "請輸入動漫名稱關鍵字進行搜尋"
        return R

    docs = db.collection("本季新番").get()
    results = [doc.to_dict() for doc in docs if keyword in doc.to_dict().get("title", "")]

    if not results:
        R += f"找不到含有「{keyword}」的動漫"
        return R

    for d in results:
        genre_str = "、".join(d.get("genre", ["其他"]))
        R += f"<b>{d.get('title','未知')}</b>　類型：{genre_str}<br>"
        R += f"集數：{d.get('episode','未知')}　人氣：{d.get('views','未知')}<br>"
        if d.get("link"):
            R += f"<a href='{d['link']}' target='_blank'>▶ 前往觀看</a>"
        R += "<hr>"
    return R


# ──────────────────────────────────────────
# 路由 1：爬蟲  GET /crawl
# ──────────────────────────────────────────
@app.route("/crawl")
def crawl():
    url = "https://ani.gamer.com.tw/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    response = req_lib.get(url, headers=headers)
    response.encoding = "utf-8"
    if response.status_code != 200:
        return f"請求失敗，狀態碼：{response.status_code}"

    soup = BeautifulSoup(response.text, "html.parser")

    
    newanime_block = soup.select_one(".timeline-ver > .newanime-block")
    if not newanime_block:
        return "找不到新番區塊，請確認網頁結構是否更新"

    anime_items = newanime_block.select(".newanime-date-area")
    all_docs = []

    for item in anime_items:
        title_tag   = item.select_one(".anime-name")
        ep_tag      = item.select_one(".anime-episode p")
        view_tag    = item.select_one(".anime-watch-number p")
        link_tag    = item.select_one("a.anime-card-block")
        img_tag     = item.select_one(".anime-blocker img")
        hour_tag    = item.select_one(".anime-hours")
        day_code    = item.get("data-date-code", "7")
        animesn     = item.get("data-animesn", "")

        title_str   = title_tag.get_text(strip=True)   if title_tag   else "未知"
        episode_str = ep_tag.get_text(strip=True)      if ep_tag      else "未知"
        views_str   = view_tag.get_text(strip=True)    if view_tag    else "0"
        link_str    = "https://ani.gamer.com.tw/" + link_tag["href"] if link_tag else ""
        image_str   = img_tag.get("data-src", "")      if img_tag     else ""
        hour_str    = hour_tag.get_text(strip=True)    if hour_tag    else ""
        day_str     = DAY_MAP.get(day_code, "未定")

        doc = {
            "title":     title_str,
            "episode":   episode_str,
            "views":     views_str,
            "views_num": parse_views(views_str),
            "link":      link_str,
            "image":     image_str,
            "hour":      hour_str,
            "day":       day_str,
            "animesn":   animesn,
            "genre":     auto_genre(title_str),
        }

        db.collection("本季新番").document(title_str).set(doc)
        all_docs.append(doc)

    # 排行榜（前10）
    sorted_docs = sorted(all_docs, key=lambda x: x["views_num"], reverse=True)[:10]
    for rank, anime in enumerate(sorted_docs, start=1):
        anime["rank"] = rank
        db.collection("熱門排行").document(f"rank_{rank:02d}").set(anime)

    return f"爬蟲及存檔完畢！共 {len(all_docs)} 部，熱門排行前10已更新"


# ──────────────────────────────────────────
# 路由 2：Dialogflow Webhook  POST /webhook
# ──────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    req = request.get_json(force=True)

    action     = req.get("queryResult", {}).get("action", "")
    parameters = req.get("queryResult", {}).get("parameters", {})
    query_text = req.get("queryResult", {}).get("queryText", "")

    print(f"[Webhook] action={action} | query={query_text}")

    if action == "new_season":
        info = handle_new_season()

    elif action == "by_genre":
        genre_input = parameters.get("genre", "")
        genre = normalize_genre(genre_input)
        info = handle_by_genre(genre)

    elif action == "detail":
        anime_name = parameters.get("anime_name", "")
        info = handle_detail(anime_name)

    elif action == "ranking":
        info = handle_ranking()

    elif action == "random_recommend":
        info = handle_random()

    else:
        info = (
            "你好！我是巴哈動漫小精靈 🎌\n\n"
            "你可以問我：\n"
            "・本季有哪些新番？\n"
            "・推薦奇幻類動漫\n"
            "・告訴我更多關於[動漫名稱]\n"
            "・熱門排行榜\n"
            "・隨機推薦一部"
        )

    return make_response(jsonify({"fulfillmentText": info}))


# ──────────────────────────────────────────
# Intent 處理函式
# ──────────────────────────────────────────

def handle_new_season():
    """本季新番 → 回傳前8部"""
    docs = db.collection("本季新番").limit(8).get()
    if not docs:
        return "目前資料庫還沒有本季新番資料，請先執行 /crawl 更新！"

    info = "🎌 本季新番一覽：\n\n"
    for doc in docs:
        d = doc.to_dict()
        genre_str = "、".join(d.get("genre", ["其他"]))
        info += f"📺 {d['title']}\n"
        info += f"   類型：{genre_str} | 更新：星期{d.get('day','?')} {d.get('hour','')}\n"
        info += f"   集數：{d.get('episode','未知')} | 人氣：{d.get('views','未知')}\n\n"

    info += "想查某部的詳情，輸入動漫名稱就可以喔 😊"
    return info


def handle_by_genre(genre):
    """依類型篩選動漫"""
    if not genre:
        return (
            "請告訴我你想看哪種類型？\n"
            "例如：異世界、戀愛、戰鬥、校園、科幻、奇幻、懸疑、運動"
        )

    docs = db.collection("本季新番").get()
    matched = [doc.to_dict() for doc in docs if genre in doc.to_dict().get("genre", [])]

    if not matched:
        return f"😢 目前沒有找到【{genre}】類型的動漫\n試試：異世界、戀愛、戰鬥、奇幻"

    info = f"✨ 【{genre}】類型推薦：\n\n"
    for d in matched[:5]:
        info += f"🎬 {d['title']}\n"
        info += f"   人氣：{d.get('views','未知')} | 集數：{d.get('episode','未知')}\n"
        info += f"   更新：星期{d.get('day','?')} {d.get('hour','')}\n\n"
    return info


def handle_detail(anime_name):
    """查詢特定動漫詳情（模糊搜尋）"""
    if not anime_name:
        return "請告訴我你想查哪部動漫的名稱？"

    docs = db.collection("本季新番").get()
    matched = None
    for doc in docs:
        d = doc.to_dict()
        if anime_name in d.get("title", ""):
            matched = d
            break

    if not matched:
        return f"😢 找不到【{anime_name}】的資料\n請確認名稱，或試試其他關鍵字"

    genre_str = "、".join(matched.get("genre", ["其他"]))
    info  = f"📖 {matched['title']}\n\n"
    info += f"🏷 類型：{genre_str}\n"
    info += f"📺 集數：{matched.get('episode','未知')}\n"
    info += f"👁 人氣：{matched.get('views','未知')}\n"
    info += f"🕐 更新：星期{matched.get('day','?')} {matched.get('hour','')}\n"
    if matched.get("link"):
        info += f"🔗 {matched['link']}\n"
    return info


def handle_ranking():
    """熱門排行榜前10名"""
    docs = db.collection("熱門排行").order_by("rank").limit(10).get()

    if not docs:
        # fallback：從本季新番排序
        all_docs = [doc.to_dict() for doc in db.collection("本季新番").get()]
        sorted_docs = sorted(all_docs, key=lambda x: x.get("views_num", 0), reverse=True)[:10]
        info = "🏆 本季人氣排行榜：\n\n"
        for i, d in enumerate(sorted_docs, 1):
            info += f"  第{i}名 {d.get('title','未知')} ({d.get('views','未知')})\n"
        return info

    info = "🏆 本季人氣排行榜：\n\n"
    for doc in docs:
        d = doc.to_dict()
        info += f"  第{d.get('rank','?')}名 {d.get('title','未知')} ({d.get('views','未知')})\n"
    return info


def handle_random():
    """隨機推薦一部"""
    all_docs = [doc.to_dict() for doc in db.collection("本季新番").get()]
    if not all_docs:
        return "目前沒有資料可推薦 😢"

    pick = random.choice(all_docs)
    genre_str = "、".join(pick.get("genre", ["其他"]))

    info  = "🎲 隨機推薦！\n\n"
    info += f"🎌 {pick.get('title','未知')}\n"
    info += f"🏷 類型：{genre_str}\n"
    info += f"📺 集數：{pick.get('episode','未知')}\n"
    info += f"👁 人氣：{pick.get('views','未知')}\n"
    info += f"🕐 更新：星期{pick.get('day','?')} {pick.get('hour','')}\n"
    if pick.get("link"):
        info += f"🔗 {pick['link']}\n"
    info += "\n快去看看吧！🍿"
    return info


# ──────────────────────────────────────────
# 啟動
# ──────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)