from flask import Flask, request, jsonify, make_response
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
# 類型同義詞對照
# ──────────────────────────────────────────
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


def normalize_genre(genre_input: str) -> str:
    return GENRE_ALIAS.get(genre_input.strip(), genre_input.strip())


def get_all_anime():
    """讀取本季新番 collection 全部資料"""
    return [doc.to_dict() for doc in db.collection("本季新番").get()]


# ──────────────────────────────────────────
# 網頁路由
# ──────────────────────────────────────────
@app.route("/")
def index():
    R  = "<h1>歡迎進入動畫推薦網站 🎌</h1>"
    R += "<a href='/all'>查看全部動畫</a><br><hr>"
    R += "<a href='/hot'>近期熱播排行</a><br><hr>"
    R += "<a href='/new'>本季新番</a><br><hr>"
    R += "<a href='/newArrive'>新上架</a><br><hr>"
    R += "<a href='/expire'>⚠️ 本月授權到期</a><br><hr>"
    R += "<a href='/random'>隨機推薦動畫</a><br><hr>"
    R += "<a href='/search'>查詢動漫</a><br><hr>"
    return R


@app.route("/all")
def all_anime():
    R = "<h1>全部動畫</h1>"
    R += "<a href='/'>← 回首頁</a><br><hr>"
    for d in get_all_anime():
        genre_str = "、".join(d.get("genre", ["其他"]))
        R += f"<b>{d.get('title','未知')}</b>　類型：{genre_str}　年份：{d.get('year','')}　"
        R += f"集數：{d.get('episode','未知')}　人氣：{d.get('views','未知')}<br>"
        if d.get("link"):
            R += f"<a href='{d['link']}' target='_blank'>▶ 前往觀看</a>"
        R += "<hr>"
    return R


@app.route("/hot")
def hot():
    R = "<h1>近期熱播 🔥</h1>"
    R += "<a href='/'>← 回首頁</a><br><hr>"
    docs = db.collection("熱門排行").order_by("rank").limit(10).get()
    if docs:
        for doc in docs:
            d = doc.to_dict()
            R += f"第{d.get('rank','?')}名　<b>{d.get('title','未知')}</b>　人氣：{d.get('views','未知')}<br>"
            if d.get("link"):
                R += f"<a href='{d['link']}' target='_blank'>▶ 前往觀看</a>"
            R += "<hr>"
    else:
        data = sorted(
            [d for d in get_all_anime() if d.get("source") == "近期熱播"],
            key=lambda x: x.get("views_num", 0), reverse=True
        )
        for i, d in enumerate(data, 1):
            R += f"第{i}名　<b>{d.get('title','未知')}</b>　人氣：{d.get('views','未知')}<br>"
            if d.get("link"):
                R += f"<a href='{d['link']}' target='_blank'>▶ 前往觀看</a>"
            R += "<hr>"
    return R


@app.route("/new")
def new_anime():
    R = "<h1>本季新番 🎌</h1>"
    R += "<a href='/'>← 回首頁</a><br><hr>"
    data = [d for d in get_all_anime() if d.get("source") == "本季新番"]
    for d in data:
        genre_str = "、".join(d.get("genre", ["其他"]))
        R += f"<b>{d.get('title','未知')}</b>　類型：{genre_str}<br>"
        R += f"更新：星期{d.get('day','?')} {d.get('hour','')}　集數：{d.get('episode','未知')}<br>"
        if d.get("link"):
            R += f"<a href='{d['link']}' target='_blank'>▶ 前往觀看</a>"
        R += "<hr>"
    return R


@app.route("/newArrive")
def new_arrive():
    R = "<h1>新上架 🆕</h1>"
    R += "<a href='/'>← 回首頁</a><br><hr>"
    data = [d for d in get_all_anime() if d.get("source") == "新上架"]
    for d in data:
        genre_str = "、".join(d.get("genre", ["其他"]))
        R += f"<b>{d.get('title','未知')}</b>　類型：{genre_str}<br>"
        R += f"集數：{d.get('episode','未知')}　人氣：{d.get('views','未知')}<br>"
        if d.get("link"):
            R += f"<a href='{d['link']}' target='_blank'>▶ 前往觀看</a>"
        R += "<hr>"
    return R


