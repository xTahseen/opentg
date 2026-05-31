import requests
from pyrogram import Client, filters
from pyrogram.types import Message
from utils import modules_help, prefix


async def spacebin_paste(text, extension="txt"):
    url = "https://spaceb.in/api/"

    try:
        data = {"content": text}
        files = {"extension": (None, extension)}

        r = requests.post(url, data=data, files=files)
        r.raise_for_status()

        result = r.json()

        if result.get("error"):
            return {"error": result["error"]}

        payload = result.get("payload", {})
        paste_id = payload.get("id")

        if not paste_id:
            return {"error": "No paste ID returned"}

        return {
            "url": f"https://spaceb.in/{paste_id}",
            "raw": f"https://spaceb.in/{paste_id}/raw",
        }

    except Exception as e:
        return {"error": str(e)}


async def get_text_from_message(message):
    reply = message.reply_to_message

    if reply:
        text = reply.text or reply.caption

        if not text and reply.document:
            try:
                doc = await reply.download()

                with open(doc, "r") as f:
                    text = f.read()

            except Exception as e:
                return None, f"<b>Error reading document: {e}</b>"

    else:
        args = message.text.split(maxsplit=1)
        text = args[1] if len(args) > 1 else ""

    if not text:
        return None, "<b>No text found to paste</b>"

    return text, None


@Client.on_message(filters.command("paste", prefix) & filters.me)
async def spacebin_cmd(_, message: Message):
    args = message.text.split(maxsplit=2)

    extension = "txt"

    if len(args) >= 2 and "." in args[1]:
        extension = args[1].split(".", 1)[1]

    text, error = await get_text_from_message(message)

    if error:
        await message.edit(error)
        return

    result = await spacebin_paste(text, extension)

    if "error" in result:
        await message.edit(f"<b>Error: {result['error']}</b>")
        return

    await message.edit(
        f"<b>Pasted to Spacebin:\n"
        f"• <a href='{result['url']}'>Link</a>\n"
        f"• <a href='{result['raw']}'>Raw</a></b>",
        disable_web_page_preview=True,
    )


modules_help["paste"] = {
    "Paste [.ext] [text/reply]": "Paste text to spaceb.in (default ext: txt)",
}
