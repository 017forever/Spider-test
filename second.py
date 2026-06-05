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
    "異世界": ["異世界", "轉生", "召喚", "穿越", "史萊姆", "魔王", "勇者", "迷宮", "農家", "藥師"],
    "戀愛":   ["戀愛", "婚", "喜歡", "告白", "同居", "青梅", "女友", "男友", "愛", "敗北女角", "女角"],
    "戰鬥":   ["英雄", "戰鬥", "討伐", "獵人", "格鬥", "決戰", "最強", "無敵", "進擊", "巨人", "鬼滅"],
    "校園":   ["學校", "高中", "大學", "學園", "社團", "學生", "班", "青春"],
    "科幻":   ["機器人", "科技", "未來", "宇宙", "石紀", "STONE", "DR.", "賽博"],
    "奇幻":   ["魔法", "精靈", "龍", "騎士", "魔導", "咒術", "芙莉蓮", "魔女"],
    "懸疑":   ["偵探", "推理", "謀殺", "秘密", "真相", "謎", "死亡筆記"],
    "運動":   ["足球", "籃球", "排球", "棒球", "競技", "少年", "網球", "游泳"],
}

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
    return GENRE_ALIAS.get(genre_input.strip(), genre_input.strip())


def parse_theme_item(item):
    """解析近期熱播/新上架卡片"""
    title_tag = item.select_one(".theme-name")
    view_tag  = item.select_one(".show-view-number p")
    img_tag   = item.select_one("img.theme-img")
    ep_tag    = item.select_one(".theme-number")
    href      = item.get("href", "")
    title_str   = title_tag.get_text(strip=True) if title_tag else "未知"
    views_str   = view_tag.get_text(strip=True)  if view_tag  else "0"
    image_str   = img_tag.get("data-src", "")    if img_tag   else ""
    episode_str = ep_tag.get_text(strip=True)    if ep_tag    else "未知"
    link_str    = "https://ani.gamer.com.tw/" + href if href else ""
    return {
        "title":     title_str,
        "episode":   episode_str,
        "views":     views_str,
        "views_num": parse_views(views_str),
        "link":      link_str,
        "image":     image_str,
        "hour":      "",
        "day":       "",
        "genre":     auto_genre(title_str),
    }


# ──────────────────────────────────────────
# 首頁
# ──────────────────────────────────────────
@app.route("/")
def index():
    R  = "<h1>歡迎進入動畫推薦網站</h1>"
    R += "<a href='/crawl'>更新動畫資料</a><br><hr>"
    R += "<a href='/all'>查看全部動畫</a><br><hr>"
    R += "<a href='/hot'>近期熱播排行</a><br><hr>"
    R += "<a href='/new'>本季新番</a><br><hr>"
    R += "<a href='/newArrive'>新上架</a><br><hr>"
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
        R += f"<b>{d.get('title','未知')}</b>　類型：{genre_str}　年份：{d.get('year','')}　"
        R += f"集數：{d.get('episode','未知')}　人氣：{d.get('views','未知')}<br>"
        if d.get("link"):
            R += f"<a href='{d['link']}' target='_blank'>▶ 前往觀看</a>"
        R += "<hr>"
    return R


@app.route("/hot")
def hot():
    all_docs = [doc.to_dict() for doc in db.collection("本季新番").get()]
    data = sorted(
        [d for d in all_docs if d.get("source") == "近期熱播"],
        key=lambda x: x.get("views_num", 0), reverse=True
    )
    R = "<h1>近期熱播 🔥</h1>"
    R += "<a href='/'>← 回首頁</a><br><hr>"
    for i, d in enumerate(data, 1):
        R += f"第{i}名　<b>{d.get('title','未知')}</b>　人氣：{d.get('views','未知')}<br>"
        if d.get("link"):
            R += f"<a href='{d['link']}' target='_blank'>▶ 前往觀看</a>"
        R += "<hr>"
    return R


@app.route("/new")
def new_anime():
    all_docs = [doc.to_dict() for doc in db.collection("本季新番").get()]
    data = [d for d in all_docs if d.get("source") == "本季新番"]
    R = "<h1>本季新番 🎌</h1>"
    R += "<a href='/'>← 回首頁</a><br><hr>"
    for d in data:
        genre_str = "、".join(d.get("genre", ["其他"]))
        R += f"<b>{d.get('title','未知')}</b>　類型：{genre_str}　年份：{d.get('year','')}<br>"
        R += f"更新：星期{d.get('day','?')} {d.get('hour','')}　集數：{d.get('episode','未知')}<br>"
        if d.get("link"):
            R += f"<a href='{d['link']}' target='_blank'>▶ 前往觀看</a>"
        R += "<hr>"
    return R


