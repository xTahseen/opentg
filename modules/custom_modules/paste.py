import requests
from pyrogram import Client, filters
from pyrogram.types import Message
from utils import modules_help, prefix


API_URL = "https://snippeted.vercel.app/api/paste"


async def create_paste(text, filename="snippet.txt", duration="1d"):
    try:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"

        lang_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "html": "html",
            "css": "css",
            "json": "json",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "go": "go",
            "rs": "rust",
            "php": "php",
            "txt": "plaintext"
        }

        payload = {
            "content": text,
            "language": lang_map.get(ext, "plaintext"),
            "name": filename,
            "duration": duration
        }

        r = requests.post(API_URL, json=payload, timeout=20)
        r.raise_for_status()

        return r.json()

    except Exception as e:
        return {"error": str(e)}


async def get_text_from_message(message):
    reply = message.reply_to_message

    if reply:
        text = reply.text or reply.caption

        if not text and reply.document:
            try:
                path = await reply.download()

                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()

            except Exception as e:
                return None, None, f"<b>Error reading document: {e}</b>"

            return text, reply.document.file_name, None

        return text, "snippet.txt", None

    args = message.text.split(maxsplit=2)

    if len(args) < 2:
        return None, None, "<b>No text found to paste</b>"

    return args[-1], "snippet.txt", None


@Client.on_message(filters.command("paste", prefix) & filters.me)
async def paste_cmd(_, message: Message):
    text, filename, error = await get_text_from_message(message)

    if error:
        await message.edit(error)
        return

    result = await create_paste(text, filename)

    if result.get("error"):
        await message.edit(
            f"<b>Paste failed:</b>\n<code>{result['error']}</code>"
        )
        return

    await message.edit(
        f"<b>Pasted to Snippted</b>\n"
        f"• <a href='{result['viewUrl']}'><b>View</b></a>\n"
        f"• <a href='{result['rawUrl']}'><b>Raw</b></a>\n",
        disable_web_page_preview=True
    )


modules_help["paste"] = {
    "Paste [text/reply]": "Upload text to Snippet Editor"
}
