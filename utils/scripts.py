#  Moon-Userbot - telegram userbot
#  Copyright (C) 2020-present Moon Userbot Organization
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import importlib
import math
import os
import re
import shlex
import subprocess
import sys
import time
import traceback
from PIL import Image
from io import BytesIO
from types import ModuleType
from typing import Dict, Tuple

import logging
import psutil

# Install robust wrapper for Dispatcher.remove_handler as early as possible.
# This ensures the loader's remove_handler calls will use the patched behavior.
try:
    import pyrogram.dispatcher as _py_disp
    _orig_remove_handler = getattr(_py_disp.Dispatcher, "remove_handler", None)

    if _orig_remove_handler is not None:
        _log = logging.getLogger("scripts.remove_handler")

        def _robust_remove_handler(self, handler, group=None):
            """
            Try original remove_handler(self, handler, group).
            If it raises ValueError because the handler is not in the specified group,
            search all groups for identity match and remove it where found.
            If not found anywhere, re-raise ValueError to preserve behavior.
            """
            try:
                return _orig_remove_handler(self, handler, group)
            except ValueError as ve:
                _log.warning(
                    "Dispatcher.remove_handler: handler not found in group=%r, attempting global search. handler id=%s repr=%s",
                    group, id(handler), repr(handler),
                )
                groups_attr = getattr(self, "groups", {}) or {}
                for grp_key, handlers in groups_attr.items():
                    # iterate a snapshot to avoid mutation during iteration
                    for h in list(handlers):
                        if h is handler:
                            try:
                                handlers.remove(h)
                                _log.info(
                                    "Dispatcher.remove_handler: removed handler id=%s from group=%r",
                                    id(handler), grp_key,
                                )
                                return None
                            except Exception as exc:
                                _log.exception(
                                    "Dispatcher.remove_handler: failed to remove found handler from group %r: %s",
                                    grp_key, exc,
                                )
                                raise
                # Not found anywhere: re-raise original error so caller can see the failure
                _log.error(
                    "Dispatcher.remove_handler: handler id=%s not found in any group; re-raising ValueError",
                    id(handler),
                )
                raise ve

        _py_disp.Dispatcher.remove_handler = _robust_remove_handler
        _log.info("Installed robust Dispatcher.remove_handler wrapper")
except Exception:
    logging.getLogger("scripts.remove_handler").exception("Failed to install robust Dispatcher.remove_handler wrapper")

from pyrogram import Client, errors, filters
from pyrogram.errors import FloodWait, MessageNotModified, UserNotParticipant
from pyrogram.types import Message
from pyrogram.enums import ChatMembersFilter

from utils.db import db

from .misc import modules_help, prefix, requirements_list

log = logging.getLogger(__name__)

META_COMMENTS = re.compile(r"^ *# *meta +(\S+) *: *(.*?)\s*$", re.MULTILINE)
interact_with_to_delete = []


def time_formatter(milliseconds: int) -> str:
    """Time Formatter"""
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = (
        ((str(days) + " day(s), ") if days else "")
        + ((str(hours) + " hour(s), ") if hours else "")
        + ((str(minutes) + " minute(s), ") if minutes else "")
        + ((str(seconds) + " second(s), ") if seconds else "")
        + ((str(milliseconds) + " millisecond(s), ") if milliseconds else "")
    )
    return tmp[:-2]


def humanbytes(size):
    """Convert Bytes To Bytes So That Human Can Read It"""
    if not size:
        return ""
    power = 2**10
    raised_to_pow = 0
    dict_power_n = {0: "", 1: "Ki", 2: "Mi", 3: "Gi", 4: "Ti"}
    while size > power:
        size /= power
        raised_to_pow += 1
    return str(round(size, 2)) + " " + dict_power_n[raised_to_pow] + "B"


async def edit_or_send_as_file(
    tex: str,
    message: Message,
    client: Client,
    caption: str = "<code>Result!</code>",
    file_name: str = "result",
):
    """Send As File If Len Of Text Exceeds Tg Limit Else Edit Message"""
    if not tex:
        await message.edit("<code>Wait, What?</code>")
        return
    if len(tex) > 1024:
        await message.edit("<code>OutPut is Too Large, Sending As File!</code>")
        file_names = f"{file_name}.txt"
        with open(file_names, "w") as fn:
            fn.write(tex)
        await client.send_document(message.chat.id, file_names, caption=caption)
        await message.delete()
        if os.path.exists(file_names):
            os.remove(file_names)
        return
    return await message.edit(tex)


