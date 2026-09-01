import json
import requests
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from utils import modules_help, prefix

def google_translate(query, source_lang="auto", target_lang="en"):
    url = "https://translate-pa.googleapis.com/v1/translateHtml"
    payload = json.dumps([[[query], source_lang, target_lang], "te_lib"])
    headers = {
        "Content-Type": "application/json+protobuf",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Referer": "https://translate.google.com/",
        "x-goog-api-key": "AIzaSyATBXajvzQLTDHEQbcpq0Ihe0vWDHmO520",
    }
    response = requests.post(url, data=payload, headers=headers)
    if response.status_code == 200:
        response.encoding = "utf-8"
        data = response.json()
        translated_text = "".join(data[0])
        detected_lang = data[1][0] if len(data) > 1 and data[1] else source_lang
        return translated_text, detected_lang
    else:
        raise Exception(f"Failed to fetch translation ({response.status_code}): {response.text[:200]}")

@Client.on_message(filters.command(["tr"], prefix))
async def translate_text(client, message: Message):
    args = message.text.split(maxsplit=2)
    reply_text = message.reply_to_message.text or message.reply_to_message.caption if message.reply_to_message else None
    if len(args) < 2 and not reply_text:
        usage_message = (
            f"<b>Usage:</b> <code>{prefix}gtr [language] [text]</code>\n"
        )
        await message.edit(usage_message) if message.from_user.is_self else await message.reply(usage_message)
        return

    target_lang = args[1] if len(args) > 1 else "en"
    query = args[2].strip() if len(args) > 2 else ""
    if not query and reply_text:
        query = reply_text.strip()

    if not query:
        await message.reply("No text found to translate.")
        return

    processing_message = await (message.edit("Translating...") if message.from_user.is_self else message.reply("Translating..."))

    try:
        translated_text, detected_lang = google_translate(query, target_lang=target_lang)
        await processing_message.edit(
            f"**Translated Text ({detected_lang.upper()} → {target_lang.upper()}):**\n{translated_text}",
            parse_mode=enums.ParseMode.MARKDOWN,
        )
    except Exception as e:
        await processing_message.edit(f"Failed to translate the text: {str(e)}")

modules_help["translate"] = {
    "tr [language] [text]": "Translate the provided text to the specified language."
}
