import os
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import Message
import google.generativeai as genai
from PIL import Image
from utils.config import gemini_key
from utils.misc import prefix
from utils.scripts import modules_help

genai.configure(api_key=gemini_key)
model = genai.GenerativeModel("gemini-1.5-flash")

def split_message(text, max_length=4000):
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]

async def upload_file(file_path, file_type):
    uploaded_file = genai.upload_file(file_path)
    while uploaded_file.state.name == "PROCESSING":
        await asyncio.sleep(10)
        uploaded_file = genai.get_file(uploaded_file.name)
    if uploaded_file.state.name == "FAILED":
        raise ValueError(f"{file_type.capitalize()} failed to process")
    return uploaded_file

async def prepare_file(reply, file_path, prompt):
    if reply.photo:
        with Image.open(file_path) as img:
            img.verify()
            return [prompt, img]
    elif reply.video or reply.video_note:
        return [prompt, await upload_file(file_path, "video")]
    elif reply.document and file_path.endswith(".pdf"):
        return [prompt, await upload_file(file_path, "PDF")]
    elif reply.audio or reply.voice:
        return [await upload_file(file_path, "audio"), prompt]
    elif reply.document:
        return [await upload_file(file_path, "document"), prompt]
    else:
        raise ValueError("Unsupported file type")

async def process_file(message, prompt, is_custom_prompt):
    reply = message.reply_to_message
    if not reply:
        return await message.edit_text(f"<b>Usage:</b> <code>{prefix}{message.command[0]} [prompt]</code> [Reply to a file]")
    file_path = await reply.download()
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return await message.edit_text("<code>Failed to process the file. Try again.</code>")
    try:
        input_data = await prepare_file(reply, file_path, prompt)
        response = model.generate_content(input_data)
        result_text = (
            (f"**Prompt:** {prompt}\n" if is_custom_prompt else "")
            + f"**Answer:** {response.text}" if response and response.text
            else f"**Prompt:** {prompt}\n<code>No content generated.</code>"
        )
        if len(result_text) > 4000:
            for chunk in split_message(result_text):
                await message.reply_text(chunk, parse_mode=enums.ParseMode.MARKDOWN)
            await message.delete()
        else:
            await message.edit_text(result_text, parse_mode=enums.ParseMode.MARKDOWN)
    except ValueError as e:
        await message.edit_text(f"<code>{str(e)}</code>")
    except Exception as e:
        await message.edit_text(f"Error: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@Client.on_message(filters.command(["process", "pr"], prefix) & filters.me)
async def process_generic_file(_, message):
    args = message.text.split(maxsplit=1)
    is_custom_prompt = len(args) > 1
    prompt = args[1] if is_custom_prompt else "Deeply analyze it, write complete details about it."
    await message.edit_text("<code>Processing file...</code>")
    await process_file(message, prompt, is_custom_prompt)

modules_help["process"] = {
    "process [prompt] [reply to any file]*": "Process any file (image, audio, video, video note, PDF, or document).",
}
