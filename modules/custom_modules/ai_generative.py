import os
import time
from PIL import Image
import google.generativeai as genai
from pyrogram import Client, filters, enums
from utils.misc import modules_help, prefix
from utils.scripts import format_exc
from utils.config import gemini_key

genai.configure(api_key=gemini_key)
model = genai.GenerativeModel("gemini-1.5-flash-latest")
model_cook = genai.GenerativeModel(
    model_name="gemini-1.5-flash-latest",
    generation_config={"temperature": 0.35, "top_p": 0.95, "top_k": 40, "max_output_tokens": 1024},
)

async def process_file(message, prompt, model_to_use, file_type, status_msg, display_prompt=False):
    """Processes files (image, audio, video) and interacts with Generative AI."""
    await message.edit_text(f"<code>{status_msg}</code>")
    reply = message.reply_to_message

    if not reply:
        return await message.edit_text(f"<b>Usage:</b> <code>{prefix}{message.command[0]} [custom prompt]</code> [Reply to a {file_type}]")

    file_path = await reply.download()
    if not file_path or not os.path.exists(file_path):
        return await message.edit_text("<code>Failed to process the file. Try again.</code>")

    try:
        if file_type == "image" and reply.photo:
            with Image.open(file_path) as img:
                img.verify()
                input_data = [prompt, img]

        elif file_type in ["audio", "video"] and (reply.audio or reply.voice or reply.video or reply.video_note):
            uploaded_file = genai.upload_file(file_path)
            while uploaded_file.state.name == "PROCESSING":
                await message.edit_text("<code>Umm, processing...</code>")
                time.sleep(5)
                uploaded_file = genai.get_file(uploaded_file.name)

            if uploaded_file.state.name == "FAILED":
                return await message.edit_text("<code>File processing failed. Please try again.</code>")
            
            input_data = [uploaded_file, prompt]

        else:
            return await message.edit_text(f"<code>Invalid {file_type} file. Please try again.</code>")

        response = model_to_use.generate_content(input_data)

        result_text = f"**Prompt:** {prompt}\n" if display_prompt else ""
        result_text += f"**Answer:** {response.text}"
        await message.edit_text(result_text, parse_mode=enums.ParseMode.MARKDOWN)

    except Exception as e:
        await message.edit_text(f"<code>Error:</code> {format_exc(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@Client.on_message(filters.command("getai", prefix) & filters.me)
async def getai(_, message):
    """Analyze an image using Generative AI."""
    prompt = message.text.split(maxsplit=1)[1] if len(message.command) > 1 else "Get details of the image, be accurate as much possible."
    await process_file(message, prompt, model, "image", "Analyzing image...", display_prompt=len(message.command) > 1)

@Client.on_message(filters.command("aicook", prefix) & filters.me)
async def aicook(_, message):
    """Identify food in an image and generate cooking instructions."""
    await process_file(message, "Identify the baked good in the image and provide an accurate recipe.", model_cook, "image", "Cooking...")

@Client.on_message(filters.command("aiseller", prefix) & filters.me)
async def aiseller(_, message):
    """Generate a marketing description for a product."""
    if len(message.command) > 1:
        target_audience = message.text.split(maxsplit=1)[1]
        prompt = f"Generate a marketing description for the product.\nTarget Audience: {target_audience}"
        await process_file(message, prompt, model, "image", "Generating description...", display_prompt=False)
    else:
        await message.edit_text(f"<b>Usage:</b> <code>{prefix}aiseller [target audience]</code> [Reply to a product image]")

@Client.on_message(filters.command(["transcribe", "ts"], prefix) & filters.me)
async def transcribe(_, message):
    """Transcribe or summarize an audio or video file."""
    prompt = message.text.split(maxsplit=1)[1] if len(message.command) > 1 else "Transcribe this file."
    await process_file(message, prompt, model, "audio", "Transcribing...", display_prompt=len(message.command) > 1)

modules_help["generative"] = {
    "getai [custom prompt] [reply to image]*": "Analyze an image using AI.",
    "aicook [reply to image]*": "Identify food and generate cooking instructions.",
    "aiseller [target audience] [reply to image]*": "Generate marketing descriptions for products.",
    "transcribe [custom prompt] [reply to audio/video]*": "Transcribe or summarize an audio or video file.",
}
