from pyrogram import Client, filters
from pyrogram.types import Message
from utils.misc import modules_help, prefix
from utils.db import db

NS = "custom.dm"

def _chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]

@Client.on_message(filters.me & filters.media)
async def store_my_media(_, message: Message):
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
            await message.edit("Media collection is now <b>ON</b>.")
            return

        elif arg == "off":
            db.set(NS, "enabled", False)
            await message.edit("Media collection is now <b>OFF</b>.")
            return

    chats = db.get(NS, "chats", [])
    if not chats:
        await message.edit("No stored media found across any chats.")
        return

    await message.edit("Please wait...")

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
    await message.edit(
        f"Deleted <b>{total_deleted}</b> of your media across <b>{total_chats}</b> chats."
    )

modules_help["dm"] = {
    "dm on": "Enable storing your own outgoing media globally.",
    "dm off": "Disable storing your own outgoing media.",
    "dm": "Delete all your stored media across all chats (global).",
}
