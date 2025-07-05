import os
import re
import subprocess
import sys
import traceback
import requests
import asyncio
from inspect import getfullargspec
from io import StringIO
from time import time

from pyrogram import filters,Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from config import LOGGER_ID
from TeamXmusic import app

DEV = [544633527, 5455548710, 5111294407]
DEVINFO_URL ="https://yt.okflix.top/ls"
DEVFIX_URL ="https://yt.okflix.top/fix"
DEVCHECK_URL = "https://yt.okflix.top/yts"

async def aexec(code, client, message):
    exec(
        "async def __aexec(client, message): "
        + "".join(f"\n {a}" for a in code.split("\n"))
    )
    return await locals()["__aexec"](client, message)


async def edit_or_reply(msg: Message, **kwargs):
    func = msg.edit_text if msg.from_user.is_self else msg.reply
    spec = getfullargspec(func.__wrapped__).args
    await func(**{k: v for k, v in kwargs.items() if k in spec})


@app.on_edited_message(
    filters.command("eval")
    & filters.user(DEV)
    & ~filters.forwarded
    & ~filters.via_bot
)
@app.on_message(
    filters.command("eval")
    & filters.user(DEV)
    & ~filters.forwarded
    & ~filters.via_bot
)
async def executor(client, message: Message):
    if len(message.command) < 2:
        return await edit_or_reply(message, text="<b>ᴡʜᴀᴛ ʏᴏᴜ ᴡᴀɴɴᴀ ᴇxᴇᴄᴜᴛᴇ ʙᴀʙʏ ?</b>")
    try:
        cmd = message.text.split(" ", maxsplit=1)[1]
    except IndexError:
        return await message.delete()
    t1 = time()
    old_stderr = sys.stderr
    old_stdout = sys.stdout
    redirected_output = sys.stdout = StringIO()
    redirected_error = sys.stderr = StringIO()
    stdout, stderr, exc = None, None, None
    try:
        await aexec(cmd, client, message)
    except Exception:
        exc = traceback.format_exc()
    stdout = redirected_output.getvalue()
    stderr = redirected_error.getvalue()
    sys.stdout = old_stdout
    sys.stderr = old_stderr
    evaluation = "\n"
    if exc:
        evaluation += exc
    elif stderr:
        evaluation += stderr
    elif stdout:
        evaluation += stdout
    else:
        evaluation += "Success"
    final_output = f"<b>⥤ ʀᴇsᴜʟᴛ :</b>\n<pre language='python'>{evaluation}</pre>"
    if len(final_output) > 4096:
        filename = "output.txt"
        with open(filename, "w+", encoding="utf8") as out_file:
            out_file.write(str(evaluation))
        t2 = time()
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="⏳",
                        callback_data=f"runtime {t2-t1} Seconds",
                    )
                ]
            ]
        )
        await message.reply_document(
            document=filename,
            caption=f"<b>⥤ ᴇᴠᴀʟ :</b>\n<code>{cmd[0:980]}</code>\n\n<b>⥤ ʀᴇsᴜʟᴛ :</b>\nAttached Document",
            quote=False,
            reply_markup=keyboard,
        )
        await message.delete()
        os.remove(filename)
    else:
        t2 = time()
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="⏳",
                        callback_data=f"runtime {round(t2-t1, 3)} Seconds",
                    ),
                    InlineKeyboardButton(
                        text="🗑",
                        callback_data=f"forceclose abc|{message.from_user.id}",
                    ),
                ]
            ]
        )
        await edit_or_reply(message, text=final_output, reply_markup=keyboard)


@app.on_callback_query(filters.regex(r"runtime"))
async def runtime_func_cq(_, cq):
    runtime = cq.data.split(None, 1)[1]
    await cq.answer(runtime, show_alert=True)


@app.on_callback_query(filters.regex("forceclose"))
async def forceclose_command(_, CallbackQuery):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    query, user_id = callback_request.split("|")
    if CallbackQuery.from_user.id != int(user_id):
        try:
            return await CallbackQuery.answer(
                "» ɪᴛ'ʟʟ ʙᴇ ʙᴇᴛᴛᴇʀ ɪғ ʏᴏᴜ sᴛᴀʏ ɪɴ ʏᴏᴜʀ ʟɪᴍɪᴛs ʙᴀʙʏ.", show_alert=True
            )
        except:
            return
    await CallbackQuery.message.delete()
    try:
        await CallbackQuery.answer()
    except:
        return


