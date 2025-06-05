import requests
import time
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from utils.misc import modules_help, prefix
from utils.scripts import progress

@Client.on_message(filters.command(["soundcloud", "sc"], prefix))
async def soundcloud_music(client: Client, message: Message):
    chat_id = message.chat.id
    is_self = message.from_user and message.from_user.is_self

    query = (
        message.text.split(maxsplit=1)[1]
        if len(message.command) > 1
        else message.reply_to_message.text
        if message.reply_to_message
        else None
    )

    if not query:
        response = f"<b>Usage:</b> <code>{prefix}scmusic [song name]</code>"
        await (message.edit(response) if is_self else message.reply(response))
        return

    status_message = await message.reply(f"<code>Searching for {query} on SoundCloud...</code>") if not is_self else await message.edit_text(f"<code>Searching for {query} on SoundCloud...</code>")

    try:
        search_result = requests.get(f"https://api.nekorinn.my.id/search/soundcloud?q={query}").json()
        if not (search_result.get("status") and search_result.get("result")):
            raise ValueError("No results found")
    except Exception as e:
        await status_message.edit_text(f"<code>Failed to search: {str(e)}</code>")
        return

    song_details = search_result["result"][0]
    song_title, song_link = song_details["title"], song_details["link"]

    await status_message.edit_text(f"<code>Found: {song_title}</code>\n<code>Fetching download link...</code>")

    try:
        download_result = requests.get(f"https://api.nekorinn.my.id/downloader/soundcloud?url={song_link}").json()
        if not download_result.get("status"):
            raise ValueError("Failed to fetch download link")
    except Exception as e:
        await status_message.edit_text(f"<code>Failed to fetch link: {str(e)}</code>")
        return

    song_download_link = download_result["result"].get("downloadUrl")
    song_thumbnail = download_result["result"].get("thumbnailUrl")

    if not song_download_link or not song_download_link.startswith("http"):
        await status_message.edit_text("<code>Song isn't available for download.</code>")
        return

    await status_message.edit_text(f"<code>Downloading {song_title}...</code>")

    try:
        if song_thumbnail:
            with open(f"{song_title}.jpg", "wb") as thumb_file:
                thumb_file.write(requests.get(song_thumbnail, stream=True).content)
        
        song_response = requests.get(song_download_link, stream=True)
        if "audio" not in song_response.headers.get("Content-Type", ""):
            raise ValueError("Not Found")
        
        with open(f"{song_title}.mp3", "wb") as song_file:
            song_file.write(song_response.content)
    except Exception as e:
        await status_message.edit_text(f"<code>Failed to download: {str(e)}</code>")
        return

    await status_message.edit_text(f"<code>Uploading {song_title}...</code>")

    try:
        c_time = time.time()
        await client.send_audio(
            chat_id,
            f"{song_title}.mp3",
            caption=f"<b>Song Name:</b> {song_title}",
            progress=progress,
            progress_args=(status_message, c_time, f"<code>Uploading {song_title}...</code>"),
            thumb=f"{song_title}.jpg" if os.path.exists(f"{song_title}.jpg") else None,
        )
    except Exception as e:
        await status_message.edit_text(f"<code>Failed to upload: {str(e)}</code>")
        return
    finally:
        for file in [f"{song_title}.jpg", f"{song_title}.mp3"]:
            if os.path.exists(file):
                os.remove(file)

    await status_message.delete()

modules_help["soundcloud"] = {
    "soundcloud": "search, download, and upload songs from SoundCloud"
}
