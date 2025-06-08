from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# 環境変数読み込み
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
GAS_URL = os.getenv("GAS_URL")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# エピソード読み込み
with open("line_novel_episode_data_FULL_1to20_FINAL.json", encoding="utf-8") as f:
    episodes = json.load(f)

# GASでプレミアムチェック（スプレッドシートにuserIdがあれば1）
def is_premium_user(user_id):
    try:
        res = requests.get(GAS_URL, params={"userId": user_id})
        return res.text.strip() == "1"
    except:
        return False

# GASにuserIdを登録（合言葉が正しいときのみ）
def register_premium_user(user_id, keyword):
    try:
        payload = {"userId": user_id, "keyword": keyword}
        requests.post(GAS_URL, json=payload)
    except:
        pass

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 🔐 合言葉でプレミアム解除
    if text == "unlock2024":
        register_premium_user(user_id, text)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ プレミアム解除されました。6話以降も読めるようになりました！")
        )
        return

    # 話数選択
    if text.isdigit():
        episode_num = int(text)

        if 1 <= episode_num <= 20:
            if episode_num > 5 and not is_premium_user(user_id):
                reply = [
                    TextSendMessage(text=f"第{episode_num}話はプレミアム限定です。"),
                    TextSendMessage(text="続きを読むにはこちら👇"),
                    TextSendMessage(text="https://note.com/あなたのアカウント名/n/note_id")
                ]
                line_bot_api.reply_message(event.reply_token, reply)
                return

            key = str(episode_num)
            if key in episodes:
                messages = [TextSendMessage(text=msg) for msg in episodes[key]]
                line_bot_api.reply_message(event.reply_token, messages)
                return

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="1〜20の数字で話数を指定してね。"))

    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="読みたい話の番号（1〜20）か、合言葉を送ってね。"))
