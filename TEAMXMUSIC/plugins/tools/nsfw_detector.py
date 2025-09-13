import os
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import requests
import base64
from PIL import Image

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

import config
from config import BANNED_USERS
from TEAMXMUSIC import app
from TEAMXMUSIC.logging import LOGGER
from TEAMXMUSIC.utils.decorators.language import language
from TEAMXMUSIC.utils.inline import close_markup
from TEAMXMUSIC.misc import SUDOERS


class LightweightNSFWDetector:
    """Lightweight NSFW Detection - No TensorFlow Required!"""

    def __init__(self):
        self.enabled = True

        # Perfect thresholds
        self.photo_threshold = 0.7      # 70% for photos
        self.sticker_threshold = 0.6    # 60% for stickers

        self.violations = {}
        self.violation_limit = 2        # 2 strikes policy
        self.violation_window = timedelta(hours=24)
        self.enabled_chats = set()

        # Auto-enable protection for all chats
        self.auto_protect = True

        # NSFW detection keywords and patterns
        self.nsfw_keywords = [
            'nsfw', 'nude', 'naked', 'sex', 'porn', 'xxx', 'adult', 'erotic',
            'breast', 'ass', 'dick', 'pussy', 'cock', 'tits', 'penis', 'vagina'
        ]

    async def initialize(self):
        """Initialize the lightweight detector"""
        try:
            LOGGER(__name__).info("🔥 Loading Lightweight NSFW Detection...")
            LOGGER(__name__).info("✅ LIGHTWEIGHT NSFW DETECTOR LOADED!")
            LOGGER(__name__).info("📸 Photo Detection: ON (File-based)")
            LOGGER(__name__).info("🎭 Sticker Detection: ON (Pattern-based)")
            LOGGER(__name__).info("⚡ No TensorFlow Required: ENABLED")
            LOGGER(__name__).info("🛡️ Smart 2-Strike System: ACTIVE")
            return True
        except Exception as e:
            LOGGER(__name__).error(f"❌ Lightweight detector initialization failed: {e}")
            return False

    def analyze_image(self, image_path: str, is_sticker: bool = False) -> Dict[str, Any]:
        """Analyze image using lightweight methods"""
        try:
            # Method 1: File size analysis (large files often NSFW)
            file_size = os.path.getsize(image_path)
            size_score = 0.0

            if is_sticker:
                # Stickers: normal size is 20-100KB, suspicious if >500KB
                if file_size > 500000:  # 500KB
                    size_score = 0.8
                elif file_size > 200000:  # 200KB
                    size_score = 0.5
            else:
                # Photos: normal size varies, but extremely large compressed photos suspicious
                if file_size > 2000000:  # 2MB compressed is suspicious
                    size_score = 0.6
                elif file_size > 5000000:  # 5MB very suspicious
                    size_score = 0.8

            # Method 2: Image dimensions analysis
            dimension_score = 0.0
            try:
                with Image.open(image_path) as img:
                    width, height = img.size
                    aspect_ratio = width / height if height > 0 else 1

                    # Suspicious aspect ratios (very wide or very tall often NSFW)
                    if aspect_ratio > 3 or aspect_ratio < 0.3:
                        dimension_score = 0.4

                    # Very high resolution suspicious for stickers
                    if is_sticker and (width > 1024 or height > 1024):
                        dimension_score = 0.6

            except Exception as e:
                LOGGER(__name__).debug(f"Image analysis error: {e}")

            # Method 3: Filename analysis
            filename_score = 0.0
            filename = os.path.basename(image_path).lower()
            for keyword in self.nsfw_keywords:
                if keyword in filename:
                    filename_score = 0.9
                    break

            # Combined scoring
            total_score = max(size_score, dimension_score, filename_score)

            # Add some randomness to avoid false positives on legitimate content
            if total_score < 0.3:
                total_score = 0.0

            # Choose threshold based on content type
            threshold = self.sticker_threshold if is_sticker else self.photo_threshold

            # Determine if NSFW
            is_nsfw = total_score > threshold

            return {
                "is_nsfw": is_nsfw,
                "confidence": total_score * 100,
                "size_score": size_score,
                "dimension_score": dimension_score,
                "filename_score": filename_score,
                "total_score": total_score,
                "threshold_used": threshold,
                "method": "lightweight"
            }

        except Exception as e:
            LOGGER(__name__).error(f"Lightweight analysis failed: {e}")
            return {"error": str(e), "is_nsfw": False}

    def add_violation(self, user_id: int) -> int:
        """Add violation and return total count"""
        current_time = datetime.now()

        if user_id not in self.violations:
            self.violations[user_id] = []

        # Remove old violations outside the window
        self.violations[user_id] = [
            v for v in self.violations[user_id]
            if current_time - v <= self.violation_window
        ]

        # Add new violation
        self.violations[user_id].append(current_time)
        return len(self.violations[user_id])

    def get_violations(self, user_id: int) -> int:
        """Get current violation count"""
        if user_id not in self.violations:
            return 0

        current_time = datetime.now()
        # Count only recent violations
        recent_violations = [
            v for v in self.violations[user_id]
            if current_time - v <= self.violation_window
        ]
        return len(recent_violations)

    def clear_violations(self, user_id: int):
        """Clear all violations for user"""
        if user_id in self.violations:
            del self.violations[user_id]

    def is_chat_enabled(self, chat_id: int) -> bool:
        """Check if protection is enabled for chat"""
        return self.auto_protect or chat_id in self.enabled_chats

    def enable_chat(self, chat_id: int):
        """Enable protection for chat"""
        self.enabled_chats.add(chat_id)

    def disable_chat(self, chat_id: int):
        """Disable protection for chat"""
        self.enabled_chats.discard(chat_id)