@app.route("/newArrive")
def new_arrive():
    docs = db.collection("新上架").get()
    R = "<h1>新上架 🆕</h1>"
    R += "<a href='/'>← 回首頁</a><br><hr>"
    for doc in docs:
        d = doc.to_dict()
        genre_str = "、".join(d.get("genre", ["其他"]))
        R += f"<b>{d.get('title','未知')}</b>　類型：{genre_str}<br>"
        R += f"集數：{d.get('episode','未知')}　人氣：{d.get('views','未知')}<br>"
        if d.get("link"):
            R += f"<a href='{d['link']}' target='_blank'>▶ 前往觀看</a>"
        R += "<hr>"
    return R


@app.route("/random")
def random_anime():
    # 從三個 collection 合併後隨機挑一部
    all_docs = (
        [doc.to_dict() for doc in db.collection("本季新番").get()] +
        [doc.to_dict() for doc in db.collection("近期熱播").get()]
    )
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
    if pick.get("day"):
        R += f"更新：星期{pick.get('day','?')} {pick.get('hour','')}<br>"
    if pick.get("link"):
        R += f"<a href='{pick['link']}' target='_blank'>▶ 前往觀看</a>"
    return R


@app.route("/search")
def search():
    keyword = request.args.get("q", "").strip()
    R = "<h1>查詢動漫 🔍</h1>"
    R += "<a href='/'>← 回首頁</a><br><hr>"
    R += f"<form method='get'>關鍵字：<input name='q' value='{keyword}'>"
    R += "<button type='submit'>搜尋</button></form><hr>"
    if not keyword:
        R += "請輸入動漫名稱關鍵字進行搜尋"
        return R
    # 同時搜尋三個 collection
    all_docs = (
        [doc.to_dict() for doc in db.collection("本季新番").get()] +
        [doc.to_dict() for doc in db.collection("近期熱播").get()] +
        [doc.to_dict() for doc in db.collection("新上架").get()]
    )
    # 去除重複標題
    seen = set()
    results = []
    for d in all_docs:
        t = d.get("title", "")
        if keyword in t and t not in seen:
            seen.add(t)
            results.append(d)
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
# 爬蟲路由（本機版專用）GET /crawl
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
    season_count = hot_count = new_count = 0
    hot_list = []

    # 1. 本季新番
    newanime_block = soup.select_one("#blockVideoInSeason")
    if newanime_block:
        for item in newanime_block.select(".newanime-date-area"):
            title_tag  = item.select_one(".anime-name")
            ep_tag     = item.select_one(".anime-episode p")
            view_tag   = item.select_one(".anime-watch-number p")
            link_tag   = item.select_one("a.anime-card-block")
            img_tag    = item.select_one(".anime-blocker img")
            hour_tag   = item.select_one(".anime-hours")
            day_code   = item.get("data-date-code", "7")
            animesn    = item.get("data-animesn", "")
            title_str   = title_tag.get_text(strip=True)  if title_tag  else "未知"
            episode_str = ep_tag.get_text(strip=True)     if ep_tag     else "未知"
            views_str   = view_tag.get_text(strip=True)   if view_tag   else "0"
            link_str    = "https://ani.gamer.com.tw/" + link_tag["href"] if link_tag else ""
            image_str   = img_tag.get("data-src", "")     if img_tag    else ""
            hour_str    = hour_tag.get_text(strip=True)   if hour_tag   else ""
            day_str     = DAY_MAP.get(day_code, "未定")
            doc = {
                "title": title_str, "episode": episode_str,
                "views": views_str, "views_num": parse_views(views_str),
                "link": link_str, "image": image_str,
                "hour": hour_str, "day": day_str,
                "animesn": animesn, "genre": auto_genre(title_str),
            }
            db.collection("本季新番").document(title_str).set(doc)
            season_count += 1

    # 2. 近期熱播
    hot_block = soup.select_one("#blockHotAnime")
    if hot_block:
        for item in hot_block.select("a.theme-list-main"):
            doc = parse_theme_item(item)
            db.collection("近期熱播").document(doc["title"]).set(doc)
            hot_list.append(doc)
            hot_count += 1

    # 熱門排行
    for rank, anime in enumerate(
        sorted(hot_list, key=lambda x: x["views_num"], reverse=True)[:10], 1
    ):
        anime["rank"] = rank
        db.collection("熱門排行").document(f"rank_{rank:02d}").set(anime)

    # 3. 新上架
    new_block = soup.select_one("#blockAnimeNewArrive")
    if new_block:
        for item in new_block.select("a.theme-list-main"):
            doc = parse_theme_item(item)
            db.collection("新上架").document(doc["title"]).set(doc)
            new_count += 1

    return f"爬蟲完畢！本季新番:{season_count} 近期熱播:{hot_count} 新上架:{new_count}"


