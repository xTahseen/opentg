import re
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.misc import modules_help, prefix
from utils.db import db

NS = "custom.dm"


def _chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


async def _save_sent_message(client: Client, message: Message):
    if not message:
        return
    enabled = db.get(NS, "enabled", False)
    if not enabled:
        return
    me = await client.get_me()
    if message.chat.id == me.id:
        return
    chat_id = str(message.chat.id)
    msg_ids = db.get(NS, f"media:{chat_id}", [])
    msg_ids.append(message.id)
    db.set(NS, f"media:{chat_id}", msg_ids)
    chats = db.get(NS, "chats", [])
    if chat_id not in chats:
        chats.append(chat_id)
        db.set(NS, "chats", chats)


@Client.on_message(filters.me & filters.media & ~filters.bot & ~filters.channel & ~filters.group)
async def store_my_media(client: Client, message: Message):
    if message.chat.id == (await client.get_me()).id:
        return
    enabled = db.get(NS, "enabled", False)
    if not enabled:
        return
    chat_id = str(message.chat.id)
    msg_ids = db.get(NS, f"media:{chat_id}", [])
    msg_ids.append(message.id)
    db.set(NS, f"media:{chat_id}", msg_ids)
    chats = db.get(NS, "chats", [])
    if chat_id not in chats:
        chats.append(chat_id)
        db.set(NS, "chats", chats)


@Client.on_message(filters.me & filters.command(["dm"], prefix))
async def handle_dm(client: Client, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        arg = args[1].lower()
        if arg == "on":
            db.set(NS, "enabled", True)
            await message.edit("Media <b>ON</b>")
            return
        elif arg == "off":
            db.set(NS, "enabled", False)
            await message.edit("Media <b>OFF</b>")
            return
    chats = db.get(NS, "chats", [])
    if not chats:
        await message.edit("No media.")
        return
    await message.edit("Cleaning...")
    total_deleted = 0
    total_chats = 0
    for chat_id in list(chats):
        msg_ids = db.get(NS, f"media:{chat_id}", [])
        if not msg_ids:
            db.remove(NS, f"media:{chat_id}")
            continue
        per_chat_deleted = 0
        for chunk in _chunked(msg_ids, 30):
            try:
                await client.delete_messages(int(chat_id), chunk)
                per_chat_deleted += len(chunk)
            except Exception as e:
                print(f"Failed deleting in chat {chat_id}, chunk {chunk[:3]}... -> {e}")
        db.remove(NS, f"media:{chat_id}")
        if per_chat_deleted:
            total_chats += 1
            total_deleted += per_chat_deleted
    db.set(NS, "chats", [])
    await message.edit(f"Deleted <b>{total_deleted}</b> in <b>{total_chats}</b> chats.")


@Client.on_message(filters.me & filters.regex(rf"^{re.escape(prefix)}s\d+$"))
async def media_slot(client: Client, message: Message):
    slot = message.text[len(prefix):]

    if message.reply_to_message:
        m = message.reply_to_message
        db.set(NS, slot, {"chat_id": m.chat.id, "message_id": m.id})
        await message.edit(f"Saved media in <b>{slot}</b>")
        return

    saved = db.get(NS, slot, None)
    if not saved:
        await message.edit(f"Empty <b>{slot}</b>")
        return

    chat_id = saved.get("chat_id")
    msg_id = saved.get("message_id")

    try:
        sent_msg = await client.copy_message(
            chat_id=message.chat.id,
            from_chat_id=chat_id,
            message_id=msg_id
        )
    except Exception as e:
        await message.edit("Send failed")
        print(f"send failed for slot {slot}: {e}")
        return

    await _save_sent_message(client, sent_msg)
    await message.delete()


modules_help["dm"] = {
    "dm on": "Enable storing outgoing media.",
    "dm off": "Disable storing outgoing media.",
    "dm": "Delete all stored media globally.",
    "s1, s2, ...": "Reply with media to save, or reuse slot.",
}
