import asyncio
import os
from pathlib import Path
from pyrogram import Client, enums, filters
from pyrogram.types import Message, Document, Audio, Video, Voice, VideoNote
from gemini_webapi import GeminiClient, GeneratedImage, WebImage
from utils.misc import modules_help, prefix
from utils.db import db

TEMP_IMAGE_DIR = "./temp_gemini_images"
TEMP_FILE_DIR = "./temp_gemini_files"
os.makedirs(TEMP_IMAGE_DIR, exist_ok=True)
os.makedirs(TEMP_FILE_DIR, exist_ok=True)

async def get_client():
    cookie = db.get("custom.gemini", "cookie", None)
    if not cookie:
        raise ValueError("❌ No Gemini cookies set.")
    cookies_parts = cookie.strip().split("|")
    if len(cookies_parts) != 2:
        raise ValueError("❌ Please set cookies as: PSID|1PSIDTS")
    psid, one_psidts = cookies_parts
    client = GeminiClient(secure_1psid=psid, secure_1psidts=one_psidts)
    await client.init()
    return client

@Client.on_message(filters.command(["set_gemini"], prefix))
async def set_gemini(_, message: Message):
    if len(message.command) < 2:
        usage = "<b>Usage:</b> <code>set_gemini PSID|1PSIDTS</code>"
        return await message.edit(usage) if message.from_user.is_self else await message.reply(usage)
    cookies = message.text.split(maxsplit=1)[1]
    db.set("custom.gemini", "cookie", cookies)
    await message.edit("✅ Gemini cookies set successfully.")

@Client.on_message(filters.command(["gemini", "ai"], prefix))
async def gemini_query(app: Client, message: Message):
    if len(message.command) < 2:
        usage = "<b>Usage:</b> <code>gemini [prompt]</code>"
        return await message.edit(usage) if message.from_user.is_self else await message.reply(usage)

    prompt = " ".join(message.command[1:])
    is_self = message.from_user and message.from_user.is_self
    wait_msg = await (message.edit if is_self else message.reply)("<code>Umm, lemme think...</code>")

    try:
        files = []

        if message.reply_to_message:
            replied = message.reply_to_message

            for attr in ["document", "audio", "video", "voice", "video_note"]:
                media_obj = getattr(replied, attr, None)
                if media_obj:
                    filename = getattr(media_obj, "file_name", None)
                    ext_map = {
                        "voice": ".ogg",
                        "video_note": ".mp4",
                        "video": ".mp4",
                        "audio": ".mp3",
                        "document": ".bin",
                    }
                    ext = Path(filename).suffix if filename else ext_map.get(attr, ".bin")
                    path = os.path.join(TEMP_FILE_DIR, f"{media_obj.file_unique_id}{ext}")
                    await replied.download(path)
                    files.append(Path(path))
                    break

            if replied.photo:
                path = os.path.join(TEMP_FILE_DIR, f"{replied.photo.file_unique_id}.jpg")
                await replied.download(path)
                files.append(Path(path))

        client = await get_client()
        response = await client.generate_content(prompt, files=files if files else None)
        response_text = response.text or "❌ No answer found."

        # Edit the "thinking..." message instead of replying
        await wait_msg.edit(
            f"**Question:**\n{prompt}\n\n**Answer:**\n{response_text}",
            parse_mode=enums.ParseMode.MARKDOWN,
        )

        if response.images:
            for i, image in enumerate(response.images):
                try:
                    if isinstance(image, GeneratedImage):
                        file_path = os.path.join(TEMP_IMAGE_DIR, f"gemini_gen_{i}.png")
                        await image.save(path=TEMP_IMAGE_DIR, filename=f"gemini_gen_{i}.png", verbose=True)
                        await app.send_photo(
                            chat_id=message.chat.id,
                            photo=file_path,
                            reply_to_message_id=message.id,
                        )
                    elif isinstance(image, WebImage):
                        await app.send_photo(
                            chat_id=message.chat.id,
                            photo=image.url,
                            reply_to_message_id=message.id,
                        )
                except Exception as e:
                    await app.send_message(
                        chat_id=message.chat.id,
                        text=f"⚠️ Failed to send image {i}: {e}",
                        reply_to_message_id=message.id,
                    )

    except Exception as e:
        await wait_msg.edit(f"❌ Error: {e}")

modules_help["gemini"] = {
    "gemini [prompt]*": "Ask anything from Gemini AI. Supports images, videos, PDFs, voice messages, video notes, etc.",
    "set_gemini [PSID|1PSIDTS]*": "Set Gemini cookies. Use '|' to separate values.",
}