# ──────────────────────────────────────────
# Dialogflow Webhook  POST /webhook
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
        genre = normalize_genre(parameters.get("genre", ""))
        info = handle_by_genre(genre)
    elif action == "detail":
        info = handle_detail(parameters.get("anime_name", ""))
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


def handle_new_season():
    docs = db.collection("本季新番").limit(8).get()
    if not docs:
        return "目前資料庫還沒有本季新番資料！"
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
    if not genre:
        return "請告訴我你想看哪種類型？\n例如：異世界、戀愛、戰鬥、校園、科幻、奇幻、懸疑、運動"
    # 同時搜尋本季新番和近期熱播
    all_docs = (
        [doc.to_dict() for doc in db.collection("本季新番").get()] +
        [doc.to_dict() for doc in db.collection("近期熱播").get()]
    )
    seen = set()
    matched = []
    for d in all_docs:
        t = d.get("title", "")
        if genre in d.get("genre", []) and t not in seen:
            seen.add(t)
            matched.append(d)
    if not matched:
        return f"😢 目前沒有找到【{genre}】類型的動漫\n試試：異世界、戀愛、戰鬥、奇幻"
    info = f"✨ 【{genre}】類型推薦：\n\n"
    for d in matched[:5]:
        info += f"🎬 {d['title']}\n"
        info += f"   人氣：{d.get('views','未知')} | 集數：{d.get('episode','未知')}\n\n"
    return info


def handle_detail(anime_name):
    if not anime_name:
        return "請告訴我你想查哪部動漫的名稱？"
    all_docs = (
        [doc.to_dict() for doc in db.collection("本季新番").get()] +
        [doc.to_dict() for doc in db.collection("近期熱播").get()]
    )
    matched = next((d for d in all_docs if anime_name in d.get("title", "")), None)
    if not matched:
        return f"😢 找不到【{anime_name}】的資料\n請確認名稱，或試試其他關鍵字"
    genre_str = "、".join(matched.get("genre", ["其他"]))
    info  = f"📖 {matched['title']}\n\n"
    info += f"🏷 類型：{genre_str}\n"
    info += f"📺 集數：{matched.get('episode','未知')}\n"
    info += f"👁 人氣：{matched.get('views','未知')}\n"
    if matched.get("day"):
        info += f"🕐 更新：星期{matched.get('day','?')} {matched.get('hour','')}\n"
    if matched.get("link"):
        info += f"🔗 {matched['link']}\n"
    return info


def handle_ranking():
    docs = db.collection("熱門排行").order_by("rank").limit(10).get()
    if not docs:
        all_docs = [doc.to_dict() for doc in db.collection("近期熱播").get()]
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
    all_docs = (
        [doc.to_dict() for doc in db.collection("本季新番").get()] +
        [doc.to_dict() for doc in db.collection("近期熱播").get()]
    )
    if not all_docs:
        return "目前沒有資料可推薦 😢"
    pick = random.choice(all_docs)
    genre_str = "、".join(pick.get("genre", ["其他"]))
    info  = "🎲 隨機推薦！\n\n"
    info += f"🎌 {pick.get('title','未知')}\n"
    info += f"🏷 類型：{genre_str}\n"
    info += f"📺 集數：{pick.get('episode','未知')}\n"
    info += f"👁 人氣：{pick.get('views','未知')}\n"
    if pick.get("link"):
        info += f"🔗 {pick['link']}\n"
    info += "\n快去看看吧！🍿"
    return info


if __name__ == "__main__":
    app.run(debug=True, port=5000)