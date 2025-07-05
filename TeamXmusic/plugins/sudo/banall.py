import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from config import SUDO_USERS
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait, RPCError

sudo_filter = filters.user(SUDO_USERS)

@Client.on_message(filters.command("banall") & filters.group & sudo_filter)
async def banall_handler(client: Client, message: Message):
    await message.reply("🚨 Starting ultra-fast banall process...")

    try:
        banned = 0
        skipped = 0
        to_ban = []

        async for member in client.get_chat_members(message.chat.id):
            user_id = member.user.id
            status = member.status

            if user_id in SUDO_USERS or status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                skipped += 1
                continue
            to_ban.append(user_id)

        # Helper to ban a single user with error handling
        async def ban_user(user_id):
            try:
                await client.ban_chat_member(chat_id=message.chat.id, user_id=user_id)
                return True
            except FloodWait as e:
                await asyncio.sleep(e.value)
                return await ban_user(user_id)
            except RPCError:
                return False

        # Use asyncio.gather for concurrent bans
        tasks = [ban_user(uid) for uid in to_ban]
        results = await asyncio.gather(*tasks)

        banned = sum(results)
        skipped += len(to_ban) - banned

        await message.reply(
            f"✅ Banall completed!\n\n👤 Total scanned: {len(to_ban) + skipped}\n🔨 Banned: {banned}\n⏭️ Skipped: {skipped}"
        )

    except Exception as e:
        await message.reply(f"❌ Error: {e}")