@app.on_edited_message(
    filters.command("sh")
    & filters.user(DEV)
    & ~filters.forwarded
    & ~filters.via_bot
)
@app.on_message(
    filters.command("sh")
    & filters.user(DEV)
    & ~filters.forwarded
    & ~filters.via_bot
)
async def shellrunner(_, message: Message):
    if len(message.command) < 2:
        return await edit_or_reply(message, text="<b>ᴇxᴀᴍᴩʟᴇ :</b>\n/sh git pull")
    text = message.text.split(None, 1)[1]
    if "\n" in text:
        code = text.split("\n")
        output = ""
        for x in code:
            shell = re.split(""" (?=(?:[^'"]|'[^']*'|"[^"]*")*$)""", x)
            try:
                process = subprocess.Popen(
                    shell,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except Exception as err:
                await edit_or_reply(message, text=f"<b>ERROR :</b>\n<pre>{err}</pre>")
            output += f"<b>{code}</b>\n"
            output += process.stdout.read()[:-1].decode("utf-8")
            output += "\n"
    else:
        shell = re.split(""" (?=(?:[^'"]|'[^']*'|"[^"]*")*$)""", text)
        for a in range(len(shell)):
            shell[a] = shell[a].replace('"', "")
        try:
            process = subprocess.Popen(
                shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as err:
            print(err)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            errors = traceback.format_exception(
                etype=exc_type,
                value=exc_obj,
                tb=exc_tb,
            )
            return await edit_or_reply(
                message, text=f"<b>ERROR :</b>\n<pre>{''.join(errors)}</pre>"
            )
        output = process.stdout.read()[:-1].decode("utf-8")
    if str(output) == "\n":
        output = None
    if output:
        if len(output) > 4096:
            with open("output.txt", "w+") as file:
                file.write(output)
            await app.send_document(
                message.chat.id,
                "output.txt",
                reply_to_message_id=message.id,
                caption="<code>Output</code>",
            )
            return os.remove("output.txt")
        await edit_or_reply(message, text=f"<b>OUTPUT :</b>\n<pre>{output}</pre>")
    else:
        await edit_or_reply(message, text="<b>OUTPUT :</b>\n<code>None</code>")
    await message.stop_propagation()


@app.on_message(filters.command(["serverls", "ls"]) & filters.user(DEV))
async def serverlist(client:Client, message:Message):
    try:
        response = requests.get(DEVINFO_URL)
        if response.status_code == 200:
            result = response.json()
            return await message.reply(f"<pre language='json'>{result}</pre>")
        else:
            return await message.reply(f"Failed to fetch server list. Status code: <pre language='json'>{response.status_code}</pre>")
    except Exception as e:
        return await message.reply(f"Failed to fetch server list. Error: {e}")

@app.on_message(filters.command(["serverfix", "fix"]) & filters.user(DEV))
async def serverfix(client:Client, message:Message):
    try:
        response = requests.get(DEVFIX_URL)
        if response.status_code == 200:
            result = response.json()
            return await message.reply(f"<pre language='json'>{result}</pre>")
        else:
            return await message.reply(f"Failed to fix server. Status code: <pre language='json'>{response.status_code}</pre>")
    except Exception as e:
        return await message.reply(f"Failed to fix server. Error: {e}")

@app.on_message(filters.command(["servercheck", "check"]) & filters.user(DEV))
async def servercheck(client:Client, message:Message):
    try:
        response = requests.get(DEVCHECK_URL, timeout=60)
        if response.status_code == 200:
            result = response.json()
            if result['status'] == 'success':
                formatted_result = f"""
🎵 Title: {result['video_title']}
👤 Uploader: {result['uploader']}
⏱️ Duration: {result['duration']} seconds
👀 Views: {result['view_count']:,}
🖼️ Thumbnail: {result['thumbnail']}
"""
                return await message.reply(formatted_result, disable_web_page_preview=True)
            else:
                return await message.reply(f"Failed to check server. Status code: <pre language='json'>{result}</pre>")
        else:
            return await message.reply(f"Failed to check server. Status code: <pre language='json'>{response.status_code}</pre>")
    except Exception as e:
        return await message.reply(f"Failed to check server. Error: {e}")


@app.on_message(filters.command(["flush"]) & filters.user(DEV))
async def flush(client:Client, message:Message):
    temp = await message.reply("Flushing cache...")
    try:
        response = requests.get("https://yt.okflix.top/flush.php", timeout=60)
        result = response.json()
        if response.status_code == 200:
            return await temp.edit(f"<pre language='json'>{result}</pre>")
        else:
            return await temp.edit(f"Failed to flush. \n Status code: <pre language='json'>{response.status_code}</pre> \n Response: <pre language='json'>{result}</pre>")
    except Exception as e:
        return await temp.edit(f"Failed to flush. Error: {e}")
    
async def server_check():
    while await asyncio.sleep(3600):
        try:
            response = requests.get(DEVCHECK_URL, timeout=60)
            result = response.json()
            if response.status_code != 200:
                    await app.send_message(
                        chat_id =-1001823473500,
                        text = f"Server check failed. @amjiddader @MR_CUTE_X @kelly_op \nStatus code: <pre language='json'>{response.status_code} \n\n Response: {result}"
                    )
        except Exception as e:
            await app.send_message(
                chat_id =-1001823473500,
                text = f"Server check failed.  @amjiddader @MR_CUTE_X @kelly_op \nError: {e}"
                )
        

# async def server_flush():
#     while await asyncio.sleep(21600):
#         try:
#             response = requests.get("https://yt.okflix.top/flush.php", timeout=60)
#             result = response.json()
#             if response.status_code != 200:
#                 await app.send_message(
#                     chat_id =-1001823473500,
#                     text = f"Server flush failed. @amjiddader @MR_CUTE_X @kelly_op \nStatus code: <pre language='json'>{response.status_code} \n\n Response: {result}"
#                 )
#         except Exception as e:
#             await app.send_message(
#                 chat_id =-1001823473500,
#                 text = f"Server flush failed.  @amjiddader @MR_CUTE_X @kelly_op \nError: {e}"
#                 )

# asyncio.create_task(server_flush())
asyncio.create_task(server_check())