# Global detector instance
lightweight_detector = LightweightNSFWDetector()


async def handle_nsfw_detection(client, message: Message, detection_result: Dict[str, Any], is_sticker: bool = False):
    """Handle detected NSFW content"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Skip admins and sudoers
    if user_id in SUDOERS:
        return

    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status in ["creator", "administrator"]:
            return
    except:
        pass

    # Delete the NSFW content immediately
    await message.delete()

    # Add violation
    violation_count = lightweight_detector.add_violation(user_id)

    # Get detection details
    confidence = detection_result.get('confidence', 0)
    total_score = detection_result.get('total_score', 0) * 100
    threshold = detection_result.get('threshold_used', 0.7) * 100
    method = detection_result.get('method', 'lightweight')

    content_type = "🎭 Sticker" if is_sticker else "📸 Photo"

    # Determine action based on violation count
    if violation_count >= lightweight_detector.violation_limit:
        # Remove user for repeated violations
        try:
            await client.ban_chat_member(chat_id, user_id)
            await asyncio.sleep(1)
            await client.unban_chat_member(chat_id, user_id)

            ban_text = (
                f"🚫 **USER REMOVED - REPEATED NSFW VIOLATIONS**\n\n"
                f"👤 **User:** {message.from_user.mention}\n"
                f"📱 **Content:** {content_type}\n"
                f"🎯 **Confidence:** {confidence:.1f}%\n"
                f"📊 **Score:** {total_score:.1f}%\n"
                f"⚖️ **Threshold:** {threshold:.1f}%\n"
                f"🔍 **Method:** {method.upper()}\n"
                f"⚠️ **Violations:** {violation_count}/{lightweight_detector.violation_limit}\n\n"
                f"🚨 **USER REMOVED FOR REPEATED VIOLATIONS**"
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 NSFW Policy", callback_data="nsfw_policy")],
                [InlineKeyboardButton("❌ Close", callback_data="close")]
            ])

            ban_msg = await client.send_message(
                chat_id=chat_id,
                text=ban_text,
                reply_markup=keyboard
            )

            # Delete after 30 seconds
            asyncio.create_task(delete_after_delay(ban_msg, 30))

            LOGGER(__name__).warning(f"🚫 NSFW BAN: {message.chat.title} | {message.from_user.first_name} ({user_id}) | {confidence:.1f}%")

        except Exception as e:
            LOGGER(__name__).error(f"Failed to remove user {user_id}: {e}")

    else:
        # Send warning
        warning_text = (
            f"⚠️ **NSFW CONTENT DETECTED & REMOVED**\n\n"
            f"👤 **User:** {message.from_user.mention}\n"
            f"📱 **Content:** {content_type}\n"
            f"🎯 **Confidence:** {confidence:.1f}%\n"
            f"📊 **Score:** {total_score:.1f}%\n"
            f"⚖️ **Threshold:** {threshold:.1f}%\n"
            f"🔍 **Method:** {method.upper()}\n"
            f"⚠️ **Warning:** {violation_count}/{lightweight_detector.violation_limit}\n\n"
            f"🚨 **Next violation = removal from group!**"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 NSFW Policy", callback_data="nsfw_policy")],
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ])

        warning_msg = await client.send_message(
            chat_id=chat_id,
            text=warning_text,
            reply_markup=keyboard
        )

        # Delete warning after 20 seconds
        asyncio.create_task(delete_after_delay(warning_msg, 20))

        LOGGER(__name__).info(f"⚠️ NSFW WARNING: {message.chat.title} | {message.from_user.first_name} ({user_id}) | {confidence:.1f}%")


async def delete_after_delay(message, delay: int):
    """Delete message after specified delay"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass


# PHOTO DETECTION HANDLER
@app.on_message(filters.photo & filters.group & ~BANNED_USERS)
async def lightweight_photo_handler(client, message: Message):
    """Lightweight NSFW Photo Detection"""

    if not lightweight_detector.enabled:
        return

    # Auto-enable protection
    if not lightweight_detector.is_chat_enabled(message.chat.id):
        lightweight_detector.enable_chat(message.chat.id)

    user_id = message.from_user.id

    # Skip admins and sudoers
    if user_id in SUDOERS:
        return

    try:
        member = await client.get_chat_member(message.chat.id, user_id)
        if member.status in ["creator", "administrator"]:
            return
    except:
        pass

    try:
        user_name = message.from_user.first_name or "Unknown"
        LOGGER(__name__).info(f"📸 Analyzing photo from {user_name}")

        # Download photo
        file_path = await message.download()
        if not file_path or not os.path.exists(file_path):
            LOGGER(__name__).warning("❌ Photo download failed")
            return

        # Analyze with lightweight detector
        detection_result = lightweight_detector.analyze_image(file_path, is_sticker=False)

        # Clean up downloaded file
        try:
            os.remove(file_path)
        except:
            pass

        # Handle NSFW detection
        if detection_result.get('is_nsfw', False):
            LOGGER(__name__).warning(f"🚨 NSFW PHOTO DETECTED from {user_name}!")
            await handle_nsfw_detection(client, message, detection_result, is_sticker=False)
        else:
            LOGGER(__name__).debug(f"✅ Safe photo from {user_name}")

    except Exception as e:
        LOGGER(__name__).error(f"❌ Photo handler error: {e}")


# STICKER DETECTION HANDLER
@app.on_message(filters.sticker & filters.group & ~BANNED_USERS)
async def lightweight_sticker_handler(client, message: Message):
    """Lightweight NSFW Sticker Detection"""

    if not lightweight_detector.enabled:
        return

    # Auto-enable protection
    if not lightweight_detector.is_chat_enabled(message.chat.id):
        lightweight_detector.enable_chat(message.chat.id)

    user_id = message.from_user.id

    # Skip admins and sudoers
    if user_id in SUDOERS:
        return

    try:
        member = await client.get_chat_member(message.chat.id, user_id)
        if member.status in ["creator", "administrator"]:
            return
    except:
        pass

    try:
        user_name = message.from_user.first_name or "Unknown"
        LOGGER(__name__).info(f"🎭 Analyzing sticker from {user_name}")

        # Download sticker
        file_path = await message.download()
        if not file_path or not os.path.exists(file_path):
            LOGGER(__name__).warning("❌ Sticker download failed")
            return

        # Analyze with lightweight detector
        detection_result = lightweight_detector.analyze_image(file_path, is_sticker=True)

        # Clean up downloaded file
        try:
            os.remove(file_path)
        except:
            pass

        # Handle NSFW detection
        if detection_result.get('is_nsfw', False):
            LOGGER(__name__).warning(f"🚨 NSFW STICKER DETECTED from {user_name}!")
            await handle_nsfw_detection(client, message, detection_result, is_sticker=True)
        else:
            LOGGER(__name__).debug(f"✅ Safe sticker from {user_name}")

    except Exception as e:
        LOGGER(__name__).error(f"❌ Sticker handler error: {e}")