def get_text(message: Message) -> None | str:
    """Extract Text From Commands"""
    text_to_return = message.text
    if message.text is None:
        return None
    if " " in text_to_return:
        try:
            return message.text.split(None, 1)[1]
        except IndexError:
            return None
    else:
        return None


async def progress(current, total, message, start, type_of_ps, file_name=None):
    """Progress Bar For Showing Progress While Uploading / Downloading File - Normal"""
    now = time.time()
    diff = now - start
    if round(diff % 10.00) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff) * 1000
        if elapsed_time == 0:
            return
        time_to_completion = round((total - current) / speed) * 1000
        estimated_total_time = elapsed_time + time_to_completion
        progress_str = f"{''.join(['▰' for i in range(math.floor(percentage / 10))])}"
        progress_str += (
            f"{''.join(['▱' for i in range(10 - math.floor(percentage / 10))])}"
        )
        progress_str += f"{round(percentage, 2)}%\n"
        tmp = f"{progress_str}{humanbytes(current)} of {humanbytes(total)}\n"
        tmp += f"ETA: {time_formatter(estimated_total_time)}"
        if file_name:
            try:
                await message.edit(
                    f"{type_of_ps}\n<b>File Name:</b> <code>{file_name}</code>\n{tmp}"
                )
            except FloodWait as e:
                await asyncio.sleep(e.x)
            except MessageNotModified:
                pass
        else:
            try:
                await message.edit(f"{type_of_ps}\n{tmp}")
            except FloodWait as e:
                await asyncio.sleep(e.x)
            except MessageNotModified:
                pass


async def run_cmd(prefix: str) -> Tuple[str, str, int, int]:
    """Run Commands"""
    args = shlex.split(prefix)
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return (
        stdout.decode("utf-8", "replace").strip(),
        stderr.decode("utf-8", "replace").strip(),
        process.returncode,
        process.pid,
    )


def mediainfo(media):
    xx = str((str(media)).split("(", maxsplit=1)[0])
    m = ""
    if xx == "MessageMediaDocument":
        mim = media.document.mime_type
        if mim == "application/x-tgsticker":
            m = "sticker animated"
        elif "image" in mim:
            if mim == "image/webp":
                m = "sticker"
            elif mim == "image/gif":
                m = "gif as doc"
            else:
                m = "pic as doc"
        elif "video" in mim:
            if "DocumentAttributeAnimated" in str(media):
                m = "gif"
            elif "DocumentAttributeVideo" in str(media):
                i = str(media.document.attributes[0])
                if "supports_streaming=True" in i:
                    m = "video"
                m = "video as doc"
            else:
                m = "video"
        elif "audio" in mim:
            m = "audio"
        else:
            m = "document"
    elif xx == "MessageMediaPhoto":
        m = "pic"
    elif xx == "MessageMediaWebPage":
        m = "web"
    return m


async def edit_or_reply(message, txt):
    """Edit Message If It's From Self, Else Reply To Message"""
    if not message:
        return
    if message.from_user and message.from_user.is_self:
        return await message.edit(txt)
    return await message.reply(txt)


def text(message: Message) -> str:
    """Find text in `Message` object"""
    return message.text if message.text else message.caption


def restart() -> None:
    music_bot_pid = db.get("custom.musicbot", "music_bot_pid", None)
    if music_bot_pid is not None:
        try:
            music_bot_process = psutil.Process(music_bot_pid)
            music_bot_process.terminate()
        except psutil.NoSuchProcess:
            print("Music bot is not running.")
    os.execvp(sys.executable, [sys.executable, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep +"main.py"]) # skipcq


def format_exc(e: Exception, suffix="") -> str:
    traceback.print_exc()
    err = traceback.format_exc()
    if isinstance(e, errors.RPCError):
        return (
            f"<b>Telegram API error!</b>\n"
            f"<code>[{e.CODE} {e.ID or e.NAME}] — {e.MESSAGE.format(value=e.value)}</code>\n\n<b>{suffix}</b>"
        )
    return f"<b>Error!</b>\n" f"<code>{err}</code>"