@app.route("/expire")
def expire():
    R = "<h1>⚠️ 本月授權到期節目</h1>"
    R += "<a href='/'>← 回首頁</a><br>"
    R += "<p style='color:red'>以下節目即將下架，把握時間看完！</p><hr>"
    data = [d for d in get_all_anime() if d.get("source") == "授權到期"]
    if not data:
        R += "目前沒有授權到期的節目資料"
        return R
    for d in data:
        genre_str = "、".join(d.get("genre", ["其他"]))
        R += f"<b>{d.get('title','未知')}</b>　類型：{genre_str}<br>"
        R += f"年份：{d.get('year','')}　集數：{d.get('episode','未知')}　人氣：{d.get('views','未知')}<br>"
        if d.get("link"):
            R += f"<a href='{d['link']}' target='_blank'>▶ 前往觀看</a>"
        R += "<hr>"
    return R


@app.route("/random")
def random_anime():
    all_docs = get_all_anime()
    R = "<h1>隨機推薦動畫 🎲</h1>"
    R += "<a href='/'>← 回首頁</a>　<a href='/random'>再推薦一部</a><br><hr>"
    if not all_docs:
        R += "目前沒有資料"
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
    results = [d for d in get_all_anime() if keyword in d.get("title", "")]
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
# Dialogflow Webhook
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
    elif action == "random_recommend" or action == "random_again":
        info = handle_random()
    elif action == "expiring":
        info = handle_expiring()
    elif action == "ranking_detail":
        rank_num = parameters.get("rank", 1)
        info = handle_ranking_detail(rank_num)
    else:
        info = (
            "你好！我是巴哈動漫小精靈 🎌\n\n"
            "你可以問我：\n"
            "・本季有哪些新番？\n"
            "・推薦奇幻類動漫\n"
            "・告訴我更多關於[動漫名稱]\n"
            "・熱門排行榜\n"
            "・隨機推薦一部\n"
            "・本月授權到期有哪些？"
        )
    return make_response(jsonify({"fulfillmentText": info}))


# ──────────────────────────────────────────
# Webhook 處理函式
# ──────────────────────────────────────────
def handle_new_season():
    all_docs = get_all_anime()
    season = [d for d in all_docs if d.get("source") == "本季新番"][:5]
    new    = [d for d in all_docs if d.get("source") == "新上架"][:3]
    if not season and not new:
        return "目前資料庫還沒有資料，請先更新！"
    info = "🎌 本季新番：\n"
    info += "─────────────\n"
    for d in season:
        genre_str = "、".join(d.get("genre", ["其他"]))
        info += f"\n📺 {d['title']}\n"
        info += f"🏷 類型：{genre_str}\n"
        info += f"🕐 更新：星期{d.get('day','?')} {d.get('hour','')}\n"
        if d.get("link"):
            info += f"🔗 {d['link']}\n"
        info += "──────────────\n"
    if new:
        info += "\n🆕 新上架：\n"
        info += "─────────────\n"
        for d in new:
            info += f"\n📺 {d['title']}\n"
            info += f"📦 集數：{d.get('episode','未知')}\n"
            if d.get("link"):
                info += f"🔗 {d['link']}\n"
            info += "──────────────\n"
    info += "\n想查詳情輸入動漫名稱 😊"
    return info


def handle_by_genre(genre):
    if not genre:
        return "請告訴我你想看哪種類型？\n例如：異世界、戀愛、戰鬥、校園、科幻、奇幻、懸疑、運動"
    matched = [d for d in get_all_anime() if genre in d.get("genre", [])]
    if not matched:
        return f"😢 目前沒有找到【{genre}】類型的動漫\n試試：異世界、戀愛、戰鬥、奇幻"
    info = f"✨ 【{genre}】類型推薦：\n"
    info += "─────────────\n"
    for d in matched[:5]:
        info += f"\n🎬 {d['title']}\n"
        info += f"👁 人氣：{d.get('views','未知')}\n"
        info += f"📦 集數：{d.get('episode','未知')}\n"
        if d.get("link"):
            info += f"🔗 {d['link']}\n"
        info += "──────────────\n"
    return info


