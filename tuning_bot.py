from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import json
import re
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET       = os.getenv("CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler      = WebhookHandler(LINE_CHANNEL_SECRET)

# プレミアム判定用 GAS エンドポイント（必要に応じて変更）
GAS_URL = "https://script.google.com/macros/s/AKfycbyxTlfH6bMA8eADWYJ4ApnGn-R45mxXM2EKQw8-EdzTvpCMKISoCpsvjSaoKzsVJoa8tQ/exec"

# JSONファイルからストーリー読み込み（リスト形式）
with open("tuning_kimi_ni_awasete_episode_data_FULL_1to20.json", encoding="utf-8") as f:
    raw_data = json.load(f)

# list→dict へ変換。キーは話数の文字列 "1"〜"20" に
# 値は {"subtitle": "...", "texts": [...]} の形で格納
story_data = {}
for ep in raw_data:
    num = ep.get("episode")
    if num is None:
        continue
    # サブタイトルを取る
    subtitle = ep.get("subtitle") or ep.get("title") or ""
    # 本文は texts or messages or lines
    texts = ep.get("texts") or ep.get("messages") or ep.get("lines") or []
    story_data[str(num)] = {"subtitle": subtitle, "texts": texts}

print("読み込んだ話数：", list(story_data.keys()))

@app.route("/callback", methods=["POST"])
def callback():
    # Webhook受信時には必ず 200 を返す
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    print("=== Webhook受信 ===", body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK", 200

def is_premium_user(user_id: str) -> bool:
    try:
        resp = requests.get(GAS_URL, params={"user_id": user_id}, timeout=5)
        return resp.json().get("exists", False)
    except:
        return False

def register_premium_user(user_id: str):
    try:
        requests.post(GAS_URL, json={"user_id": user_id}, timeout=5)
    except:
        pass

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    print("=== メッセージ受信 ===", event.message.text)
    user_msg = event.message.text.strip()
    user_id  = event.source.user_id

    # プレミアム解放コード
    if user_msg == "tuning_2025_unlock":
        register_premium_user(user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ プレミアム解放完了！第6話以降が読めるようになりました。")
        )
        return

    # 数字のみマッチ
    m = re.fullmatch(r"(\d{1,2})", user_msg)
    if not m:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="『3』のように数字で話数を送ってください。")
        )
        return

    num = m.group(1)
    if num not in story_data:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"{num}話は存在しません。1〜20の数字を送ってください。")
        )
        return

    # プレミアム制御
    if int(num) > 5 and not is_premium_user(user_id):
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🔒 第6話以降はプレミアム限定です。\nhttps://note.com/loyal_cosmos1726/n/nefdff71e226fから解放コードを取得してください。")
        )
        return

    # 話数を返す（サブタイトル→本文）
    ep = story_data[num]
    msgs = []
    # サブタイトルがあれば最初の吹き出し
    if ep["subtitle"]:
        msgs.append(TextSendMessage(text=ep["subtitle"]))
    # 本文（吹き出し２〜５）
    for line in ep["texts"]:
        msgs.append(TextSendMessage(text=line))

    line_bot_api.reply_message(event.reply_token, msgs)

# 本番環境は gunicorn で起動するため、ここはコメントアウト
# if __name__ == "__main__":
#     port = int(os.environ.get("PORT", 10000))
#     app.run(host="0.0.0.0", port=port)