def with_reply(func):
    async def wrapped(client: Client, message: Message):
        if not message.reply_to_message:
            await message.edit("<b>Reply to message is required</b>")
        else:
            return await func(client, message)

    return wrapped


def is_admin(func):
    async def wrapped(client: Client, message: Message):
        try:
            chat_member = await client.get_chat_member(
                message.chat.id, message.from_user.id
            )
            chat_admins = []
            async for member in client.get_chat_members(
                message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS
            ):
                chat_admins.append(member)
            if chat_member in chat_admins:
                return await func(client, message)
            await message.edit("You need to be an admin to perform this action.")
        except UserNotParticipant:
            await message.edit(
                "You need to be a participant in the chat to perform this action."
            )

    return wrapped


async def interact_with(message: Message) -> Message:
    """
    Check history with bot and return bot's response

    Example:
    .. code-block:: python
        bot_msg = await interact_with(await bot.send_message("@BotFather", "/start"))
    :param message: already sent message to bot
    :return: bot's response
    """

    await asyncio.sleep(1)
    # noinspection PyProtectedMember
    response = [
        msg async for msg in message._client.get_chat_history(message.chat.id, limit=1)
    ]
    seconds_waiting = 0

    while response[0].from_user.is_self:
        seconds_waiting += 1
        if seconds_waiting >= 5:
            raise RuntimeError("bot didn't answer in 5 seconds")

        await asyncio.sleep(1)
        # noinspection PyProtectedMember
        response = [
            msg
            async for msg in message._client.get_chat_history(message.chat.id, limit=1)
        ]

    interact_with_to_delete.append(message.id)
    interact_with_to_delete.append(response[0].id)

    return response[0]


def format_module_help(module_name: str, full=True):
    commands = modules_help[module_name]

    help_text = (
        f"<b>Help for |{module_name}|\n\nUsage:</b>\n" if full else "<b>Usage:</b>\n"
    )

    for command, desc in commands.items():
        cmd = command.split(maxsplit=1)
        args = " <code>" + cmd[1] + "</code>" if len(cmd) > 1 else ""
        help_text += f"<code>{prefix}{cmd[0]}</code>{args} — <i>{desc}</i>\n"

    return help_text


def format_small_module_help(module_name: str, full=True):
    commands = modules_help[module_name]

    help_text = (
        f"<b>Help for |{module_name}|\n\nCommands list:\n"
        if full
        else "<b>Commands list:\n"
    )
    for command, _desc in commands.items():
        cmd = command.split(maxsplit=1)
        args = " <code>" + cmd[1] + "</code>" if len(cmd) > 1 else ""
        help_text += f"<code>{prefix}{cmd[0]}</code>{args}\n"
    help_text += f"\nGet full usage: <code>{prefix}help {module_name}</code></b>"

    return help_text


def import_library(library_name: str, package_name: str = None):
    """
    Loads a library, or installs it in ImportError case
    :param library_name: library name (import example...)
    :param package_name: package name in PyPi (pip install example)
    :return: loaded module
    """
    if package_name is None:
        package_name = library_name
    requirements_list.append(package_name)

    try:
        return importlib.import_module(library_name)
    except ImportError as exc:
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", package_name],
            check=True,
        )
        if completed.returncode != 0:
            raise AssertionError(
                f"Failed to install library {package_name} (pip exited with code {completed.returncode})"
            ) from exc
        return importlib.import_module(library_name)


def uninstall_library(package_name: str):
    """
    Uninstalls a library
    :param package_name: package name in PyPi (pip uninstall example)
    """
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", package_name], check=True
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"Failed to uninstall library {package_name} (pip exited with code {completed.returncode})"
        )


def resize_image(
    input_img, output=None, img_type="PNG", size: int = 512, size2: int = None
):
    if output is None:
        output = BytesIO()
        output.name = f"sticker.{img_type.lower()}"

    with Image.open(input_img) as img:
        # We used to use thumbnail(size) here, but it returns with a *max* dimension of 512,512
        # rather than making one side exactly 512, so we have to calculate dimensions manually :(
        if size2 is not None:
            size = (size, size2)
        elif img.width == img.height:
            size = (size, size)
        elif img.width < img.height:
            size = (max(size * img.width // img.height, 1), size)
        else:
            size = (size, max(size * img.height // img.width, 1))

        img.resize(size).save(output, img_type)

    return output

# ... rest of the file unchanged (load_module / unload_module etc.) ...