def handle_detail(anime_name):
    if not anime_name:
        return "請告訴我你想查哪部動漫的名稱？"
    matched = next((d for d in get_all_anime() if anime_name in d.get("title", "")), None)
    if not matched:
        return f"😢 找不到【{anime_name}】的資料\n請確認名稱，或試試其他關鍵字"
    genre_str = "、".join(matched.get("genre", ["其他"]))
    info  = f"📖 {matched['title']}\n"
    info += "─────────────\n"
    info += f"🏷 類型：{genre_str}\n"
    info += f"📦 集數：{matched.get('episode','未知')}\n"
    info += f"👁 人氣：{matched.get('views','未知')}\n"
    if matched.get("day"):
        info += f"🕐 更新：星期{matched.get('day','?')} {matched.get('hour','')}\n"
    if matched.get("link"):
        info += f"🔗 {matched['link']}\n"
    return info


def handle_ranking():
    docs = db.collection("熱門排行").order_by("rank").limit(10).get()
    if not docs:
        data = sorted(
            [d for d in get_all_anime() if d.get("source") == "近期熱播"],
            key=lambda x: x.get("views_num", 0), reverse=True
        )[:10]
        info = "🏆 本季人氣排行榜：\n"
        info += "─────────────\n"
        for i, d in enumerate(data, 1):
            info += f"\n🥇 第{i}名 {d.get('title','未知')}\n"
            info += f"👁 人氣：{d.get('views','未知')}\n"
            if d.get("link"):
                info += f"🔗 {d['link']}\n"
            info += "──────────────\n"
        return info
    info = "🏆 本季人氣排行榜：\n"
    info += "─────────────\n"
    for doc in docs:
        d = doc.to_dict()
        info += f"\n🥇 第{d.get('rank','?')}名 {d.get('title','未知')}\n"
        info += f"👁 人氣：{d.get('views','未知')}\n"
        if d.get("link"):
            info += f"🔗 {d['link']}\n"
        info += "──────────────\n"
    return info


def handle_random():
    all_docs = get_all_anime()
    if not all_docs:
        return "目前沒有資料可推薦 😢"
    pick = random.choice(all_docs)
    genre_str = "、".join(pick.get("genre", ["其他"]))
    info  = "🎲 隨機推薦！\n─────────────\n"
    info += f"🎌 {pick.get('title','未知')}\n"
    info += f"🏷 類型：{genre_str}\n"
    info += f"📦 集數：{pick.get('episode','未知')}\n"
    info += f"👁 人氣：{pick.get('views','未知')}\n"
    if pick.get("day"):
        info += f"🕐 更新：星期{pick.get('day','?')} {pick.get('hour','')}\n"
    if pick.get("link"):
        info += f"🔗 {pick['link']}\n"
    info += "\n快去看看吧！🍿"
    return info


def handle_ranking_detail(rank_num):
    """排行榜第N名詳情"""
    try:
        rank = int(float(str(rank_num))) if rank_num else 1
    except:
        rank = 1
    if rank < 1 or rank > 10:
        return "只能查詢第1名到第10名喔 😊"
    doc_id = f"rank_{rank:02d}"
    doc = db.collection("熱門排行").document(doc_id).get()
    if not doc.exists:
        return f"找不到第{rank}名的資料 😢"
    d = doc.to_dict()
    genre_str = "、".join(d.get("genre", ["其他"]))
    info  = f"🏆 人氣第{rank}名─────────────"
    info += f"🎌 {d.get('title','未知')}"
    info += f"🏷 類型：{genre_str}"
    info += f"👁 人氣：{d.get('views','未知')}"
    info += f"📦 集數：{d.get('episode','未知')}"
    if d.get("link"):
        info += f"🔗 {d['link']}"
    return info


def handle_expiring():
    data = [d for d in get_all_anime() if d.get("source") == "授權到期"]
    if not data:
        return "目前沒有授權到期的節目資料 😊"
    info = "⚠️ 本月即將下架節目：\n"
    info += "─────────────\n"
    for d in data[:8]:
        genre_str = "、".join(d.get("genre", ["其他"]))
        info += f"\n📺 {d.get('title','未知')}\n"
        info += f"🏷 類型：{genre_str}\n"
        info += f"👁 人氣：{d.get('views','未知')}\n"
        if d.get("link"):
            info += f"🔗 {d['link']}\n"
        info += "──────────────\n"
    info += "\n把握時間快去看完吧！⏰"
    return info


if __name__ == "__main__":
    app.run(debug=True, port=5000)