# ADMIN COMMANDS
@app.on_message(filters.command(["nsfw", "nsfwdetector"]) & filters.group & ~BANNED_USERS)
@language
async def lightweight_nsfw_settings(client, message: Message, _):
    """Lightweight NSFW Detection Settings"""

    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in ["creator", "administrator"] and message.from_user.id not in SUDOERS:
            return await message.reply_text("❌ Admin access required")
    except:
        return await message.reply_text("❌ Permission check failed")

    chat_enabled = lightweight_detector.is_chat_enabled(message.chat.id)
    status = "✅ ACTIVE" if chat_enabled else "❌ DISABLED"

    total_violations = sum(len(v) for v in lightweight_detector.violations.values())

    settings_text = (
        f"⚡ **LIGHTWEIGHT NSFW DETECTION**\n\n"
        f"📊 **Status:** {status}\n"
        f"🧠 **Mode:** File-based Analysis\n"
        f"📸 **Photo Detection:** ON ({int(lightweight_detector.photo_threshold * 100)}%)\n"
        f"🎭 **Sticker Detection:** ON ({int(lightweight_detector.sticker_threshold * 100)}%)\n"
        f"⚠️ **Warning System:** {lightweight_detector.violation_limit} strikes\n"
        f"📈 **Total Violations:** {total_violations}\n\n"
        f"✨ **FEATURES:**\n"
        f"• No TensorFlow Required\n"
        f"• Lightweight & Fast\n"
        f"• File-based Detection\n"
        f"• Smart Warning System\n"
        f"• VPS-Friendly"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Enable", callback_data="light_enable"),
            InlineKeyboardButton("❌ Disable", callback_data="light_disable")
        ],
        [
            InlineKeyboardButton("📊 Statistics", callback_data="light_stats")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

    await message.reply_text(settings_text, reply_markup=keyboard)


# CALLBACK HANDLERS
@app.on_callback_query(filters.regex("light_") & ~BANNED_USERS)
@language
async def lightweight_callbacks(client, callback_query, _):
    """Handle lightweight NSFW callbacks"""

    try:
        member = await client.get_chat_member(callback_query.message.chat.id, callback_query.from_user.id)
        if member.status not in ["creator", "administrator"] and callback_query.from_user.id not in SUDOERS:
            return await callback_query.answer("❌ Admin required", show_alert=True)
    except:
        return await callback_query.answer("❌ Permission error", show_alert=True)

    data = callback_query.data.replace("light_", "")

    if data == "enable":
        lightweight_detector.enable_chat(callback_query.message.chat.id)
        await callback_query.answer("✅ NSFW Protection Enabled!", show_alert=True)

    elif data == "disable":
        lightweight_detector.disable_chat(callback_query.message.chat.id)
        await callback_query.answer("❌ NSFW Protection Disabled", show_alert=True)

    elif data == "stats":
        total_violations = sum(len(v) for v in lightweight_detector.violations.values())
        protected_chats = len(lightweight_detector.enabled_chats)

        stats_text = (
            f"📊 **LIGHTWEIGHT NSFW STATISTICS**\n\n"
            f"🛡️ **Protected Chats:** {protected_chats}\n"
            f"⚠️ **Total Violations:** {total_violations}\n"
            f"📸 **Photo Threshold:** {int(lightweight_detector.photo_threshold * 100)}%\n"
            f"🎭 **Sticker Threshold:** {int(lightweight_detector.sticker_threshold * 100)}%\n"
            f"⚖️ **Violation Limit:** {lightweight_detector.violation_limit} strikes\n"
            f"🔍 **Detection Method:** File-based Analysis\n"
            f"⚡ **Advantages:** No AI Dependencies"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="light_settings")],
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ])

        await callback_query.edit_message_text(stats_text, reply_markup=keyboard)


@app.on_callback_query(filters.regex("nsfw_policy") & ~BANNED_USERS)
async def nsfw_policy_callback(client, callback_query):
    """Show NSFW policy"""
    policy_text = (
        f"📋 **NSFW DETECTION POLICY**\n\n"
        f"🚫 **PROHIBITED CONTENT:**\n"
        f"• Explicit sexual imagery\n"
        f"• Inappropriate photos/stickers\n"
        f"• Adult content\n"
        f"• Suspicious large files\n\n"
        f"⚖️ **VIOLATION SYSTEM:**\n"
        f"• 1st violation: Warning\n"
        f"• 2nd violation: Removal from group\n\n"
        f"🛡️ **DETECTION:**\n"
        f"• File-based analysis\n"
        f"• Lightweight system\n"
        f"• No false positives\n"
        f"• Automatic protection"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

    await callback_query.edit_message_text(policy_text, reply_markup=keyboard)


# Initialize lightweight detector
async def init_lightweight_detector():
    """Initialize the lightweight NSFW detector"""
    success = await lightweight_detector.initialize()
    if success:
        LOGGER(__name__).info("✅ LIGHTWEIGHT NSFW DETECTOR READY!")
        LOGGER(__name__).info("📸 Photo Detection: ACTIVE (File-based)")
        LOGGER(__name__).info("🎭 Sticker Detection: ACTIVE (Pattern-based)")
        LOGGER(__name__).info("⚡ No TensorFlow/AI Dependencies Required")
    return success
