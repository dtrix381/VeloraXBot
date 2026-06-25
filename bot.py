import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import sqlite3
import asyncio
from datetime import datetime, timedelta, UTC
import re
import os
import math
from openpyxl import Workbook
import random

GUILD_ID = 1501471671360553131
VELORAX_X_USERNAME = "VeloraX_Labs"
GUILD_OWNER_ID = 488015447417946151
ADMIN_ROLE_ID = 1501472062903156756  # Team
ELITE_CREATOR_ROLE_ID = 1514517405735452843 # Elite Creator
MEMBER_ROLE_ID = 1501473138188353616  # Creator
VERIFIED_ROLE_ID = 1501473283852472380  # Engager
WELCOME_CHANNEL_ID = 1501481909337718824
INVITE_APPROVAL_CHANNEL_ID = 1507312406395752458
BOT_INVITER_ID = 1501868266614947880
SUPPORT_CATEGORY_ID = 1501483613529706528
ADMIN_REVIEW_CHANNEL_ID = 1507604124366147735
FIRST_OFFENSE_ROLE = 1507613554910433320
SECOND_OFFENSE_ROLE = 1507613855587766302
WAITING_ROOM_CHANNEL = 1510492366660833350
ADMIN_LOG_CHANNEL = 1501476619641163927
ADMIN_DAILY_CREATOR_POINTS = 150
REMINDER_CHANNEL_ID = 1501478302102323210

CATEGORY_NAME = 1507640053315407904
REGISTER_CHANNEL = 1507640055680733244
INVITE_CHANNEL = 1507640057287409786
AVAILABLE_QUEST_CHANNEL = 1508623094606991440
QUEST_CHANNEL = 1507640059560595536
REPORT_CHANNEL = 1507640061787639901
LOGS_CHANNEL = 1507640063666946221
STATS_CHANNEL = 1507640065826754630
LEADERBOARD_CHANNEL = 1508476505900978346

VIP_CATEGORY_NAME = 1507640088413339802
PAID_QUEST_CHANNEL = 1507640090418086019
SUBMISSION_QUEUE_CHANNEL = 1508629156215132347
VIP_APPROVAL_CHANNEL = 1507640092494266418
GOLD_LOGS_CHANNEL = 1507640096290242612
GOLD_LEADERBOARD_CHANNEL = 1507640098521481236
SHOP_CHANNEL = 1507640118616391802
APPROVAL_CHANNEL = 1507640094951997460

MAX_GIVEAWAY_ENTRIES = 3
RAFFLE_CHANNEL = 1511554965938901023
RAFFLE_PRIZE = "$10"
RAFFLE_ENTRY_COST = 1
GIVEAWAY_ARTWORK = (
    "https://cdn.discordapp.com/attachments/"
    "1225024450345439313/"
    "1511510976803901501/"
    "image.png"
)

EXCHANGE_GOLD_COST = 100
EXCHANGE_REWARD = "$10"
EXCHANGE_OPTIONS = {
    100: "$10",
    200: "$20",
    300: "$30",
    500: "$50"
}

invite_cache = {}

# ===================== CONFIG =====================
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise SystemExit("❌ DISCORD_BOT_TOKEN is not set in environment variables.")

DB_PATH = "/data/velorax.db"

intents = discord.Intents.default()
intents.presences = True  # Required for rich presence
intents.message_content = True
intents.messages = True
intents.members = True


# =========================
# DATABASE
# =========================

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    x_username TEXT,
    x_username_lower TEXT,
    points INTEGER DEFAULT 0,
    gold_points INTEGER DEFAULT 0,
    quests_completed INTEGER DEFAULT 0,
    quests_denied INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS quests (
    quest_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    tweet_link TEXT,
    created_by INTEGER,
    created_at TEXT,
    expires_at TEXT,
    message_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id INTEGER,
    user_id INTEGER,
    reply_link TEXT,
    status TEXT DEFAULT 'pending',
    approval_message_id INTEGER,
    completed_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS invites (
    code TEXT PRIMARY KEY,
    inviter_id INTEGER,
    created_at TEXT,
    reviewed_creator INTEGER DEFAULT 0,
    total_invites INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS invite_joins (
    invited_id INTEGER PRIMARY KEY,
    inviter_id INTEGER,
    code TEXT,
    first_joined_at TEXT,
    last_joined_at TEXT,
    rewarded INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS quest_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id INTEGER,
    quest_title TEXT,
    user_id INTEGER,
    claimed_at TEXT
)
""")

conn.commit()


# =========================
# HELPERS
# =========================

def get_channel(guild, channel_id):
    return guild.get_channel(channel_id)


def has_admin_role(member):
    return any(role.id == ADMIN_ROLE_ID for role in member.roles)


def has_member_role(member):
    return any(role.id == MEMBER_ROLE_ID for role in member.roles)


def time_left(expires_at):
    now = datetime.now(UTC)
    exp = datetime.fromisoformat(expires_at)

    if now >= exp:
        return "Expired"

    remaining = exp - now
    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60

    return f"{remaining.days}d {hours}h {minutes}m Left"


def get_user_rank(member):

    if member.get_role(ADMIN_ROLE_ID):
        return "Admin (Unranked)"

    cursor.execute("""
    SELECT user_id
    FROM users
    ORDER BY velorax DESC
    """)

    users = cursor.fetchall()

    for index, (uid,) in enumerate(users, start=1):
        if uid == member.id:
            return index

    return "Unranked"


# =========================
# APPROVAL CONFIRMATION VIEW
# =========================
class ApprovalConfirmView(ui.View):

    def __init__(
        self,
        original_embed,
        original_view,
        user_id,
        inviter_id,
        username
    ):
        super().__init__(timeout=None)

        self.original_embed = original_embed
        self.original_view = original_view

        self.user_id = user_id
        self.inviter_id = inviter_id
        self.username = username
        self.ADMIN_ROLE_ID = ADMIN_ROLE_ID
        self.VERIFIED_ROLE_ID = MEMBER_ROLE_ID

    @ui.button(label="Yes", style=discord.ButtonStyle.success, custom_id="confirm_approve_yes")
    async def confirm_yes(self, interaction: discord.Interaction, button: ui.Button):

        guild = interaction.guild
        member = interaction.guild.get_member(self.user_id)
        inviter = interaction.guild.get_member(self.inviter_id)
        admin_role = interaction.guild.get_role(self.ADMIN_ROLE_ID)
        if admin_role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ Only Admins can click this button.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        for item in self.children:
            item.disabled = True

        await interaction.message.edit(view=self)

        # =========================
        # 1. GIVE ROLE TO USER
        # =========================
        try:
            verified_role = interaction.guild.get_role(self.VERIFIED_ROLE_ID)
            member = interaction.guild.get_member(self.user_id)

            if verified_role and member:
                await member.add_roles(
                    verified_role,
                    reason="Creator Approved"
                )
        except Exception as e:
            print(f"Role error: {e}")

        # =========================
        # 2. GIVE CREATOR POINTS
        # =========================
        cursor.execute("""
            UPDATE users
            SET points = COALESCE(points, 0) + 25
            WHERE user_id = ?
        """, (self.user_id,))

        conn.commit()

        # =========================
        # 5. CREATOR LOGS
        # =========================
        member_text = (
            member.mention
            if member
            else f"<@{self.user_id}>"
        )

        log_channel = guild.get_channel(LOGS_CHANNEL)
        if log_channel:
            await log_channel.send(
                f"🎉 **Creator Approved**\n\n"
                f"👤 **Member:** {member_text}\n"
                f"🪪 **Reward:** :gem: +25 Creator Points\n\n"
                f"👮 **Approved by:** {interaction.user.mention}"
            )

        # =========================
        # 7. MOVE TO APPROVED CHANNEL
        # =========================
        self.original_embed.color = discord.Color.blue()
        self.original_embed.title = "Creator Registration - Approved ✅"
        self.original_embed.add_field(
            name="Approved By",
            value=interaction.user.mention,
            inline=False
        )

        # =========================
        # 8. UPDATE ORIGINAL EMBED
        # =========================
        approved_channel = interaction.guild.get_channel(1507427342967115866)

        if approved_channel:
            await approved_channel.send(embed=self.original_embed)

        try:
            await interaction.message.delete()
        except:
            pass

    @ui.button(label="No", style=discord.ButtonStyle.danger, custom_id="confirm_approve_no")
    async def confirm_no(self, interaction: discord.Interaction, button: ui.Button):
        admin_role = interaction.guild.get_role(self.ADMIN_ROLE_ID)
        if admin_role not in interaction.user.roles:
            await interaction.response.send_message("❌ Only Admins can click this button.", ephemeral=True)
            return

        # Go back to the initial dashboard step
        await interaction.response.edit_message(embed=self.original_embed, view=self.original_view)


# =========================
# INITIAL REGISTRATION VIEW
# =========================
class CreatorReviewView(ui.View):

    def __init__(self, ):
        super().__init__(timeout=None)

        self.ADMIN_ROLE_ID = ADMIN_ROLE_ID

    @ui.button(label="Approved Creator", style=discord.ButtonStyle.primary, custom_id="trigger_approve_flow")
    async def approve_creator_click(self, interaction: discord.Interaction, button: ui.Button):
        admin_role = interaction.guild.get_role(self.ADMIN_ROLE_ID)
        if admin_role not in interaction.user.roles:
            await interaction.response.send_message("❌ Only Admins can click this button.", ephemeral=True)
            return

        await interaction.response.defer()

        embed = interaction.message.embeds[0]

        user_id = None
        inviter_id = None
        username = None

        for field in embed.fields:

            if field.name == "User ID":
                user_id = int(field.value)

            elif field.name == "Inviter ID":
                inviter_id = int(field.value)

            elif field.name == "Username":
                username = field.value

        # Create confirmation screen overlay setup
        member = interaction.guild.get_member(user_id)
        inviter = interaction.guild.get_member(inviter_id)

        confirm_embed = discord.Embed(
            title="⚠️ Action Confirmation Required",
            description=f"Are you sure you want to approve {member.mention if member else 'this creator'}?",
            color=discord.Color.orange()
        )

        confirm_view = ApprovalConfirmView(
            original_embed=interaction.message.embeds[0],
            original_view=self,
            user_id=user_id,
            inviter_id=inviter_id,
            username=username
        )

        await interaction.message.edit(
            embed=confirm_embed,
            view=confirm_view
        )

    @ui.button(label="Reject Creator", style=discord.ButtonStyle.danger, custom_id="reject_creator")
    async def reject_creator(self, interaction: discord.Interaction, button: ui.Button):
        admin_role = interaction.guild.get_role(ADMIN_ROLE_ID)
        if admin_role not in interaction.user.roles:
            await interaction.response.send_message("❌ Only Admins can do this.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]

        user_id = None

        for field in embed.fields:

            if field.name == "User ID":
                user_id = int(field.value)

        await interaction.response.send_modal(
            RejectCreatorModal(
                user_id,
                interaction.message
            )
        )


# =========================
# X MODAL
# =========================

class XModal(ui.Modal, title="Connect Your X"):
    username = ui.TextInput(
        label="X Username",
        placeholder="Enter your X username",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        original_username = str(self.username).replace("@", "").strip()

        lowercase_username = original_username.lower()

        if not re.match(r"^[A-Za-z0-9_]+$", original_username):
            await interaction.followup.send(
                "Invalid username.",
                ephemeral=True
            )
            return

        cursor.execute("""
        SELECT user_id FROM users
        WHERE user_id = ?
        """, (interaction.user.id,))

        existing_user = cursor.fetchone()
        is_new_user = False

        if existing_user:

            # Update details ONLY (No points given to existing accounts)
            cursor.execute("""
                    UPDATE users
                    SET x_username = ?,
                        x_username_lower = ?
                    WHERE user_id = ?
                    """, (
                original_username,
                lowercase_username,
                interaction.user.id
            ))


        else:

            approval_channel = interaction.guild.get_channel(

                INVITE_APPROVAL_CHANNEL_ID

            )

            if approval_channel:

                async for msg in approval_channel.history(limit=500):

                    if not msg.embeds:
                        continue

                    existing_embed = msg.embeds[0]

                    for field in existing_embed.fields:

                        if (

                                field.name == "User ID"

                                and field.value == str(interaction.user.id)

                        ):
                            await interaction.followup.send(

                                "❌ You already have a pending creator application.",

                                ephemeral=True

                            )

                            return

            is_new_user = True

            cursor.execute("""

                    INSERT INTO users (

                        user_id,

                        x_username,

                        x_username_lower,

                        points,

                        gold_points,

                        quests_completed,

                        quests_denied

                    )

                    VALUES (?, ?, ?, 0, 0, 0, 0)

                    """, (

                interaction.user.id,

                original_username,

                lowercase_username

            ))

        conn.commit()

        # =========================
        # SYNC NICKNAME
        # =========================

        try:
            await interaction.user.edit(
                nick=original_username,
                reason="X account sync"
            )
        except discord.Forbidden:
            print("Missing nickname permission.")
        except Exception as e:
            print(e)

        # =========================
        # ADD VERIFIED ROLE
        # =========================

        try:

            verified_role = interaction.guild.get_role(
                VERIFIED_ROLE_ID
            )

            if verified_role:
                await interaction.user.add_roles(
                    verified_role,
                    reason="Connected X account"
                )


        except discord.Forbidden:

            print("Missing role permission.")

        except Exception as e:

            print(e)

        # =========================
        # SUCCESS RESPONSE (UPDATED WITH STYLIZED NAME & POINTS)
        # =========================
        # Dynamically look up your stylized channel name

        quest_channel = guild.get_channel(QUEST_CHANNEL)
        quest_channel_mention = quest_channel.mention if quest_channel else "#ǫᴜᴇsᴛ"

        log_text = None

        # Build dynamic response message based on reward eligibility
        if is_new_user:
            success_message = (
                f"🔄 **Your X account is now under review!** Connected as @{original_username}\n\n"
                f"⚠️ Your account is pending admin approval.\n"
                f"If approved, you will receive:\n"
                f"• :gem: 25 Creator Points\n"
                f"• Access to creator features to Earn :moneybag: and exchange into Cash\n\n"
                f"You will be notified once your account has been reviewed."
            )

        else:
            success_message = (
                f"🔄 **Your X username has been updated!** Connected as @{original_username}\n\n"
                f"⚠️ Important: Always update your X username here if you change it on X/Twitter."
            )

            log_text = (
                f"🔄 **X Username Update**: {interaction.user.mention} updated to `@{original_username}`"
            )

        cursor.execute("""
                                        SELECT inviter_id, rewarded
                                        FROM invite_joins
                                        WHERE invited_id = ?
                                        ORDER BY last_joined_at DESC
                                        LIMIT 1
                                        """, (interaction.user.id,))

        invite_data = cursor.fetchone()

        approval_message = None

        if invite_data and is_new_user:
            inviter_id, rewarded = invite_data

            inviter = interaction.guild.get_member(inviter_id)
            if not inviter:
                inviter = await interaction.client.fetch_user(inviter_id)

            approval_channel = interaction.guild.get_channel(INVITE_APPROVAL_CHANNEL_ID)

            if inviter and approval_channel:
                embed = discord.Embed(
                    title="New Creator Registration",
                    color=discord.Color.green()
                )

                embed.set_thumbnail(url=interaction.user.display_avatar.url)

                embed.add_field(
                    name="New Member",
                    value=interaction.user.mention,
                    inline=False
                )

                embed.add_field(
                    name="Invited By",
                    value=inviter.mention,
                    inline=False
                )

                embed.add_field(
                    name="X Profile",
                    value=f"https://x.com/{original_username}",
                    inline=False
                )

                embed.add_field(
                    name="User ID",
                    value=str(interaction.user.id),
                    inline=False
                )

                embed.add_field(
                    name="Inviter ID",
                    value=str(inviter.id),
                    inline=False
                )

                embed.add_field(
                    name="Username",
                    value=original_username,
                    inline=False
                )

                view = CreatorReviewView()

                await approval_channel.send(embed=embed, view=view)

        await interaction.followup.send(success_message, ephemeral=True)

        # Dynamic lookup for your stylized log channel name
        try:
            log_channel = guild.get_channel(LOGS_CHANNEL)
            if log_channel and log_text:
                await log_channel.send(log_text)
        except Exception as e:
            print(f"Failed to send log message: {e}")


class InviteApprovalView(ui.View):

    def __init__(self, user_id: int, inviter_id: int, username: str):
        super().__init__(timeout=None)

        self.user_id = user_id
        self.inviter_id = inviter_id
        self.username = username

        # LINK BUTTON (static URL button)
        self.add_item(
            ui.Button(
                label="Review Profile",
                url=f"https://x.com/{username}",
                style=discord.ButtonStyle.link
            )
        )

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):

        admin_role = interaction.guild.get_role(ADMIN_ROLE_ID)

        if admin_role not in interaction.user.roles:
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        member_role = interaction.guild.get_role(MEMBER_ROLE_ID)
        user = interaction.guild.get_member(self.user_id)

        if user and member_role:
            await user.add_roles(member_role)

        # +25 points
        cursor.execute("""
        UPDATE users
        SET points = points + 25
        WHERE user_id = ?
        """, (self.user_id,))

        rewarded = 0

        conn.commit()

        await interaction.response.send_message("Approved.", ephemeral=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):

        admin_role = interaction.guild.get_role(ADMIN_ROLE_ID)

        if admin_role not in interaction.user.roles:
            await interaction.response.send_message("No permission.", ephemeral=True)
            return

        cursor.execute("""
        UPDATE invite_joins
        SET rewarded = -1
        WHERE invited_id = ?
        """, (self.user_id,))

        conn.commit()

        await interaction.response.send_message("Rejected.", ephemeral=True)

class RejectCreatorModal(ui.Modal):

    def __init__(self, user_id, message):
        super().__init__(title="Reject Creator")
        self.user_id = user_id
        self.message = message

        self.reason = ui.TextInput(
            label="Reason",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )

        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        member = interaction.guild.get_member(
            self.user_id
        )

        if not member:
            try:
                member = await interaction.guild.fetch_member(
                    self.user_id
                )
            except:
                member = None

        cursor.execute("""
        DELETE FROM users
        WHERE user_id = ?
        """, (self.user_id,))

        conn.commit()

        waiting_room = interaction.guild.get_channel(
            WAITING_ROOM_CHANNEL
        )

        mention = (
            member.mention
            if member
            else f"<@{self.user_id}>"
        )

        await waiting_room.send(
            f"{mention}\n\n"
            f"❌ Your creator application has been denied for now.\n\n"
            f"Reason: {self.reason}\n\n"
            f"👮 Denied By: {interaction.user.mention}\n\n"
            f"You may update your X account and apply again once it meets our requirements."
        )

        try:
            await self.message.delete()
        except:
            pass

        await interaction.followup.send(
            "❌ Creator application rejected.",
            ephemeral=True
        )

# =========================
# REGISTER BUTTON
# =========================

class RegisterView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="ᴄᴏɴɴᴇᴄᴛ x",
        style=discord.ButtonStyle.blurple,
        custom_id="persistent_connect_x"
    )
    async def connect_x(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(XModal())


# =========================
# INVITES VIEW (PERSISTENT & UNIQUE CODES)
# =========================

class InviteView(ui.View):

    def __init__(self):
        # timeout=None keeps the button listening indefinitely across bot reboots
        super().__init__(timeout=None)

    @ui.button(
        label="Generate Invite",
        style=discord.ButtonStyle.green,
        custom_id="generate_invite"  # Keep this exact custom_id registered in on_ready!
    )
    async def generate_invite(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):
        # 1. Fetch the absolute oldest generated code for this specific user
        cursor.execute("""
        SELECT code FROM invites
        WHERE inviter_id = ?
        ORDER BY created_at ASC 
        LIMIT 1
        """, (interaction.user.id,))

        existing = cursor.fetchone()

        # 2. If they already have a code in the DB, give it to them directly
        if existing:
            await interaction.response.send_message(
                f"Your permanent invite link:\nhttps://discord.gg/{existing[0]}",
                ephemeral=True
            )
            return

        # 3. Only run this if they have absolutely zero history in the system
        try:
            invite = await interaction.channel.create_invite(
                max_age=0,  # Never expires
                max_uses=0,  # Infinite uses
                unique=True  # Guarantees a brand new code unique to them
            )

            # 4. Save the base anchor row. invited_id is left NULL initially
            # SAVE JOIN RECORD

            cursor.execute("""
            INSERT INTO invites (
                code,
                inviter_id,
                created_at
            )
            VALUES (?, ?, ?)
            """, (
                invite.code,
                interaction.user.id,
                datetime.now(UTC).isoformat()
            ))

            conn.commit()

            await interaction.response.send_message(
                f"Your brand new invite link:\n{invite.url}",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I do not have permission to create invite links in this channel.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Error creating invite: {e}")
            await interaction.response.send_message(
                "❌ An unexpected error occurred while generating your link.",
                ephemeral=True
            )


# =========================
# SUBMIT QUEST MODAL
# =========================

class SubmitQuestModal(ui.Modal):

    def __init__(self, quest_id, tweet_link):
        super().__init__(title=f"Submit Quest #{quest_id}")

        self.quest_id = quest_id
        self.tweet_link = tweet_link

        self.reply_link = ui.TextInput(
            label="Reply Link",
            placeholder="Paste your reply link here",
            required=True
        )

        self.add_item(self.reply_link)

    async def on_submit(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        # =========================
        # CHECK QUEST EXPIRATION
        # =========================

        cursor.execute("""
        SELECT current_claims, max_claims, completed
        FROM quests
        WHERE quest_id = ?
        """, (self.quest_id,))

        quest_data = cursor.fetchone()

        if not quest_data:
            await interaction.followup.send(
                "Quest not found.",
                ephemeral=True
            )
            return

        current_claims = quest_data[0]
        max_claims = quest_data[1]
        completed = quest_data[2]

        if completed or current_claims >= max_claims:
            await interaction.followup.send(
                "❌ This quest is already full.",
                ephemeral=True
            )
            return

        # =========================
        # GET USER REGISTERED X USERNAME
        # =========================

        cursor.execute("""
        SELECT x_username
        FROM users
        WHERE user_id = ?
        """, (interaction.user.id,))

        row = cursor.fetchone()

        if not row or not row[0]:
            await interaction.followup.send(
                "❌ You must connect your X account first.",
                ephemeral=True
            )
            return

        registered_username = row[0].lower()

        # =========================
        # CHECK APPROVED
        # =========================

        cursor.execute("""
        SELECT id FROM submissions
        WHERE quest_id = ?
        AND user_id = ?
        AND status = 'approved'
        """, (
            self.quest_id,
            interaction.user.id
        ))

        approved = cursor.fetchone()

        if approved:
            await interaction.followup.send(
                "You already completed this quest.",
                ephemeral=True
            )
            return

        # =========================
        # CHECK PENDING
        # =========================

        cursor.execute("""
        SELECT id FROM submissions
        WHERE quest_id = ?
        AND user_id = ?
        AND status = 'pending'
        """, (
            self.quest_id,
            interaction.user.id
        ))

        pending = cursor.fetchone()

        if pending:
            await interaction.followup.send(
                "Your submission is still pending.",
                ephemeral=True
            )
            return

        # =========================
        # VALIDATE REPLY LINK
        # =========================

        submitted_link = str(self.reply_link).strip().lower()

        expected_link = f"https://x.com/{registered_username}/status"

        if not submitted_link.startswith(expected_link):
            await interaction.followup.send(
                f"❌ Invalid reply link.\n\n"
                f"You must submit your own X reply:\n{expected_link}",
                ephemeral=True
            )
            return

        # =========================
        # INSERT SUBMISSION
        # =========================

        cursor.execute("""
        INSERT INTO submissions (
            quest_id,
            user_id,
            reply_link,
            status
        )
        VALUES (?, ?, ?, ?)
        """, (
            self.quest_id,
            interaction.user.id,
            str(self.reply_link),
            "pending"
        ))

        submission_id = cursor.lastrowid

        conn.commit()

        guild = interaction.guild

        approval_channel = get_channel(
            guild,
            VIP_APPROVAL_CHANNEL
        )

        review_title = f"Quest #{self.quest_id} Submission"

        embed = discord.Embed(
            title=review_title,
            color=discord.Color.orange()
        )


        embed.set_thumbnail(
            url=interaction.user.display_avatar.url
        )

        embed.add_field(
            name="User",
            value=interaction.user.mention,
            inline=False
        )

        embed.add_field(
            name="Reply Link",
            value=str(self.reply_link),
            inline=False
        )

        approval_message = await approval_channel.send(
            embed=embed,
            view=ApprovalView(
                interaction.user.id,
                self.quest_id,
                submission_id
            )
        )

        # SAVE APPROVAL MESSAGE ID

        cursor.execute("""
        UPDATE submissions
        SET approval_message_id = ?
        WHERE id = ?
        """, (
            approval_message.id,
            submission_id
        ))

        conn.commit()

        # =========================
        # GET QUEST INFO
        # =========================

        cursor.execute("""
        SELECT
            title,
            current_claims,
            max_claims,
            message_id
        FROM quests
        WHERE quest_id = ?
        """, (self.quest_id,))

        quest_info = cursor.fetchone()

        quest_title = quest_info[0]
        current_claims = quest_info[1]
        max_claims = quest_info[2]
        quest_message_id = quest_info[3]

        # =========================
        # SUBMISSION QUEUE LOG
        # =========================

        queue_channel = interaction.guild.get_channel(
            SUBMISSION_QUEUE_CHANNEL
        )

        queue_embed = discord.Embed(
            title="🕒 Paid Quest Submission Queue",
            color=discord.Color.orange()
        )

        queue_embed.add_field(
            name="Quest",
            value=(
                f"**Quest #{self.quest_id} - {quest_title}**\n"
                f"[Jump to Quest]"
                f"(https://discord.com/channels/"
                f"{interaction.guild.id}/"
                f"{PAID_QUEST_CHANNEL}/"
                f"{quest_message_id})"
            ),
            inline=False
        )

        queue_embed.add_field(
            name="Member",
            value=interaction.user.mention,
            inline=False
        )

        queue_embed.add_field(
            name="Slots",
            value=f"{current_claims}/{max_claims}",
            inline=False
        )

        queue_embed.add_field(
            name="Submission",
            value=f"[View Submission]({approval_message.jump_url})",
            inline=False
        )

        queue_embed.add_field(
            name="Status",
            value="🟡 Under Review",
            inline=False
        )

        queue_embed.set_thumbnail(
            url=interaction.user.display_avatar.url
        )

        queue_log_message = await queue_channel.send(
            embed=queue_embed
        )

        # SAVE APPROVAL MESSAGE ID

        cursor.execute("""
        UPDATE submissions
        SET
            approval_message_id = ?,
            queue_message_id = ?
        WHERE id = ?
        """, (
            approval_message.id,
            queue_log_message.id,
            submission_id
        ))

        conn.commit()

        await interaction.followup.send(
            "Quest submitted successfully.",
            ephemeral=True
        )


# =========================
# QUEST VIEW
# =========================

class QuestView(ui.View):

    def __init__(self, quest_id, tweet_link):
        super().__init__(timeout=None)

        self.quest_id = quest_id
        self.tweet_link = tweet_link

        # RAID LINK BUTTON

        self.add_item(
            ui.Button(
                label="Raid Link",
                style=discord.ButtonStyle.link,
                url=tweet_link
            )
        )

        self.add_item(
            SubmitQuestButton(quest_id)
        )

class SubmitQuestButton(ui.Button):

    def __init__(self, quest_id):
        super().__init__(
            label="Submit Quest",
            style=discord.ButtonStyle.green,
            custom_id=f"submit_quest_{quest_id}"
        )

        self.quest_id = quest_id

    async def callback(self, interaction: discord.Interaction):

        cursor.execute("""
        SELECT
            expires_at,
            quest_type,
            proof_thread_id,
            tweet_link,
            priority_until
        FROM quests
        WHERE quest_id = ?
        """, (self.quest_id,))

        quest = cursor.fetchone()

        if not quest:
            await interaction.response.send_message(
                "Quest not found.",
                ephemeral=True
            )
            return

        priority_until = quest[4]

        if priority_until:

            priority_until = datetime.fromisoformat(
                priority_until
            )

            if datetime.now(UTC) < priority_until:

                elite_role = interaction.guild.get_role(
                    ELITE_CREATOR_ROLE_ID
                )

                if elite_role not in interaction.user.roles:
                    remaining = int(
                        (
                                priority_until -
                                datetime.now(UTC)
                        ).total_seconds() / 60
                    )

                    await interaction.response.send_message(
                        f"🔒 Elite Creator Early Access\n\n"
                        f"This quest is exclusive to Elite Creators.\n"
                        f"Available to everyone in "
                        f"{remaining} minutes.",
                        ephemeral=True
                    )

                    return

        expires_at = quest[0]

        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)

        quest_type = quest[1]
        proof_thread_id = quest[2]
        tweet_link = quest[3]

        # =========================
        # FOLLOW / RETWEET
        # =========================

        if quest_type in ["follow", "retweet"]:

            thread = interaction.guild.get_thread(
                proof_thread_id
            )

            if not thread:
                await interaction.response.send_message(
                    "Proof thread not found.",
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                f"📸 Upload your screenshot proof here:\n"
                f"{thread.jump_url}",
                ephemeral=True
            )

            return

        # =========================
        # NORMAL QUEST
        # =========================

        await interaction.response.send_modal(
            SubmitQuestModal(
                self.quest_id,
                tweet_link
            )
        )

async def send_quest_report(guild, quest_id):

    cursor.execute("""
    SELECT
        s.user_id,
        u.x_username,
        s.reply_link,
        s.status
    FROM submissions s
    LEFT JOIN users u
        ON s.user_id = u.user_id
    WHERE s.quest_id = ?
    """, (quest_id,))

    submissions = cursor.fetchall()

    wb = Workbook()
    ws = wb.active

    ws.title = f"Quest {quest_id}"

    ws.append([
        "Discord User ID",
        "Discord Username",
        "X Username",
        "Reply Link",
        "Status"
    ])

    for row in submissions:

        user_id = row[0]

        member = guild.get_member(user_id)

        discord_username = (
            str(member)
            if member
            else str(user_id)
        )

        ws.append([
            user_id,
            discord_username,
            row[1],
            row[2],
            row[3]
        ])

    filename = f"quest_{quest_id}_report.xlsx"

    wb.save(filename)

    admin_channel = guild.get_channel(
        ADMIN_LOG_CHANNEL
    )

    if admin_channel:

        await admin_channel.send(
            f"📊 Quest #{quest_id} completed.",
            file=discord.File(filename)
        )

    os.remove(filename)

# =========================
# APPROVAL VIEW
# =========================

class ApprovalView(ui.View):

    def __init__(self, user_id, quest_id, submission_id):
        super().__init__(timeout=None)

        self.user_id = user_id
        self.quest_id = quest_id
        self.submission_id = submission_id

        # =========================
        # APPROVE BUTTON
        # =========================

        approve_button = ui.Button(
            label="ᴀᴘᴘʀᴏᴠᴇ",
            style=discord.ButtonStyle.green,
            custom_id=f"approve_{submission_id}"
        )

        async def approve_callback(interaction: discord.Interaction):

            if not has_admin_role(interaction.user):
                await interaction.response.send_message(
                    "No permission.",
                    ephemeral=True
                )
                return

            cursor.execute("""
            SELECT status FROM submissions
            WHERE id = ?
            """, (self.submission_id,))

            submission = cursor.fetchone()

            if not submission:
                await interaction.response.send_message(
                    "Submission not found.",
                    ephemeral=True
                )
                return

            if submission[0] == "approved":
                await interaction.response.send_message(
                    "Already approved.",
                    ephemeral=True
                )
                return

            # =========================
            # CHECK IF QUEST IS FILLED
            # =========================

            cursor.execute("""
            SELECT current_claims, max_claims
            FROM quests
            WHERE quest_id = ?
            """, (self.quest_id,))

            quest_limits = cursor.fetchone()

            current_claims = quest_limits[0]
            max_claims = quest_limits[1]

            if current_claims >= max_claims:

                # UPDATE SUBMISSION STATUS
                cursor.execute("""
                UPDATE submissions
                SET status = 'filled'
                WHERE id = ?
                """, (self.submission_id,))

                conn.commit()

                # DISABLED VIEW
                filled_view = ui.View(timeout=None)

                # APPROVE DISABLED

                filled_view.add_item(
                    ui.Button(
                        label="ᴀᴘᴘʀᴏᴠᴇ",
                        style=discord.ButtonStyle.green,
                        disabled=True
                    )
                )

                # DENY DISABLED

                filled_view.add_item(
                    ui.Button(
                        label="ᴅᴇɴʏ",
                        style=discord.ButtonStyle.red,
                        disabled=True
                    )
                )

                # FILLED ENABLED

                quest_filled_button = ui.Button(
                    label="Qᴜᴇsᴛ Fɪʟʟᴇᴅ",
                    style=discord.ButtonStyle.secondary,
                    disabled=False
                )

                quest_filled_button.callback = filled_callback

                filled_view.add_item(quest_filled_button)

                await interaction.message.edit(
                    view=filled_view
                )

                # UPDATE QUEUE EMBED
                cursor.execute("""
                SELECT queue_message_id
                FROM submissions
                WHERE id = ?
                """, (self.submission_id,))

                queue_data = cursor.fetchone()

                if queue_data and queue_data[0]:

                    queue_channel = interaction.guild.get_channel(
                        SUBMISSION_QUEUE_CHANNEL
                    )

                    try:

                        queue_message = await queue_channel.fetch_message(
                            queue_data[0]
                        )

                        filled_embed = discord.Embed(
                            title="⚠️ Quest Filled",
                            color=discord.Color.orange()
                        )

                        filled_embed.add_field(
                            name="Quest",
                            value=f"**Quest #{self.quest_id}**",
                            inline=False
                        )

                        filled_embed.add_field(
                            name="Member",
                            value=f"<@{self.user_id}>",
                            inline=False
                        )

                        filled_embed.add_field(
                            name="Status",
                            value="Quest already filled before review.",
                            inline=False
                        )

                        filled_embed.add_field(
                            name="Processed By",
                            value=interaction.user.mention,
                            inline=False
                        )

                        await queue_message.edit(
                            embed=filled_embed
                        )

                    except Exception as e:
                        print(f"Filled embed update error: {e}")

                await interaction.response.send_message(
                    "Quest already filled.",
                    ephemeral=True
                )

                return

            # =========================
            # UPDATE STATUS
            # =========================

            cursor.execute("""
            UPDATE submissions
            SET status = 'approved',
                completed_at = ?
            WHERE id = ?
            AND status != 'approved'
            """, (
                datetime.now(UTC).isoformat(),
                self.submission_id
            ))

            cursor.execute("""
            SELECT inviter_id
            FROM invite_joins
            WHERE invited_id = ?
            AND rewarded = 0
            LIMIT 1
            """, (self.user_id,))

            result = cursor.fetchone()

            if result:
                inviter_id = result[0]

                cursor.execute("""
                UPDATE users
                SET gold_points = gold_points + 1
                WHERE user_id = ?
                """, (inviter_id,))

                cursor.execute("""
                UPDATE invite_joins
                SET rewarded = 1
                WHERE invited_id = ?
                """, (self.user_id,))

                # Fetch updated total
                cursor.execute("""
                SELECT gold_points
                FROM users
                WHERE user_id = ?
                """, (inviter_id,))

                gold_result = cursor.fetchone()

                total_gold = (
                    gold_result[0]
                    if gold_result
                    else 0
                )

                inviter = interaction.guild.get_member(inviter_id)

                if inviter:
                    gold_log_channel = interaction.guild.get_channel(
                        GOLD_LOGS_CHANNEL
                    )

                    if gold_log_channel:
                        await gold_log_channel.send(
                            f"🎉 **Invite Reward Released**\n\n"
                            f"👤 **Creator:** <@{self.user_id}>\n"
                            f"👑 **Inviter:** {inviter.mention}\n\n"
                            f"💰 **Reward Earned:** :moneybag: +1 Gold Points\n"
                            f"📊 **Inviter Total Gold:** :moneybag: {total_gold}\n\n"
                            f"✅ Triggered after the creator's first approved paid quest."
                        )

            # =========================
            # INCREASE CLAIM COUNT
            # =========================

            cursor.execute("""
            UPDATE quests
            SET current_claims = current_claims + 1
            WHERE quest_id = ?
            """, (self.quest_id,))

            # =========================
            # ADD POINT + QUEST COUNT
            # =========================

            cursor.execute("""
            SELECT reward_points
            FROM quests
            WHERE quest_id = ?
            """, (self.quest_id,))

            quest_data = cursor.fetchone()

            reward_points = (
                quest_data[0]
                if quest_data
                else 1
            )

            cursor.execute("""
            UPDATE users
            SET gold_points = gold_points + ?,
                quests_completed = quests_completed + 1
            WHERE user_id = ?
            """, (reward_points, self.user_id,))

            conn.commit()

            cursor.execute("""
            SELECT
                title,
                current_claims,
                max_claims
            FROM quests
            WHERE quest_id = ?
            """, (self.quest_id,))

            quest_info = cursor.fetchone()

            quest_title = quest_info[0]
            updated_claims = quest_info[1]
            updated_max = quest_info[2]

            # =========================
            # UPDATE MAIN QUEST EMBED
            # =========================

            cursor.execute("""
            SELECT
                message_id,
                ping_message_id,
                tweet_link,
                reward_points
            FROM quests
            WHERE quest_id = ?
            """, (self.quest_id,))

            quest_main_data = cursor.fetchone()

            message_id = quest_main_data[0]
            ping_message_id = quest_main_data[1]
            tweet_link = quest_main_data[2]
            reward_points = quest_main_data[3]

            try:

                quest_channel = interaction.guild.get_channel(
                    PAID_QUEST_CHANNEL
                )

                quest_message = await quest_channel.fetch_message(
                    message_id
                )

                # QUEST COMPLETED

                if updated_claims >= updated_max:

                    # =========================
                    # DISABLE OTHER APPROVALS
                    # =========================

                    cursor.execute("""
                    SELECT approval_message_id
                    FROM submissions
                    WHERE quest_id = ?
                    AND status = 'pending'
                    """, (self.quest_id,))

                    pending_messages = cursor.fetchall()

                    approval_channel = interaction.guild.get_channel(
                        VIP_APPROVAL_CHANNEL
                    )

                    for msg in pending_messages:

                        try:

                            approval_message = await approval_channel.fetch_message(
                                msg[0]
                            )

                            filled_view = ui.View(timeout=None)

                            # APPROVE DISABLED

                            filled_view.add_item(
                                ui.Button(
                                    label="ᴀᴘᴘʀᴏᴠᴇ",
                                    style=discord.ButtonStyle.green,
                                    disabled=True
                                )
                            )

                            # DENY DISABLED

                            filled_view.add_item(
                                ui.Button(
                                    label="ᴅᴇɴʏ",
                                    style=discord.ButtonStyle.red,
                                    disabled=True
                                )
                            )

                            # FILLED ENABLED

                            quest_filled_button = ui.Button(
                                label="Qᴜᴇsᴛ Fɪʟʟᴇᴅ",
                                style=discord.ButtonStyle.secondary
                            )

                            async def filled_only_callback(
                                    interaction: discord.Interaction,
                                    submission_message=approval_message,
                                    submission_message_id=msg[0]
                            ):

                                # =========================
                                # GET SUBMISSION DATA
                                # =========================

                                cursor.execute("""
                                SELECT
                                    submissions.id,
                                    submissions.user_id,
                                    submissions.queue_message_id,
                                    quests.title
                                FROM submissions
                                JOIN quests
                                ON submissions.quest_id = quests.quest_id
                                WHERE approval_message_id = ?
                                """, (submission_message_id,))

                                filled_data = cursor.fetchone()

                                if not filled_data:
                                    await interaction.response.send_message(
                                        "Submission not found.",
                                        ephemeral=True
                                    )
                                    return

                                filled_submission_id = filled_data[0]
                                filled_user_id = filled_data[1]
                                queue_message_id = filled_data[2]
                                filled_quest_title = filled_data[3]

                                # =========================
                                # UPDATE STATUS
                                # =========================

                                cursor.execute("""
                                UPDATE submissions
                                SET status = 'filled'
                                WHERE id = ?
                                """, (filled_submission_id,))

                                conn.commit()

                                # =========================
                                # UPDATE QUEUE EMBED
                                # =========================

                                if queue_message_id:

                                    queue_channel = interaction.guild.get_channel(
                                        SUBMISSION_QUEUE_CHANNEL
                                    )

                                    try:

                                        queue_message = await queue_channel.fetch_message(
                                            queue_message_id
                                        )

                                        filled_embed = discord.Embed(
                                            title="⚠️ Quest Filled",
                                            color=discord.Color.orange()
                                        )

                                        filled_embed.add_field(
                                            name="Quest",
                                            value=f"**Quest #{self.quest_id} - {filled_quest_title}**",
                                            inline=False
                                        )

                                        filled_embed.add_field(
                                            name="Member",
                                            value=f"<@{filled_user_id}>",
                                            inline=False
                                        )

                                        filled_embed.add_field(
                                            name="Status",
                                            value="Quest was already filled before approval.",
                                            inline=False
                                        )

                                        filled_embed.add_field(
                                            name="Processed By",
                                            value=interaction.user.mention,
                                            inline=False
                                        )

                                        member = interaction.guild.get_member(
                                            filled_user_id
                                        )

                                        if member:
                                            filled_embed.set_thumbnail(
                                                url=member.display_avatar.url
                                            )

                                        filled_embed.set_footer(
                                            text="Submission marked as filled."
                                        )

                                        await queue_message.edit(
                                            embed=filled_embed
                                        )

                                    except Exception as e:

                                        print(f"Filled queue update error: {e}")

                                # =========================
                                # DELETE APPROVAL MESSAGE
                                # =========================

                                await submission_message.delete()

                                await interaction.response.send_message(
                                    "Submission marked as quest filled.",
                                    ephemeral=True
                                )

                            quest_filled_button.callback = filled_only_callback

                            filled_view.add_item(quest_filled_button)

                            await approval_message.edit(
                                view=filled_view
                            )

                        except Exception as e:

                            print(f"Pending approval update error: {e}")

                    cursor.execute("""
                    UPDATE quests
                    SET completed = 1
                    WHERE quest_id = ?
                    """, (self.quest_id,))

                    # =========================
                    # LOCK PROOF THREAD
                    # =========================

                    cursor.execute("""
                    SELECT proof_thread_id
                    FROM quests
                    WHERE quest_id = ?
                    """, (self.quest_id,))

                    thread_data = cursor.fetchone()

                    if thread_data and thread_data[0]:

                        try:

                            proof_thread = interaction.guild.get_thread(
                                thread_data[0]
                            )

                            if proof_thread:
                                await proof_thread.edit(
                                    locked=True,
                                    archived=True
                                )

                        except Exception as e:

                            print(f"Proof thread lock error: {e}")
                    conn.commit()

                    await send_quest_report(
                        interaction.guild,
                        self.quest_id
                    )

                    completed_embed = discord.Embed(
                        title=f"Quest #{self.quest_id} - {quest_title}",
                        color=discord.Color.dark_grey()
                    )

                    completed_embed.add_field(
                        name="Status",
                        value="✅ COMPLETED",
                        inline=False
                    )

                    completed_embed.add_field(
                        name="Claims",
                        value=f"{updated_claims}/{updated_max}",
                        inline=False
                    )

                    completed_embed.add_field(
                        name="Reward",
                        value=f":moneybag: {reward_points} Gold Points",
                        inline=False
                    )

                    completed_embed.add_field(
                        name="Raid Link",
                        value=f"[Click Here to Raid]({tweet_link})",
                        inline=False
                    )

                    completed_embed.set_footer(
                        text="This quest has reached maximum claims."
                    )

                    disabled_view = ui.View(timeout=None)

                    disabled_view.add_item(
                        ui.Button(
                            label="Raid Link",
                            url=tweet_link,
                            style=discord.ButtonStyle.link
                        )
                    )

                    disabled_view.add_item(
                        ui.Button(
                            label="Quest Filled",
                            style=discord.ButtonStyle.secondary,
                            disabled=True
                        )
                    )

                    await quest_message.edit(
                        embed=completed_embed,
                        view=disabled_view
                    )

                    # DELETE PING MESSAGE

                    try:

                        if ping_message_id:
                            ping_message = await quest_channel.fetch_message(
                                ping_message_id
                            )

                            await ping_message.delete()

                    except:
                        pass

                # STILL AVAILABLE

                else:

                    updated_embed = discord.Embed(
                        title=f"Quest #{self.quest_id} - {quest_title}",
                        color=0x2ECC71
                    )

                    updated_embed.add_field(
                        name="Available Claims",
                        value=f"{updated_claims}/{updated_max}",
                        inline=False
                    )

                    updated_embed.add_field(
                        name="Reward",
                        value=f":moneybag: {reward_points} Gold Points",
                        inline=False
                    )

                    updated_embed.add_field(
                        name="Raid Link",
                        value=f"[Click Here to Raid]({tweet_link})",
                        inline=False
                    )

                    await quest_message.edit(
                        embed=updated_embed,
                        view=QuestView(
                            self.quest_id,
                            tweet_link
                        )
                    )

            except Exception as e:

                print(f"Quest embed update error: {e}")

            cursor.execute("""
            SELECT queue_message_id
            FROM submissions
            WHERE id = ?
            """, (self.submission_id,))

            queue_data = cursor.fetchone()

            if queue_data and queue_data[0]:

                queue_channel = interaction.guild.get_channel(
                    SUBMISSION_QUEUE_CHANNEL
                )

                try:

                    queue_message = await queue_channel.fetch_message(
                        queue_data[0]
                    )

                    approved_embed = discord.Embed(
                        title="✅ Submission Approved",
                        color=discord.Color.green()
                    )

                    approved_embed.add_field(
                        name="",
                        value=(
                            f"**Quest #{self.quest_id} - {quest_title}**"
                        ),
                        inline=False
                    )

                    approved_embed.add_field(
                        name="Member",
                        value=f"<@{self.user_id}>",
                        inline=False
                    )

                    approved_embed.add_field(
                        name="Reward",
                        value=f":moneybag: {reward_points} Gold Points",
                        inline=False
                    )

                    approved_embed.add_field(
                        name="Slots",
                        value=f"{updated_claims}/{updated_max}",
                        inline=False
                    )

                    approved_embed.add_field(
                        name="Status",
                        value="✅ Approved",
                        inline=False
                    )

                    approved_embed.add_field(
                        name="Processed By",
                        value=interaction.user.mention,
                        inline=False
                    )

                    member = interaction.guild.get_member(
                        self.user_id
                    )

                    if member:
                        approved_embed.set_thumbnail(
                            url=member.display_avatar.url
                        )

                    approved_embed.set_footer(
                        text="Submission successfully approved."
                    )

                    await queue_message.edit(
                        embed=approved_embed
                    )


                except Exception as e:

                    print(f"Queue embed update error: {e}")

            # GET POINTS

            cursor.execute("""
            SELECT gold_points FROM users
            WHERE user_id = ?
            """, (self.user_id,))

            gold_points = cursor.fetchone()[0]

            # =========================
            # GET QUEST TITLE
            # =========================

            cursor.execute("""
            SELECT title
            FROM quests
            WHERE quest_id = ?
            """, (self.quest_id,))

            quest_data = cursor.fetchone()

            quest_title = (
                quest_data[0]
                if quest_data and quest_data[0]
                else "Untitled Quest"
            )

            # =========================
            # CHANNELS + USER
            # =========================

            logs_channel = get_channel(
                interaction.guild,
                GOLD_LOGS_CHANNEL
            )

            member = interaction.guild.get_member(
                self.user_id
            )

            await logs_channel.send(
                f"{member.mention} completed "
                f"**Quest #{self.quest_id} - {quest_title}** "
                f"and earned :moneybag:  {reward_points} **Gold Points**\n\n"
                f"Approved by: {interaction.user.mention}\n"
                f"Total Gold Points: :moneybag: {gold_points}"
            )

            await interaction.message.delete()

        approve_button.callback = approve_callback

        self.add_item(approve_button)

        # =========================
        # DENY BUTTON
        # =========================

        deny_button = ui.Button(
            label="ᴅᴇɴʏ",
            style=discord.ButtonStyle.red,
            custom_id=f"deny_{submission_id}"
        )

        async def deny_callback(interaction: discord.Interaction):

            if not has_admin_role(interaction.user):
                await interaction.response.send_message(
                    "No permission.",
                    ephemeral=True
                )
                return

            await interaction.response.send_modal(
                DenyReasonModal(self, interaction.message)
            )

        deny_button.callback = deny_callback

        self.add_item(deny_button)

        # =========================
        # DENY REASON MODAL
        # =========================

        class DenyReasonModal(ui.Modal):

            def __init__(self, approval_view, approval_message):
                super().__init__(title="Deny Submission")

                self.approval_view = approval_view
                self.approval_message = approval_message

                self.reason = ui.TextInput(
                    label="Reason for denial",
                    placeholder="Explain why this submission was denied...",
                    style=discord.TextStyle.paragraph,
                    required=True,
                    max_length=500
                )

                self.add_item(self.reason)

            async def on_submit(self, interaction: discord.Interaction):

                view = self.approval_view

                # =========================
                # UPDATE SUBMISSION
                # =========================

                cursor.execute("""
                            UPDATE submissions
                            SET status = 'denied'
                            WHERE id = ?
                            """, (view.submission_id,))

                cursor.execute("""
                            UPDATE users
                            SET quests_denied = quests_denied + 1
                            WHERE user_id = ?
                            """, (view.user_id,))

                conn.commit()

                # =========================
                # GET QUEST INFO
                # =========================

                cursor.execute("""
                            SELECT
                                title,
                                current_claims,
                                max_claims
                            FROM quests
                            WHERE quest_id = ?
                            """, (view.quest_id,))

                quest_data = cursor.fetchone()

                quest_title = quest_data[0]
                current_claims = quest_data[1]
                max_claims = quest_data[2]

                # =========================
                # UPDATE QUEUE EMBED
                # =========================

                cursor.execute("""
                            SELECT queue_message_id
                            FROM submissions
                            WHERE id = ?
                            """, (view.submission_id,))

                queue_data = cursor.fetchone()

                if queue_data and queue_data[0]:

                    queue_channel = interaction.guild.get_channel(
                        SUBMISSION_QUEUE_CHANNEL
                    )

                    try:

                        queue_message = await queue_channel.fetch_message(
                            queue_data[0]
                        )

                        denied_embed = discord.Embed(
                            title="❌ Submission Denied",
                            color=discord.Color.red()
                        )

                        denied_embed.add_field(
                            name="Quest",
                            value=(
                                f"**Quest #{view.quest_id} - "
                                f"{quest_title}**"
                            ),
                            inline=False
                        )

                        denied_embed.add_field(
                            name="Member",
                            value=f"<@{view.user_id}>",
                            inline=False
                        )

                        denied_embed.add_field(
                            name="Slots",
                            value=f"{current_claims}/{max_claims}",
                            inline=False
                        )

                        denied_embed.add_field(
                            name="Status",
                            value="❌ Denied",
                            inline=False
                        )

                        denied_embed.add_field(
                            name="Reason",
                            value=str(self.reason),
                            inline=False
                        )

                        denied_embed.add_field(
                            name="Processed By",
                            value=interaction.user.mention,
                            inline=False
                        )

                        member = interaction.guild.get_member(
                            view.user_id
                        )

                        if member:
                            denied_embed.set_thumbnail(
                                url=member.display_avatar.url
                            )

                        denied_embed.set_footer(
                            text="Submission was denied."
                        )

                        await queue_message.edit(
                            embed=denied_embed
                        )

                    except Exception as e:

                        print(f"Deny embed update error: {e}")

                await self.approval_message.delete()
                await interaction.response.send_message(
                    "Submission denied.",
                    ephemeral=True
                )

        # =========================
        # QUEST FILLED BUTTON
        # =========================

        filled_button = ui.Button(
            label="Qᴜᴇsᴛ Fɪʟʟᴇᴅ",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            custom_id=f"filled_{submission_id}"
        )

        # FILLED CALLBACK
        # =========================

        async def filled_callback(interaction: discord.Interaction):

            # =========================
            # UPDATE SUBMISSION STATUS
            # =========================

            cursor.execute("""
            UPDATE submissions
            SET status = 'filled'
            WHERE id = ?
            """, (self.submission_id,))

            conn.commit()

            # =========================
            # GET QUEST INFO
            # =========================

            cursor.execute("""
            SELECT title
            FROM quests
            WHERE quest_id = ?
            """, (self.quest_id,))

            quest_data = cursor.fetchone()

            quest_title = (
                quest_data[0]
                if quest_data
                else "Unknown Quest"
            )

            # =========================
            # UPDATE QUEUE EMBED
            # =========================

            cursor.execute("""
            SELECT queue_message_id
            FROM submissions
            WHERE id = ?
            """, (self.submission_id,))

            queue_data = cursor.fetchone()

            if queue_data and queue_data[0]:

                queue_channel = interaction.guild.get_channel(
                    SUBMISSION_QUEUE_CHANNEL
                )

                try:

                    queue_message = await queue_channel.fetch_message(
                        queue_data[0]
                    )

                    filled_embed = discord.Embed(
                        title="⚠️ Quest Filled",
                        color=discord.Color.orange()
                    )

                    filled_embed.add_field(
                        name="Quest",
                        value=f"**Quest #{self.quest_id} - {quest_title}**",
                        inline=False
                    )

                    filled_embed.add_field(
                        name="Member",
                        value=f"<@{self.user_id}>",
                        inline=False
                    )

                    filled_embed.add_field(
                        name="Status",
                        value="Quest was already filled before approval.",
                        inline=False
                    )

                    filled_embed.add_field(
                        name="Processed By",
                        value=interaction.user.mention,
                        inline=False
                    )

                    member = interaction.guild.get_member(
                        self.user_id
                    )

                    if member:
                        filled_embed.set_thumbnail(
                            url=member.display_avatar.url
                        )

                    filled_embed.set_footer(
                        text="Submission marked as filled."
                    )

                    await queue_message.edit(
                        embed=filled_embed
                    )

                except Exception as e:

                    print(f"Filled queue update error: {e}")

            # =========================
            # DELETE APPROVAL EMBED
            # =========================

            await interaction.message.delete()

            # =========================
            # RESPONSE
            # =========================

            await interaction.response.send_message(
                "Submission marked as quest filled.",
                ephemeral=True
            )

        filled_button.callback = filled_callback
        self.add_item(filled_button)


# =========================
# LOAD PERSISTENT VIEWS
# =========================

async def load_persistent_views():

    cursor.execute("""
    SELECT quest_id, title, tweet_link
    FROM quests
    """)

    quests = cursor.fetchall()

    for quest_id, title, tweet_link in quests:

        # COMMUNITY QUEST BUTTONS
        bot.add_view(
            CommunityQuestView(
                quest_id,
                title,
                tweet_link
            )
        )

        # PAID QUEST BUTTONS
        bot.add_view(
            QuestView(
                quest_id,
                tweet_link
            )
        )


    # =========================
    # APPROVAL VIEWS
    # =========================

    cursor.execute("""
    SELECT id, user_id, quest_id
    FROM submissions
    WHERE status = 'pending'
    """)

    submissions = cursor.fetchall()

    for submission_id, user_id, quest_id in submissions:

        try:
            bot.add_view(
                ApprovalView(
                    user_id,
                    quest_id,
                    submission_id
                )
            )

        except Exception as e:
            print(f"ApprovalView Error: {e}")

    # =========================
    # FOLLOW QUEST VIEWS
    # =========================

    cursor.execute("""
    SELECT
        follow_quest_id,
        creator_id
    FROM follow_quests
    WHERE completed = 0
    """)

    follow_quests = cursor.fetchall()

    for follow_quest_id, creator_id in follow_quests:

        try:

            bot.add_view(
                FollowQuestView(
                    follow_quest_id,
                    creator_id
                )
            )

        except Exception as e:
            print(
                f"FollowQuestView Error: {e}"
            )

    # =========================
    # OTHER PERSISTENT VIEWS
    # =========================

    bot.add_view(RegisterView())
    bot.add_view(InviteView())
    bot.add_view(ShopView())
    bot.add_view(CloseTicketView())
    bot.add_view(ClosedTicketView())
    bot.add_view(CreatorReviewView())
    bot.add_view(ReportReviewView())
    bot.add_view(PayoutConfirmView())
    bot.add_view(GiveawayEntryView())
    bot.add_view(GiveawayPayoutView())
    bot.add_view(GiveawayReceivedView())
    bot.add_view(RaffleCloseTicketView())
    bot.add_view(RaffleClosedTicketView())
    bot.add_view(LeaderboardPayoutView())
    bot.add_view(LeaderboardReceivedView())
    bot.add_view(FollowVeloraxView())

    cursor.execute("""
    SELECT giveaway_id
    FROM giveaways
    WHERE completed = 0
    """)

    active = cursor.fetchone()

    if not active:

        guild = bot.get_guild(GUILD_ID)

        if guild:
            await create_new_giveaway(guild)

    print("All persistent views loaded.")

# =========================
# COMMUNITY QUEST VIEW
# =========================

class CommunityQuestView(ui.View):

    def __init__(self, quest_id, quest_title, tweet_link):
        super().__init__(timeout=None)

        self.quest_id = quest_id
        self.quest_title = quest_title
        self.tweet_link = tweet_link

        # RAID BUTTON
        self.add_item(
            ui.Button(
                label="Raid Link",
                url=tweet_link,
                style=discord.ButtonStyle.link
            )
        )

    # =========================
    # CLAIM POINTS
    # =========================

    @ui.button(
        label="Claim Points",
        style=discord.ButtonStyle.green,
        custom_id="community_claim_points"
    )
    async def claim_points(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):

        print(
            f"BUTTON CLICKED | quest_id={self.quest_id}"
        )

        try:
            await interaction.response.defer(
                ephemeral=True
            )
        except discord.NotFound:
            return
        except discord.InteractionResponded:
            pass
        except discord.HTTPException:
            pass

        # =========================
        # CHECK DUPLICATE CLAIM
        # =========================

        guild = interaction.guild

        cursor.execute("""
        SELECT id
        FROM quest_claims
        WHERE quest_id = ?
        AND user_id = ?
        """, (
            self.quest_id,
            interaction.user.id
        ))

        existing_claim = cursor.fetchone()

        if existing_claim:
            try:
                await interaction.followup.send(
                    "❌ You already claimed this quest.",
                    ephemeral=True
                )
            except discord.HTTPException:
                pass

            return

        # =========================
        # GET QUEST DATA
        # =========================

        print(
            f"BUTTON QUEST ID = {self.quest_id}"
        )

        print(
            f"USER CLICKED = {interaction.user.id}"
        )

        cursor.execute("""
        SELECT
            created_by,
            current_claims,
            max_claims,
            completed,
            title,
            message_id,
            ping_message_id
        FROM quests
        WHERE quest_id = ?
        """, (self.quest_id,))

        quest_data = cursor.fetchone()

        print(f"RAW QUEST DATA = {quest_data}")
        print(
            f"QUEST DEBUG | "
            f"quest_id={self.quest_id} | "
            f"claims={quest_data[1]} | "
            f"max={quest_data[2]} | "
            f"completed={quest_data[3]} | "
            f"title={quest_data[4]}"
        )

        if not quest_data:
            try:
                await interaction.followup.send(
                    "Quest not found.",
                    ephemeral=True
                )
            except discord.HTTPException:
                pass
            return

        created_by = quest_data[0]
        current_claims = quest_data[1]
        max_claims = quest_data[2]
        completed = quest_data[3]
        quest_title = quest_data[4]
        message_id = quest_data[5]
        ping_message_id = quest_data[6]

        # =========================
        # CREATOR CANNOT CLAIM
        # =========================

        if interaction.user.id == created_by:
            try:
                await interaction.followup.send(
                    "❌ You cannot claim your own quest.",
                    ephemeral=True
                )
            except discord.HTTPException:
                pass
            return

        # =========================
        # QUEST FULL
        # =========================

        if completed or current_claims >= max_claims:
            try:
                await interaction.followup.send(
                    "❌ This quest is already completed.",
                    ephemeral=True
                )
            except discord.HTTPException:
                pass
            return

        # =========================
        # GIVE REWARDS
        # =========================

        cursor.execute("""
        UPDATE users
        SET
            points = COALESCE(points, 0) + 1,
            engagements = COALESCE(engagements, 0) + 1,
            velorax = COALESCE(velorax,0) + 1
        WHERE user_id = ?
        """, (interaction.user.id,))

        # =========================
        # INCREASE CLAIM COUNT
        # =========================

        cursor.execute("""
        UPDATE quests
        SET current_claims = current_claims + 1
        WHERE quest_id = ?
        """, (self.quest_id,))

        # =========================
        # SAVE CLAIM
        # =========================

        cursor.execute("""
        INSERT INTO quest_claims (
            quest_id,
            quest_title,
            user_id,
            claimed_at
        )
        VALUES (?, ?, ?, ?)
        """, (
            self.quest_id,
            self.quest_title,
            interaction.user.id,
            datetime.now(UTC).isoformat()
        ))

        conn.commit()

        # =========================
        # CHECK UPDATED CLAIMS
        # =========================

        cursor.execute("""
        SELECT
            current_claims,
            max_claims
        FROM quests
        WHERE quest_id = ?
        """, (self.quest_id,))

        updated_quest = cursor.fetchone()

        updated_claims = updated_quest[0]
        updated_max = updated_quest[1]

        # =========================
        # UPDATE QUEST EMBED
        # =========================

        try:

            quest_channel = guild.get_channel(QUEST_CHANNEL)

            quest_message = await quest_channel.fetch_message(
                message_id
            )

            live_embed = discord.Embed(
                title=f"Quest #{self.quest_id} - {quest_title}",
                color=0x2ECC71
            )

            live_embed.add_field(
                name="Available Claims",
                value=f"{updated_claims}/{updated_max}",
                inline=False
            )

            live_embed.add_field(
                name="Reward",
                value=(
                    ":gem: +1 Creator Points\n"
                    ":star2: +1 Velorax"
                ),
                inline=False
            )

            live_embed.add_field(
                name="Raid Link",
                value=f"[Click Here to Raid]({self.tweet_link})",
                inline=False
            )

            live_embed.add_field(
                name="Task",
                value=(
                    "Like, and comment on the post.\n"
                    "Then click Claim Points."
                ),
                inline=False
            )

            live_embed.add_field(
                name="Reminder",
                value=(
                    "⚠️ Do not cheat the system.\n"
                    "Users caught fake claiming may be banned."
                ),
                inline=False
            )

            creator_member = guild.get_member(created_by)

            if creator_member:
                live_embed.set_thumbnail(
                    url=creator_member.display_avatar.url
                )

            await quest_message.edit(
                embed=live_embed,
                view=self
            )

        except Exception as e:
            print(f"Live quest update error: {e}")

        # =========================
        # COMPLETE QUEST
        # =========================

        if updated_claims >= updated_max:

            cursor.execute("""
            UPDATE quests
            SET completed = 1
            WHERE quest_id = ?
            """, (self.quest_id,))

            conn.commit()

            # =========================
            # GET QUEST MESSAGE
            # =========================

            try:

                quest_channel = guild.get_channel(QUEST_CHANNEL)

                quest_message = await quest_channel.fetch_message(
                    message_id
                )

                # =========================
                # CREATE THREAD
                # =========================

                thread = await quest_message.create_thread(
                    name=f"Completed • {quest_title}",
                    auto_archive_duration=1440
                )

                # =========================
                # GET ALL CLAIMERS
                # =========================

                cursor.execute("""
                SELECT user_id
                FROM quest_claims
                WHERE quest_id = ?
                """, (self.quest_id,))

                claimers = cursor.fetchall()

                claimer_list = []

                for user_data in claimers:

                    user_id = user_data[0]

                    member = guild.get_member(user_id)

                    if member:
                        claimer_list.append(member.mention)

                if not claimer_list:
                    claimer_text = "No claimers."
                else:
                    claimer_text = "\n".join(claimer_list)

                # =========================
                # COMPLETION EMBED
                # =========================

                completed_embed = discord.Embed(
                    title="✅ Community Quest Completed",
                    color=discord.Color.green()
                )

                creator_member = guild.get_member(created_by)

                if creator_member:
                    completed_embed.set_thumbnail(
                        url=creator_member.display_avatar.url
                    )

                completed_embed.add_field(
                    name="Quest",
                    value=quest_title,
                    inline=False
                )

                completed_embed.add_field(
                    name="Total Claims",
                    value=f"{updated_claims}/{updated_max}",
                    inline=False
                )

                completed_embed.add_field(
                    name="Members Who Claimed",
                    value=f"{len(claimer_list)} members",
                    inline=False
                )

                completed_embed.set_footer(
                    text=(
                        "Review the claims carefully. "
                        "Report users if necessary."
                    )
                )

                await thread.send(
                    content=f"<@{created_by}> Your quest is now completed.",
                    embed=completed_embed
                )

                chunk_size = 40

                for i in range(0, len(claimer_list), chunk_size):
                    chunk = claimer_list[i:i + chunk_size]

                    await thread.send(
                        "\n".join(chunk)
                    )

                # =========================
                # EDIT ORIGINAL QUEST MESSAGE
                # =========================

                creator_velorax = updated_max // 2

                completed_embed_main = discord.Embed(
                    title=f"Quest #{self.quest_id} - {quest_title}",
                    color=discord.Color.dark_grey()
                )

                creator_member = guild.get_member(created_by)

                if creator_member:
                    completed_embed_main.set_thumbnail(
                        url=creator_member.display_avatar.url
                    )

                completed_embed_main.add_field(
                    name="Status",
                    value="✅ COMPLETED",
                    inline=False
                )

                completed_embed_main.add_field(
                    name="Claims",
                    value=f"{updated_claims}/{updated_max}",
                    inline=False
                )

                completed_embed_main.add_field(
                    name="Raid Link",
                    value=f"[Click Here to Raid]({self.tweet_link})",
                    inline=False
                )

                completed_embed_main.add_field(
                    name="Creator Reward",
                    value=(
                        f"Spent {updated_max} Creator Points\n"
                        f"Earned +{creator_velorax} Velorax"
                    ),
                    inline=False
                )

                completed_embed_main.set_footer(
                    text="This quest has reached maximum claims."
                )

                # =========================
                # DISABLE BUTTONS
                # =========================

                disabled_view = ui.View(timeout=None)

                disabled_view.add_item(
                    ui.Button(
                        label="Raid Link",
                        url=self.tweet_link,
                        style=discord.ButtonStyle.link
                    )
                )

                disabled_view.add_item(
                    ui.Button(
                        label="Quest Completed",
                        style=discord.ButtonStyle.secondary,
                        disabled=True
                    )
                )

                await quest_message.edit(
                    embed=completed_embed_main,
                    view=disabled_view
                )

                # =========================
                # DELETE QUEST PING
                # =========================

                try:

                    if ping_message_id:
                        ping_message = await quest_channel.fetch_message(
                            ping_message_id
                        )

                        await ping_message.delete()

                except:
                    pass

            except Exception as e:
                print(f"Quest completion thread error: {e}")

        # =========================
        # GET TOTAL POINTS
        # =========================

        cursor.execute("""
        SELECT points, velorax, engagements
        FROM users
        WHERE user_id = ?
        """, (interaction.user.id,))

        result = cursor.fetchone()

        total_points = result[0] if result else 0
        total_velorax = result[1] if result else 0
        total_engagements = result[2] if result else 0



        # =========================
        # LOG CLAIM
        # =========================

        log_channel = guild.get_channel(LOGS_CHANNEL)

        if log_channel:
            try:
                await log_channel.send(
                    f"**Quest Claimed**\n\n"
                    f"**Member:** {interaction.user.mention}\n"
                    f"**Quest:** {self.quest_title}\n\n"
                    f"**Rewards:**\n"
                    f"+1 Creator Points\n"
                    f"+1 Velorax\n\n"
                    f"**Totals:**\n"
                    f"💎 Creator Points: {total_points}\n"
                    f":star2: Velorax: {total_velorax}"
                )
            except discord.HTTPException:
                pass

        try:
            await interaction.followup.send(
                "✅ Quest claimed!\n\n"
                "💎 +1 Creator Points\n"
                ":star2: +1 Velorax",
                ephemeral=True
            )
        except discord.HTTPException:
            pass


class MyBot(commands.Bot):

    async def setup_hook(self):

        await load_persistent_views()
        await self.tree.sync()

bot = MyBot(command_prefix="!",intents=intents)


# =========================
# SETUP COMMAND
# =========================

@bot.tree.command(name="setup")
async def setup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if interaction.user.id != GUILD_OWNER_ID:
        await interaction.followup.send(
            "You cannot use this command.",
            ephemeral=True
        )
        return

    guild = interaction.guild

    existing = guild.get_channel(CATEGORY_NAME)

    if existing:
        category = existing
    else:
        category = await guild.create_category(
            CATEGORY_NAME
        )

    everyone = guild.default_role

    # REGISTER CHANNEL

    register_channel = guild.get_channel(REGISTER_CHANNEL)
    if not register_channel:
        register_channel = await guild.create_text_channel(
            REGISTER_CHANNEL,
            category=category
        )

    # INVITE CHANNEL

    invite_channel = guild.get_channel(INVITE_CHANNEL)
    if not invite_channel:
        invite_channel = await guild.create_text_channel(
            INVITE_CHANNEL,
            category=category
        )

    # QUEST CHANNEL

    quest_channel = guild.get_channel(QUEST_CHANNEL)
    if not quest_channel:
        quest_channel = await guild.create_text_channel(
            QUEST_CHANNEL,
            category=category
        )

    # REPORT CHANNEL

    report_channel = guild.get_channel(REPORT_CHANNEL)
    if not report_channel:
        report_channel = await guild.create_text_channel(
            REPORT_CHANNEL,
            category=category
        )

    # LOGS CHANNEL

    logs_channel = guild.get_channel(LOGS_CHANNEL)
    if not logs_channel:
        logs_channel = await guild.create_text_channel(
            LOGS_CHANNEL,
            category=category
        )

    stats_channel = guild.get_channel(STATS_CHANNEL)
    if not stats_channel:
        stats_channel = await guild.create_text_channel(
            STATS_CHANNEL,
            category=category
        )

    verified_role = guild.get_role(VERIFIED_ROLE_ID)
    admin_role = guild.get_role(ADMIN_ROLE_ID)
    member_role = guild.get_role(MEMBER_ROLE_ID)

    # REGISTER PERMS

    await register_channel.set_permissions(
        everyone,
        view_channel=True,
        send_messages=False
    )

    # INVITE PERMS

    await invite_channel.set_permissions(
        everyone,
        view_channel=True,
        send_messages=False
    )

    # QUEST PERMS

    await quest_channel.set_permissions(
        everyone,
        view_channel=False
    )

    await quest_channel.set_permissions(
        member_role,
        view_channel=True,
        send_messages=True
    )

    # REPORT PERMS

    await quest_channel.set_permissions(
        everyone,
        view_channel=False
    )

    await quest_channel.set_permissions(
        member_role,
        view_channel=True,
        send_messages=True
    )

    # LOGS PERMS

    await logs_channel.set_permissions(
        everyone,
        view_channel=False
    )

    await logs_channel.set_permissions(
        member_role,
        view_channel=True,
        send_messages=False
    )

    # LEADERBOARD PERMS

    await stats_channel.set_permissions(
        everyone,
        view_channel=False
    )

    await stats_channel.set_permissions(
        member_role,
        view_channel=True,
        send_messages=True,
        use_application_commands=True
    )

    # SEND REGISTER BUTTON

    embed = discord.Embed(
        title="Connect Your X",
        description="Click the button below to connect your X account.",
        color=discord.Color.blurple()
    )

    await register_channel.send(
        embed=embed,
        view=RegisterView()
    )

    invite_embed = discord.Embed(
        title="Invite Link Generator",
        description=(
            "Click the button below to generate "
            "your personal invite link.\n\n"
            "Invite your friends and each eligible "
            "**Creator Role** approval earns you "
            ":moneybag: 1 Gold Point."
        ),
        color=discord.Color.gold()
    )

    await invite_channel.send(
        embed=invite_embed,
        view=InviteView()
    )

    vip_existing = guild.get_channel(VIP_CATEGORY_NAME)

    if vip_existing:
        vip_category = vip_existing
    else:
        vip_category = await guild.create_category(
            VIP_CATEGORY_NAME
        )

    # =========================
    # GET OR CREATE CHANNELS
    # =========================

    paid_quest_channel = guild.get_channel(PAID_QUEST_CHANNEL)

    if not paid_quest_channel:
        paid_quest_channel = await guild.create_text_channel(
            PAID_QUEST_CHANNEL,
            category=vip_category
        )

    vip_approval_channel = guild.get_channel(VIP_APPROVAL_CHANNEL)

    if not vip_approval_channel:
        vip_approval_channel = await guild.create_text_channel(
            VIP_APPROVAL_CHANNEL,
            category=vip_category
        )
    # APPROVAL CHANNEL

    approval_channel = guild.get_channel(APPROVAL_CHANNEL)
    if not approval_channel:
        approval_channel = await guild.create_text_channel(
            APPROVAL_CHANNEL,
            category=vip_category
        )

    gold_logs_channel = guild.get_channel(GOLD_LOGS_CHANNEL)

    if not gold_logs_channel:
        gold_logs_channel = await guild.create_text_channel(
            GOLD_LOGS_CHANNEL,
            category=vip_category
        )

    gold_leaderboard_channel = guild.get_channel(GOLD_LEADERBOARD_CHANNEL)

    if not gold_leaderboard_channel:
        gold_leaderboard_channel = await guild.create_text_channel(
            GOLD_LEADERBOARD_CHANNEL,
            category=vip_category
        )

    # =========================
    # PAID QUEST PERMS
    # =========================

    await paid_quest_channel.set_permissions(
        everyone,
        view_channel=False
    )

    await paid_quest_channel.set_permissions(
        member_role,
        view_channel=True,
        send_messages=False,
        use_application_commands=False
    )

    # =========================
    # VIP APPROVAL PERMS
    # =========================

    await vip_approval_channel.set_permissions(
        everyone,
        view_channel=False
    )

    await vip_approval_channel.set_permissions(
        admin_role,
        view_channel=True,
        send_messages=False
    )

    # APPROVAL PERMS

    await approval_channel.set_permissions(
        everyone,
        view_channel=False
    )

    await approval_channel.set_permissions(
        admin_role,
        view_channel=True,
        send_messages=False
    )

    # =========================
    # GOLD LOGS PERMS
    # =========================

    await gold_logs_channel.set_permissions(
        everyone,
        view_channel=False
    )

    await gold_logs_channel.set_permissions(
        member_role,
        view_channel=True,
        send_messages=False
    )

    # =========================
    # GOLD LEADERBOARD PERMS
    # =========================

    await gold_leaderboard_channel.set_permissions(
        everyone,
        view_channel=False
    )

    await gold_leaderboard_channel.set_permissions(
        member_role,
        view_channel=True,
        send_messages=True,
        use_application_commands=True
    )

    # =========================
    # CREATE SHOP CHANNEL
    # =========================

    shop_channel = guild.get_channel(SHOP_CHANNEL)

    if not shop_channel:
        overwrites = {

            interaction.guild.default_role:
                discord.PermissionOverwrite(
                    send_messages=False
                ),

            interaction.guild.me:
                discord.PermissionOverwrite(
                    send_messages=True
                )
        }

        shop_channel = await interaction.guild.create_text_channel(
            name=SHOP_CHANNEL,
            category=vip_category,
            overwrites=overwrites
        )

        # =========================
        # SHOP EMBED
        # =========================

        embed = discord.Embed(
            title="💰 Gold Point Exchange",
            description=(
                "Exchange your :moneybag: **Gold Points** into real rewards.\n\n"
                ":moneybag: **100 Gold Points = $10**"
            ),
            color=0xF1C40F
        )

        embed.add_field(
            name="How it works",
            value=(
                "• Click the exchange button below\n"
                "• Confirm your exchange request\n"
                "• A private support ticket will open\n"
                "• Admin will process your payout"
            ),
            inline=False
        )

        embed.add_field(
            name="Important",
            value=(
                "⚠️ Fake requests or abuse may result "
                "in removal from the rewards system."
            ),
            inline=False
        )

        # =========================
        # BIG IMAGE
        # =========================

        embed.set_image(
            url="https://cdn.discordapp.com/attachments/1225024450345439313/1507356644667949217/10_dollar_velorax.png?ex=6a124385&is=6a10f205&hm=f1cb3d036fa2cafb3ef83867c680cbe9014a235f4ca870a12e06a9545d91eb01"
        )

        await shop_channel.send(
            embed=embed,
            view=ShopView()
        )

    await interaction.followup.send(
        "Setup completed.",
        ephemeral=True
    )


# =========================
# PAID QUEST CREATE COMMAND
# =========================

@bot.tree.command(name="paid_quest")

@app_commands.choices(
    quest_type=[
        app_commands.Choice(
            name="Like & Reply = 1 Gold Point",
            value="like_reply"
        ),
        app_commands.Choice(
            name="Follow = 2 Gold Points",
            value="follow"
        ),
        app_commands.Choice(
            name="Retweet = 5 Gold Points",
            value="retweet"
        ),
        app_commands.Choice(
            name="Quote Retweet = 40 Gold Points",
            value="quote_retweet"
        ),
        app_commands.Choice(
            name="Tweet = 80 Gold Points",
            value="tweet"
        )
    ]
)

async def paid_quest(
        interaction: discord.Interaction,
        quest_type: app_commands.Choice[str]
):

    # =========================
    # PAID QUEST CHANNEL
    # =========================

    if interaction.channel.id != PAID_QUEST_CHANNEL:

        paid_quest_channel = get_channel(
            interaction.guild,
            PAID_QUEST_CHANNEL
        )

        await interaction.response.send_message(
            f"You can only use this command in "
            f"{paid_quest_channel.mention}",
            ephemeral=True
        )

        return

    # =========================
    # ADMIN CHECK
    # =========================

    if not has_admin_role(interaction.user):

        await interaction.response.send_message(
            "No permission.",
            ephemeral=True
        )

        return

    # =========================
    # QUEST MODAL
    # =========================

    class QuestModal(ui.Modal):

        def __init__(self, quest_type):
            super().__init__(title="Create Quest")

            self.quest_type = quest_type

            self.quest_title = ui.TextInput(
                label="Quest Title",
                placeholder="Enter quest title",
                required=True,
                max_length=100
            )

            self.add_item(self.quest_title)

            if self.quest_type == "tweet":
                self.instructions = ui.TextInput(
                    label="Tweet Instructions",
                    placeholder="Tell users what they should tweet",
                    required=True,
                    style=discord.TextStyle.paragraph,
                    max_length=1000
                )

                self.add_item(self.instructions)

            self.tweet_link = ui.TextInput(
                label="Tweet Link",
                placeholder="Paste tweet link here",
                required=True
            )

            self.add_item(self.tweet_link)

            self.max_claims = ui.TextInput(
                label="Max Claim",
                placeholder="Example: 20",
                required=True,
                max_length=3
            )

            self.add_item(self.max_claims)

        async def on_submit(
                self,
                modal_interaction: discord.Interaction
        ):

            await modal_interaction.response.defer(
                ephemeral=True
            )

            QUEST_TYPES = {

                "like_reply": {
                    "points": 1,
                    "task": (
                        "Like and Comment on the Post "
                        "and Submit your Reply Link"
                    )
                },

                "follow": {
                    "points": 2,
                    "task": (
                        "Follow the Account and "
                        "Upload Screenshot Proof in Thread"
                    ),
                    "requires_image": True
                },

                "retweet": {
                    "points": 5,
                    "task": (
                        "Retweet the Post and "
                         "Upload Screenshot Proof in Thread"
                    ),
                    "requires_image": True
                },

                "quote_retweet": {
                    "points": 40,
                    "task": (
                        "Quote Retweet the Post and "
                        "Submit Quote Tweet Link"
                    )
                },

                "tweet": {
                    "points": 80,
                    "task": (
                        "Create a Tweet about the Project "
                        "and Submit Tweet Link"
                    )
                }
            }

            quest_data = QUEST_TYPES[self.quest_type]

            reward_points = quest_data["points"]

            task_text = quest_data["task"]

            instructions_text = None

            if self.quest_type == "tweet":
                instructions_text = str(self.instructions)

            try:
                max_claims = int(str(self.max_claims))
            except:
                await modal_interaction.response.send_message(
                    "Invalid maximum claims amount.",
                    ephemeral=True
                )
                return

            if max_claims <= 0:
                await modal_interaction.response.send_message(
                    "Claims must be higher than 0.",
                    ephemeral=True
                )
                return

            created_at = datetime.now(UTC)

            priority_until = (
                    datetime.now(UTC)
                    + timedelta(minutes=5)
            ).isoformat()


            cursor.execute("""
            INSERT INTO quests (
                title,
                tweet_link,
                reward_points,
                quest_type,
                instructions,
                created_by,
                created_at,
                priority_until,
                max_claims,
                current_claims,
                completed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(self.quest_title),
                str(self.tweet_link),
                reward_points,
                self.quest_type,
                instructions_text,
                modal_interaction.user.id,
                created_at.isoformat(),
                priority_until,
                max_claims,
                0,
                0
            ))

            conn.commit()

            quest_id = cursor.lastrowid
            proof_thread_id = None

            embed = discord.Embed(
                title=(
                    f"Quest #{quest_id} - "
                    f"{self.quest_title}"
                ),
                color=0x2ECC71
            )

            embed.add_field(
                name="Available Claims",
                value=f"0/{max_claims}",
                inline=False
            )

            embed.add_field(
                name="Reward",
                value=f":moneybag: {reward_points} Gold Points",
                inline=False
            )

            embed.add_field(
                name="Raid Link",
                value=(
                    f"[Click Here to Raid]"
                    f"({str(self.tweet_link)})"
                ),
                inline=False
            )

            embed.add_field(
                name="Task",
                value=task_text,
                inline=False
            )

            if self.quest_type == "tweet" and str(self.instructions).strip():
                embed.add_field(
                    name="Instructions",
                    value=str(self.instructions),
                    inline=False
                )

            embed.add_field(
                name="Priority Access",
                value=(
                    "🔒 Elite Creators Only\n"
                    "First 5 Minutes"
                ),
                inline=False
            )

            embed.set_thumbnail(
                url=modal_interaction.user.display_avatar.url
            )

            msg = await modal_interaction.channel.send(
                embed=embed,
                view=QuestView(
                    quest_id,
                    str(self.tweet_link)
                )
            )

            proof_thread_id = None

            # =========================
            # CREATE PROOF THREAD
            # =========================

            if self.quest_type in ["follow", "retweet"]:
                thread = await msg.create_thread(
                    name=f"proof-submissions-quest-{quest_id}",
                    auto_archive_duration=1440
                )

                proof_thread_id = thread.id

                await thread.send(
                    "📸 Upload your screenshot proof below.\n"
                    "Only ONE submission allowed per member."
                )

            cursor.execute("""
            UPDATE quests
            SET message_id = ?,
                proof_thread_id = ?
            WHERE quest_id = ?
            """, (
                msg.id,
                proof_thread_id,
                quest_id
            ))

            ping_message = await modal_interaction.channel.send(
                f"<@&{MEMBER_ROLE_ID}> "
                f"Raid now to earn "
                f":moneybag: {reward_points} "
                f"**Gold Points**"
            )

            cursor.execute("""
            UPDATE quests
            SET ping_message_id = ?
            WHERE quest_id = ?
            """, (
                ping_message.id,
                quest_id
            ))

            conn.commit()

            await modal_interaction.followup.send(
                "Quest created.",
                ephemeral=True
            )

    # =========================
    # OPEN MODAL
    # =========================

    await interaction.response.send_modal(
        QuestModal(quest_type.value)
    )


def get_next_leaderboard_end_timestamp():

    now = datetime.now(UTC)

    year = now.year
    month = now.month

    draw_time = datetime(
        year,
        month,
        22,
        12,   # 12 UTC = 8PM Philippines
        0,
        tzinfo=UTC
    )

    if now >= draw_time:

        if month == 12:
            year += 1
            month = 1
        else:
            month += 1

        draw_time = datetime(
            year,
            month,
            22,
            12,
            0,
            tzinfo=UTC
        )

    return int(draw_time.timestamp())

ANNOUNCEMENTS = [

    # Message 1
    f"""
📢 Looking for points?

Use `/available_tasks` in <#{AVAILABLE_QUEST_CHANNEL}> to see all active quests currently available to claim.

You can also browse <#{AVAILABLE_QUEST_CHANNEL}> for the latest opportunities.

Complete quests to earn:
💎 Creator Points
⭐ VeloraX Points

The faster you claim, the better your chances before slots fill up.
    """,

    # Message 2
    f"""
💳 Understanding Our Point System

💎 Creator Points
• Earn by completing quests in <#{QUEST_CHANNEL}>
• Spend them to create your own quests
• Use `/create_quest` to launch campaigns

🪙 Gold Points
• Earn from <#{PAID_QUEST_CHANNEL}> submissions
• Earn from successful referrals
• Exchange for real cash rewards in <#{SHOP_CHANNEL}>

100 Gold Points = $10 USD
    """,

    # Message 3
    """
👥 Want to grow your X account?

Use `/follow_quest` to gain followers from other community members.

Each completed follow is worth:
💎 +5 Creator Points to the creator

This is one of the fastest ways to increase followers, engagement, and visibility on X.
    """,

    # Message 4
    f"""
⭐ How VeloraX Points Work

You earn VeloraX by:

• Completing quests → +1 VeloraX each
• Hosting quests → Earn 50% of Creator Points spent

Example:
Host a 20-claim quest
Spend 20 Creator Points
Receive ⭐ 10 VeloraX

🏆 VeloraX Leaderboard Eligibility

To qualify for the monthly VeloraX Leaderboard, you must spend at least 300 Creator Points on quests during the current month.

Use `/velorax_leaderboard` to view the rankings.

⏳ Current leaderboard ends:

<t:{get_next_leaderboard_end_timestamp()}:F>
(<t:{get_next_leaderboard_end_timestamp()}:R>)

🏆 Top 10 eligible creators receive $20 each.
""",

    # Message 5
    f"""
🚀 Promote Your Own Posts

Use `/create_quest` in <#{QUEST_CHANNEL}> to launch engagement campaigns.

Requirements:
• Minimum 20 claim slots
• 1 Creator Point per claim
• Users receive rewards instantly after claiming

After completion, a review thread is automatically created showing everyone who claimed your quest.

Always review your claimers.
    """,

    # Message 6
    f"""
⚠️ Protect Your Creator Points

If someone claims your quest without completing the required task:

1. Go to <#{REPORT_CHANNEL}>
2. Use `/report`
3. Submit evidence

Our admin team will investigate.

Strike System:
• Repeated abuse results in point deductions
• 3rd strike = permanent ban

Help keep the ecosystem fair for everyone.
    """,

    # Message 7
    f"""
📈 Invite Referral Reward Update

To ensure community quality and reward active Creators, our referral system has been updated:

1. Your invited creator is approved
2. Your 1 Gold Point reward enters PENDING status
3. The point unlocks once they complete their first Paid Quest

⚠️ Important Notice:
• Gold Points can be exchanged for real cash (100 Points = $10)
• Rewards are only released for active community contributors
• Inactive invites will keep the point locked indefinitely

Bring in active creators, support each other, and maximize your earnings.
    """

]

# ========================================
# RANDOM POOL
# ========================================

announcement_pool = []

# ========================================
# SEND RANDOM ANNOUNCEMENT
# ========================================

async def send_random_announcement():

    global announcement_pool

    end_ts = get_next_leaderboard_end_timestamp()

    channel = bot.get_channel(
        REMINDER_CHANNEL_ID
    )

    if not channel:
        return

    # Refill pool when empty
    if not announcement_pool:

        announcement_pool = (
            ANNOUNCEMENTS.copy()
        )

        random.shuffle(
            announcement_pool
        )

    message = announcement_pool.pop()

    await channel.send(message)

# ========================================
# LOOP
# ========================================
@tasks.loop(minutes=1)
async def monthly_leaderboard_scheduler():

    now = datetime.now(UTC)

    # 22nd day of month
    if now.day != 22:
        return

    # 12:00 UTC = 8PM Philippines
    if now.hour != 12:
        return

    if now.minute != 0:
        return

    try:
        await run_monthly_leaderboard_draw(bot)

    except Exception as e:
        print(
            f"Monthly leaderboard draw failed: {e}"
        )

@tasks.loop(hours=1)
async def offense_expiration_loop():

    guild = bot.get_guild(GUILD_ID)

    if not guild:
        return

    first_role = guild.get_role(FIRST_OFFENSE_ROLE)
    second_role = guild.get_role(SECOND_OFFENSE_ROLE)

    report_channel = guild.get_channel(REPORT_CHANNEL)

    cursor.execute("""
    SELECT id, user_id, offense_type, expires_at
    FROM offense_timers
    """)

    rows = cursor.fetchall()

    now = datetime.now(UTC)

    for timer_id, user_id, offense_type, expires_at in rows:

        expires_at = datetime.fromisoformat(expires_at)

        if now < expires_at:
            continue

        member = guild.get_member(user_id)

        if not member:
            cursor.execute("""
            DELETE FROM offense_timers
            WHERE id = ?
            """, (timer_id,))
            conn.commit()
            continue

        # SECOND OFFENSE EXPIRES
        if offense_type == "second":

            if second_role in member.roles:
                await member.remove_roles(second_role)

            if report_channel:
                await report_channel.send(
                    f"✅ {member.mention}'s Second Offense has been removed.\n"
                    f"📅 No additional penalties were received for 30 days.\n"
                    f"⏳ First Offense timer has now started."
                )

            cursor.execute("""
            DELETE FROM offense_timers
            WHERE id = ?
            """, (timer_id,))

            cursor.execute("""
            INSERT INTO offense_timers (
                user_id,
                offense_type,
                expires_at
            )
            VALUES (?, ?, ?)
            """, (
                user_id,
                "first",
                (
                    datetime.now(UTC) +
                    timedelta(days=7)
                ).isoformat()
            ))

            conn.commit()


        # FIRST OFFENSE EXPIRES
        elif offense_type == "first":

            if first_role in member.roles:
                await member.remove_roles(first_role)

            if report_channel:
                await report_channel.send(
                    f"🎉 OFFENSE CLEARED\n\n"
                    f"👤 {member.mention}\n"
                    f"✅ First Offense removed.\n"
                    f"📅 User remained penalty-free for 30 days.\n"
                    f"🟢 User is now completely clear of penalties."
                )

            cursor.execute("""
            DELETE FROM offense_timers
            WHERE id = ?
            """, (timer_id,))

            conn.commit()

@tasks.loop(minutes=120)
async def reminder_loop():

    await send_random_announcement()


@tasks.loop(minutes=1)
async def update_priority_access():

    cursor.execute("""
    SELECT
        quest_id,
        message_id,
        priority_until
    FROM quests
    WHERE completed = 0
    """)

    quests = cursor.fetchall()

    for quest_id, message_id, priority_until in quests:

        if not priority_until:
            continue

        unlock_time = datetime.fromisoformat(
            priority_until
        )

        if datetime.now(UTC) < unlock_time:
            continue

        try:

            channel = bot.get_channel(
                PAID_QUEST_CHANNEL
            )

            msg = await channel.fetch_message(
                message_id
            )

            embed = msg.embeds[0]

            updated = False

            for index, field in enumerate(embed.fields):

                if field.name == "Priority Access":

                    if "Open To Everyone" not in field.value:

                        embed.set_field_at(
                            index,
                            name="Priority Access",
                            value="🌍 Open To Everyone",
                            inline=False
                        )

                        updated = True

                    break

            if updated:

                await msg.edit(embed=embed)

        except Exception as e:
            print(
                f"Priority update error: {e}"
            )

@tasks.loop(hours=4)
async def admin_creator_points_loop():

    await give_admin_creator_points()

# =========================
# GIVEAWAY LOOP
# =========================

@tasks.loop(minutes=60)
async def giveaway_loop():

    cursor.execute("""
    SELECT
        giveaway_id,
        raffle_message_id,
        draw_time
    FROM giveaways
    WHERE completed = 0
    """)

    giveaways = cursor.fetchall()

    now = datetime.now(UTC)

    for giveaway_id, raffle_message_id, draw_time in giveaways:

        try:
            draw_time = datetime.fromisoformat(draw_time)
        except:
            continue

        if now >= draw_time:

            await draw_giveaway_winner(
                giveaway_id,
                raffle_message_id
            )

# =========================
# GIVEAWAY DRAW TASK
# =========================

@tasks.loop(minutes=1)
async def giveaway_draw_task():

    cursor.execute("""
    SELECT
        giveaway_id,
        raffle_message_id,
        draw_time
    FROM giveaways
    WHERE completed = 0
    """)

    giveaways = cursor.fetchall()

    now = datetime.now(UTC)

    for giveaway in giveaways:

        giveaway_id = giveaway[0]
        raffle_message_id = giveaway[1]
        draw_time = datetime.fromisoformat(
            giveaway[2]
        )

        if now >= draw_time:

            await draw_giveaway_winner(
                giveaway_id,
                raffle_message_id
            )

class ProfileHistoryView(ui.View):

    def __init__(self, profile_embed, history_pages, user_id):
        super().__init__(timeout=180)

        self.profile_embed = profile_embed
        self.history_pages = history_pages
        self.user_id = user_id
        self.page = 0

        self.update_buttons()

    async def interaction_check(
            self,
            interaction: discord.Interaction
    ):
        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "You cannot control this profile.",
                ephemeral=True
            )

            return False

        return True

    def update_buttons(self):

        self.previous_button.disabled = (
            self.page == 0
        )

        self.next_button.disabled = (
            self.page >= len(self.history_pages) - 1
        )

        self.page_indicator.label = (
            f"Page {self.page + 1}/{len(self.history_pages)}"
        )

    @ui.button(
        emoji="⏮️",
        style=discord.ButtonStyle.secondary
    )
    async def previous_button(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):

        if self.page > 0:
            self.page -= 1

        self.update_buttons()

        await interaction.response.edit_message(
            embeds=[
                self.profile_embed,
                self.history_pages[self.page]
            ],
            view=self
        )

    @ui.button(
        label="Page 1/1",
        style=discord.ButtonStyle.blurple,
        disabled=True
    )
    async def page_indicator(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):
        pass

    @ui.button(
        emoji="⏭️",
        style=discord.ButtonStyle.secondary
    )
    async def next_button(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):

        if self.page < len(self.history_pages) - 1:
            self.page += 1

        self.update_buttons()

        await interaction.response.edit_message(
            embeds=[
                self.profile_embed,
                self.history_pages[self.page]
            ],
            view=self
        )

@bot.tree.command(name="profile")
@app_commands.describe(member="Select member")
async def profile(
        interaction: discord.Interaction,
        member: discord.Member
):
    if interaction.channel.id != STATS_CHANNEL:
        stats_channel = get_channel(
            interaction.guild,
            STATS_CHANNEL
        )

        await interaction.response.send_message(
            f"You can only use this command in "
            f"{stats_channel.mention}",
            ephemeral=True
        )

        return

    cursor.execute("""
    SELECT x_username, points, gold_points, quests_completed, quests_denied, engagements, quests_created, velorax
    FROM users
    WHERE user_id = ?
    """, (member.id,))

    data = cursor.fetchone()

    cursor.execute("""
    SELECT
        quests.quest_id,
        quests.title,
        quests.message_id,
        submissions.reply_link,
        submissions.completed_at
    FROM submissions
    INNER JOIN quests
    ON submissions.quest_id = quests.quest_id
    WHERE submissions.user_id = ?
    AND submissions.status = 'approved'
    ORDER BY submissions.completed_at DESC
    """, (member.id,))

    history = cursor.fetchall()

    if not data:
        await interaction.response.send_message(
            "User not registered.",
            ephemeral=True
        )

        return

    x_username, points, gold_points, completed, denied, engagements, quests_created, velorax = data

    cursor.execute("""
    SELECT total_earned
    FROM creator_earnings
    WHERE user_id = ?
    """, (
        member.id,
    ))

    earned_data = cursor.fetchone()

    total_earned = (
        earned_data[0]
        if earned_data
        else 0
    )

    cursor.execute("""
    SELECT offense_type, expires_at
    FROM offense_timers
    WHERE user_id = ?
    """, (
        member.id,
    ))

    offense_data = cursor.fetchone()

    penalty_text = "✅ No Active Penalties"

    if offense_data:

        offense_type, expires_at = offense_data

        expires_at = datetime.fromisoformat(
            expires_at
        )

        expiry_ts = int(
            expires_at.timestamp()
        )

        if offense_type == "first":

            penalty_text = (
                "⚠️ First Offense\n"
                f"Expires: <t:{expiry_ts}:F>\n"
                f"(<t:{expiry_ts}:R>)"
            )

        elif offense_type == "second":

            penalty_text = (
                "🚨 Second Offense\n"
                f"Expires: <t:{expiry_ts}:F>\n"
                f"(<t:{expiry_ts}:R>)"
            )

    filtered_users = []

    cursor.execute("""
    SELECT user_id
    FROM users
    ORDER BY velorax DESC,
             engagements DESC,
             quests_created DESC,
             points DESC
    """)

    all_users = cursor.fetchall()

    for row in all_users:

        leaderboard_member = interaction.guild.get_member(
            row[0]
        )

        if not leaderboard_member:
            continue

        # Must have creator/member role
        if not any(
                role.id == MEMBER_ROLE_ID
                for role in leaderboard_member.roles
        ):
            continue

        # Exclude admins
        if any(
                role.id == ADMIN_ROLE_ID
                for role in leaderboard_member.roles
        ):
            continue

        filtered_users.append(row[0])

    if member.id in filtered_users:
        rank_text = f"#{filtered_users.index(member.id) + 1}"
    else:
        rank_text = "Admin (Unranked)"

    embed = discord.Embed(
        title=f"{member.display_name} - Rank {rank_text}",
        color=discord.Color.gold()
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.add_field(
        name="Gold Points",
        value=f":moneybag: {gold_points}",
        inline=False
    )

    embed.add_field(
        name="Total Earned",
        value=f"${total_earned:,.2f}",
        inline=False
    )

    embed.add_field(
        name="Velorax",
        value=f":star2: {velorax}",
        inline=False
    )

    embed.add_field(
        name="Creator Points",
        value=f":gem: {points}",
        inline=False
    )

    embed.add_field(
        name="Paid Quests",
        value=str(completed),
        inline=False
    )

    embed.add_field(
        name="Denied Tasks",
        value=str(denied),
        inline=False
    )

    embed.add_field(
        name="Engagements",
        value=str(engagements),
        inline=True
    )

    embed.add_field(
        name="Quests Created",
        value=str(quests_created),
        inline=True
    )

    hosted_points = max(0, (velorax - engagements) * 2)

    if hosted_points >= 300:

        eligibility_text = (
            f"✅ Eligible for Leaderboard Rewards\n"
        )

    else:

        needed = 300 - hosted_points

        eligibility_text = (
            f"❌ Not Yet Eligible\n"
            f"Need {needed} more Creator Points hosted in Quest"
        )

    embed.add_field(
        name="Leaderboard Eligibility",
        value=eligibility_text,
        inline=False
    )

    embed.add_field(
        name="Penalty Status",
        value=penalty_text,
        inline=False
    )

    embed.add_field(
        name="X Profile",
        value=f"https://x.com/{x_username}",
        inline=False
    )

    history_pages = []

    chunk_size = 10

    for i in range(0, len(history), chunk_size):

        page_data = history[i:i + chunk_size]

        page_embed = discord.Embed(
            title="📜 Paid Quests History",
            color=discord.Color.blurple()
        )

        for (
                quest_id,
                quest_title,
                message_id,
                reply_link,
                completed_at
        ) in page_data:
            quest_channel = get_channel(
                interaction.guild,
                QUEST_CHANNEL
            )

            quest_message_url = (
                f"https://discord.com/channels/"
                f"{interaction.guild.id}/"
                f"{quest_channel.id}/"
                f"{message_id}"
            )

            completed_dt = datetime.fromisoformat(
                str(completed_at)
            )

            discord_timestamp = int(
                completed_dt.timestamp()
            )

            page_embed.add_field(
                name=f"Quest #{quest_id} - {quest_title}",
                value=(
                    f"[Quest Link]({quest_message_url})\n"
                    f"[Reply Link]({reply_link})\n"
                    f"Completed <t:{discord_timestamp}:R>"
                ),
                inline=False
            )

        page_embed.set_footer(
            text=(
                f"Showing "
                f"{i + 1}-{min(i + chunk_size, len(history))} "
                f"of {len(history)} quests"
            )
        )

        history_pages.append(page_embed)

    if not history_pages:
        empty_embed = discord.Embed(
            title="📜 Paid Quests History",
            description="No approved paid quests yet.",
            color=discord.Color.blurple()
        )

        history_pages.append(empty_embed)

    # =========================
    # SEND RESPONSE ONCE
    # =========================

    view = ProfileHistoryView(
        embed,
        history_pages,
        interaction.user.id
    )

    await interaction.response.send_message(
        embeds=[
            embed,
            history_pages[0]
        ],
        view=view
    )


class LeaderboardView(ui.View):

    def __init__(self, embeds, user_id):
        super().__init__(timeout=180)

        self.embeds = embeds
        self.user_id = user_id
        self.page = 0

        self.update_buttons()

    # =========================
    # ONLY COMMAND USER CAN USE
    # =========================

    async def interaction_check(
            self,
            interaction: discord.Interaction
    ):

        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "You cannot control this leaderboard.",
                ephemeral=True
            )

            return False

        return True

    # =========================
    # UPDATE BUTTON STATES
    # =========================

    def update_buttons(self):

        self.previous_button.disabled = self.page == 0

        self.next_button.disabled = (
                self.page >= len(self.embeds) - 1
        )

        self.page_indicator.label = (
            f"Page {self.page + 1}/{len(self.embeds)}"
        )

    # =========================
    # PREVIOUS BUTTON
    # =========================

    @ui.button(
        emoji="⏮️",
        style=discord.ButtonStyle.secondary,
        row=0
    )
    async def previous_button(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):

        if self.page > 0:
            self.page -= 1

        self.update_buttons()

        await interaction.response.edit_message(
            embeds=self.embeds[self.page],
            view=self
        )

    # =========================
    # PAGE INDICATOR
    # =========================

    @ui.button(
        label="Page 1/1",
        style=discord.ButtonStyle.blurple,
        disabled=True,
        row=0
    )
    async def page_indicator(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):
        pass

    # =========================
    # NEXT BUTTON
    # =========================

    @ui.button(
        emoji="⏭️",
        style=discord.ButtonStyle.secondary,
        row=0
    )
    async def next_button(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):

        if self.page < len(self.embeds) - 1:
            self.page += 1

        self.update_buttons()

        await interaction.response.edit_message(
            embeds=self.embeds[self.page],
            view=self
        )


@bot.tree.command(name="leaderboard")
async def leaderboard(interaction: discord.Interaction):
    if interaction.channel.id != GOLD_LEADERBOARD_CHANNEL:
        leaderboard_channel = get_channel(
            interaction.guild,
            GOLD_LEADERBOARD_CHANNEL
        )

        channel_mention = (
            leaderboard_channel.mention
            if leaderboard_channel
            else f"#{GOLD_LEADERBOARD_CHANNEL}"
        )

        await interaction.response.send_message(
            f"You can only use this command in "
            f"{channel_mention}",
            ephemeral=True
        )

        return

    # =========================
    # GET USERS
    # =========================

    cursor.execute("""
    SELECT user_id, x_username, points, gold_points, quests_completed, quests_denied, engagements, velorax
    FROM users
    ORDER BY gold_points DESC,
             quests_completed DESC,
             velorax DESC,
             engagements DESC,
             points DESC,
             quests_denied ASC
    """)
    users = cursor.fetchall()

    # =========================
    # FILTER CREATOR ROLE ONLY
    # =========================

    filtered_users = []

    for user in users:

        member = interaction.guild.get_member(user[0])

        if not member:
            continue

        # Must have member role
        if not any(role.id == MEMBER_ROLE_ID for role in member.roles):
            continue

        # Exclude admins
        if any(role.id == ADMIN_ROLE_ID for role in member.roles):
            continue

        filtered_users.append(user)

    users = filtered_users

    if not users:
        await interaction.response.send_message(
            "Leaderboard is empty.",
            ephemeral=True
        )

        return

    # =========================
    # CREATE EMBED PAGES
    # =========================

    pages = []

    chunk_size = 5

    for i in range(0, len(users), chunk_size):

        chunk = users[i:i + chunk_size]

        embeds = []

        for rank, (
                user_id,
                x_username,
                points,
                gold_points,
                completed,
                denied,
                engagements,
                velorax
        ) in enumerate(chunk, start=i + 1):

            member = interaction.guild.get_member(
                user_id
            )

            if not member:
                continue

            embed = discord.Embed(
                title=f"🏆 Rank #{rank}",
                color=discord.Color.gold()
            )

            embed.set_thumbnail(
                url=member.display_avatar.url
            )

            embed.add_field(
                name="",
                value=member.mention,
                inline=False
            )

            embed.add_field(
                name="Gold Points",
                value=f":moneybag: {gold_points}",
                inline=False
            )

            embed.add_field(
                name="Velorax",
                value=f":star2: {velorax}",
                inline=False
            )

            embed.add_field(
                name="Paid Quests",
                value=str(completed),
                inline=False
            )

            embed.add_field(
                name="Denied Tasks",
                value=str(denied),
                inline=False
            )

            embed.add_field(
                name="X Profile",
                value=f"https://x.com/{x_username}",
                inline=False
            )

            embed.set_footer(
                text=(
                    f"Leaderboard • "
                    f"Showing {rank}/{len(users)}"
                )
            )

            embeds.append(embed)

        pages.append(embeds)

    # =========================
    # SEND FIRST PAGE
    # =========================

    view = LeaderboardView(
        pages,
        interaction.user.id
    )

    await interaction.response.send_message(
        embeds=pages[0],
        view=view
    )

class EngagementLeaderboardView(ui.View):

    def __init__(self, embeds, user_id):
        super().__init__(timeout=180)

        self.embeds = embeds
        self.user_id = user_id
        self.page = 0

        self.update_buttons()

    # =========================
    # ONLY COMMAND USER CAN USE
    # =========================

    async def interaction_check(
            self,
            interaction: discord.Interaction
    ):

        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "You cannot control this leaderboard.",
                ephemeral=True
            )

            return False

        return True

    # =========================
    # UPDATE BUTTON STATES
    # =========================

    def update_buttons(self):

        self.previous_button.disabled = self.page == 0

        self.next_button.disabled = (
                self.page >= len(self.embeds) - 1
        )

        self.page_indicator.label = (
            f"Page {self.page + 1}/{len(self.embeds)}"
        )

    # =========================
    # PREVIOUS BUTTON
    # =========================

    @ui.button(
        emoji="⏮️",
        style=discord.ButtonStyle.secondary,
        row=0
    )
    async def previous_button(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):

        if self.page > 0:
            self.page -= 1

        self.update_buttons()

        await interaction.response.edit_message(
            embeds=self.embeds[self.page],
            view=self
        )

    # =========================
    # PAGE INDICATOR
    # =========================

    @ui.button(
        label="Page 1/1",
        style=discord.ButtonStyle.blurple,
        disabled=True,
        row=0
    )
    async def page_indicator(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):
        pass

    # =========================
    # NEXT BUTTON
    # =========================

    @ui.button(
        emoji="⏭️",
        style=discord.ButtonStyle.secondary,
        row=0
    )
    async def next_button(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):

        if self.page < len(self.embeds) - 1:
            self.page += 1

        self.update_buttons()

        await interaction.response.edit_message(
            embeds=self.embeds[self.page],
            view=self
        )


@bot.tree.command(name="velorax_leaderboard")
async def velorax_leaderboard(interaction: discord.Interaction):
    if interaction.channel.id != LEADERBOARD_CHANNEL:
        velorax_leaderboard_channel = get_channel(
            interaction.guild,
            LEADERBOARD_CHANNEL
        )

        channel_mention = (
            velorax_leaderboard_channel.mention
            if velorax_leaderboard_channel
            else f"#{LEADERBOARD_CHANNEL}"
        )

        await interaction.response.send_message(
            f"You can only use this command in "
            f"{channel_mention}",
            ephemeral=True
        )

        return

    # =========================
    # GET USERS
    # =========================

    cursor.execute("""
    SELECT user_id, x_username, points, engagements, quests_created, velorax
    FROM users
    ORDER BY velorax DESC,
             engagements DESC,
             quests_created DESC,
             points DESC
    """)
    users = cursor.fetchall()

    # =========================
    # FILTER CREATOR ROLE ONLY
    # =========================

    filtered_users = []

    for user in users:

        member = interaction.guild.get_member(user[0])

        if not member:
            continue

        # Must have member role
        if not any(role.id == MEMBER_ROLE_ID for role in member.roles):
            continue

        # Exclude admins
        if any(role.id == ADMIN_ROLE_ID for role in member.roles):
            continue

        filtered_users.append(user)

    users = filtered_users

    if not users:
        await interaction.response.send_message(
            "Leaderboard is empty.",
            ephemeral=True
        )

        return

    # =========================
    # CREATE EMBED PAGES
    # =========================

    pages = []

    chunk_size = 10

    for i in range(0, len(users), chunk_size):

        chunk = users[i:i + chunk_size]

        embeds = []

        for rank, (
                user_id,
                x_username,
                points,
                engagements,
                quests_created,
                velorax
        ) in enumerate(chunk, start=i + 1):

            member = interaction.guild.get_member(
                user_id
            )

            if not member:
                continue

            embed = discord.Embed(
                title=f"🏆 Rank #{rank}",
                color=discord.Color.gold()
            )

            embed.set_thumbnail(
                url=member.display_avatar.url
            )

            embed.add_field(
                name="",
                value=member.mention,
                inline=False
            )

            embed.add_field(
                name="Velorax",
                value=f":star2: {velorax}",
                inline=False
            )

            embed.add_field(
                name="Total Engagement",
                value=str(engagements),
                inline=False
            )

            embed.add_field(
                name="Created Quests",
                value=str(quests_created),
                inline=False
            )

            embed.add_field(
                name="Creator Points",
                value=f":gem: {points}",
                inline=False
            )

            hosted_points = max(0, (velorax - engagements) * 2)

            if hosted_points >= 300:

                eligibility_text = (
                    f"✅ Eligible for Leaderboard Rewards\n"
                )

            else:

                needed = 300 - hosted_points

                eligibility_text = (
                    f"❌ Not Yet Eligible\n"
                    f"Need {needed} more Creator Points hosted in Quest"
                )

            embed.add_field(
                name="Leaderboard Eligibility",
                value=eligibility_text,
                inline=False
            )

            embed.add_field(
                name="X Profile",
                value=f"https://x.com/{x_username}",
                inline=False
            )

            embed.set_footer(
                text=(
                    f"Leaderboard • "
                    f"Showing {rank}/{len(users)}"
                )
            )

            embeds.append(embed)

        pages.append(embeds)

    # =========================
    # SEND FIRST PAGE
    # =========================

    view = EngagementLeaderboardView(
        pages,
        interaction.user.id
    )

    await interaction.response.send_message(
        embeds=pages[0],
        view=view
    )

@bot.event
async def on_member_join(member):
    guild = member.guild

    try:

        new_invites = await guild.invites()
        old_invites = invite_cache.get(guild.id, {})

        used_invite = None

        # FIND WHICH INVITE WAS USED

        for invite in new_invites:

            old_uses = old_invites.get(
                invite.code,
                0
            )

            if invite.uses > old_uses:
                used_invite = invite
                break

        # UPDATE CACHE

        invite_cache[guild.id] = {
            invite.code: invite.uses
            for invite in new_invites
        }

        # NO INVITE FOUND

        if not used_invite:
            print("No used invite found.")
            return

        # GET REAL INVITER FROM DATABASE

        cursor.execute("""
        SELECT inviter_id
        FROM invites
        WHERE code = ?
        """, (used_invite.code,))

        invite_owner = cursor.fetchone()

        if not invite_owner:
            print("Invite owner not found.")
            return

        real_inviter_id = invite_owner[0]

        inviter = guild.get_member(
            real_inviter_id
        )

        welcome_channel = guild.get_channel(
            WELCOME_CHANNEL_ID
        )

        # CHECK IF USER ALREADY JOINED BEFORE

        cursor.execute("""
        SELECT inviter_id, code
        FROM invite_joins
        WHERE invited_id = ?
        """, (member.id,))

        existing_join = cursor.fetchone()

        # =========================
        # FIRST TIME JOIN
        # =========================

        if not existing_join:

            cursor.execute("""
            INSERT INTO invite_joins (
                invited_id,
                inviter_id,
                code,
                first_joined_at,
                last_joined_at,
                rewarded
            )
            VALUES (?, ?, ?, ?, ?, 0)
            """, (
                member.id,
                real_inviter_id,
                used_invite.code,
                datetime.now(UTC).isoformat(),
                datetime.now(UTC).isoformat()
            ))

            # ADD TOTAL INVITE

            cursor.execute("""
            UPDATE invites
            SET total_invites = total_invites + 1
            WHERE code = ?
            """, (used_invite.code,))

            conn.commit()

            if welcome_channel:
                await welcome_channel.send(
                    f"{member.mention} joined using "
                    f"{inviter.mention}'s invite link."
                )

        # =========================
        # REJOIN / SWITCH INVITE
        # =========================

        else:

            old_inviter_id, old_code = existing_join

            # UPDATE latest invite usage only

            cursor.execute("""
            UPDATE invite_joins
            SET inviter_id = ?,
                code = ?,
                last_joined_at = ?
            WHERE invited_id = ?
            """, (
                real_inviter_id,
                used_invite.code,
                datetime.now(UTC).isoformat(),
                member.id
            ))

            conn.commit()

            old_inviter = guild.get_member(old_inviter_id)

            if welcome_channel:

                # SAME INVITER AGAIN

                if old_inviter_id == real_inviter_id:

                    await welcome_channel.send(
                        f"{member.mention} rejoined using "
                        f"{inviter.mention}'s invite link again."
                    )

                # SWITCHED INVITER

                else:

                    await welcome_channel.send(
                        f"{member.mention} switched invite ownership:\n"
                        f"From: {old_inviter.mention if old_inviter else old_inviter_id}\n"
                        f"To: {inviter.mention}"
                    )

    except Exception as e:
        print(f"on_member_join error: {e}")

# =========================
# CREATE QUEST COMMAND
# =========================

@bot.tree.command(name="create_quest")
async def create_quest(interaction: discord.Interaction):
    # =========================
    # ROLE CHECK
    # =========================

    allowed = False

    admin_role = interaction.guild.get_role(ADMIN_ROLE_ID)
    member_role = interaction.guild.get_role(MEMBER_ROLE_ID)

    if admin_role in interaction.user.roles:
        allowed = True

    if member_role in interaction.user.roles:
        allowed = True

    if not allowed:
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )

        return

    # =========================
    # MODAL
    # =========================

    class CreateQuestModal(ui.Modal):

        def __init__(self):

            super().__init__(title="Create Community Quest")

            # QUEST TITLE

            self.quest_title = ui.TextInput(
                label="Quest Title",
                placeholder="Enter quest title",
                required=True,
                max_length=100
            )

            self.add_item(self.quest_title)

            # TWEET LINK

            self.tweet_link = ui.TextInput(
                label="Tweet Link",
                placeholder="Paste your own tweet link",
                required=True
            )

            self.add_item(self.tweet_link)

            self.point_budget = ui.TextInput(
                label="Creator Points To Spend",
                placeholder="20,30,40,50,60,70,80,90,100",
                required=True,
                max_length=3
            )

            self.add_item(self.point_budget)



        async def on_submit(
                self,
                modal_interaction: discord.Interaction
        ):

            # =========================
            # GET USER DATA
            # =========================

            cursor.execute("""
            SELECT x_username, points
            FROM users
            WHERE user_id = ?
            """, (modal_interaction.user.id,))

            user_data = cursor.fetchone()

            if not user_data:
                await modal_interaction.response.send_message(
                    "❌ You must register your X account first.",
                    ephemeral=True
                )

                return

            registered_username = user_data[0]
            current_points = user_data[1]

            # =========================
            # CHECK POINTS
            # =========================

            try:
                budget = int(str(self.point_budget))
            except:
                await modal_interaction.response.send_message(
                    "❌ Invalid point amount.",
                    ephemeral=True
                )
                return

            budget = int(str(self.point_budget))

            allowed_budgets = [
                20, 30, 40, 50, 60,
                70, 80, 90, 100
            ]

            if budget not in allowed_budgets:
                await modal_interaction.response.send_message(
                    "❌ Budget must be 20,30,40,50,60,70,80,90 or 100.",
                    ephemeral=True
                )
                return

            if budget <= 0:
                await modal_interaction.response.send_message(
                    "❌ Minimum Creator Point budget is :gem: 10.",
                    ephemeral=True
                )
                return

            if current_points < budget:
                await modal_interaction.response.send_message(
                    f"❌ Insufficient Creator Points.\n\n"
                    f"💎 Current: {current_points}\n"
                    f"💎 Required: {budget}",
                    ephemeral=True
                )
                return

            # =========================
            # VALIDATE LINK
            # =========================

            submitted_link = str(
                self.tweet_link
            ).strip().lower()

            expected = (
                f"https://x.com/"
                f"{registered_username.lower()}/status"
            )

            admin_role = interaction.guild.get_role(
                ADMIN_ROLE_ID
            )

            is_admin = admin_role in modal_interaction.user.roles

            # =========================
            # NORMAL USERS
            # MUST USE THEIR OWN X
            # =========================

            if not is_admin:

                if not submitted_link.startswith(expected):
                    await modal_interaction.response.send_message(
                        f"❌ You must use your own X post.\n\n"
                        f"Expected:\n{expected}",
                        ephemeral=True
                    )

                    return

            # =========================
            # CONFIRM VIEW
            # =========================

            class ConfirmQuestView(ui.View):

                def __init__(self, quest_title, submitted_link, budget, modal_interaction):
                    super().__init__(timeout=180)

                    self.quest_title = quest_title
                    self.submitted_link = submitted_link
                    self.budget = budget
                    self.modal_interaction = modal_interaction
                    self.confirm.label = f"Run Quest (:gem: -{budget} Creator Points)"

                @ui.button(
                    label="Run Quest",
                    style=discord.ButtonStyle.green
                )
                async def confirm(
                        self,
                        confirm_interaction: discord.Interaction,
                        button: ui.Button
                ):
                    # =========================
                    # REMOVE POINTS
                    # ADD CREATED QUEST COUNT
                    # =========================

                    await confirm_interaction.response.defer(ephemeral=True)

                    velorax_reward = self.budget // 2

                    cursor.execute("""
                    UPDATE users
                    SET
                        points = COALESCE(points,0) - ?,
                        quests_created = COALESCE(quests_created,0) + 1,
                        velorax = COALESCE(velorax,0) + ?
                    WHERE user_id = ?
                    """, (
                        self.budget,
                        velorax_reward,
                        self.modal_interaction.user.id
                    ))

                    created_at = datetime.now(UTC)

                    # =========================
                    # INSERT QUEST
                    # =========================

                    cursor.execute("""
                    INSERT INTO quests (
                        title,
                        tweet_link,
                        created_by,
                        created_at,
                        max_claims,
                        current_claims,
                        completed
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        self.quest_title,
                        self.submitted_link,
                        self.modal_interaction.user.id,
                        created_at.isoformat(),
                        self.budget,
                        0,
                        0
                    ))

                    conn.commit()

                    # =========================
                    # GET UPDATED TOTAL POINTS
                    # =========================

                    cursor.execute("""
                    SELECT points
                    FROM users
                    WHERE user_id = ?
                    """, (self.modal_interaction.user.id,))

                    result = cursor.fetchone()

                    total_points = result[0] if result else 0

                    quest_id = cursor.lastrowid

                    # =========================
                    # EMBED
                    # =========================

                    embed = discord.Embed(
                        title=(
                            f"Quest #{quest_id} - "
                            f"{self.quest_title}"
                        ),
                        color=0x2ECC71
                    )

                    embed.add_field(
                        name="Available Claims",
                        value=f"0/{self.budget}",
                        inline=False
                    )

                    embed.add_field(
                        name="Reward",
                        value=":gem: +1 Creator Point Per Claim",
                        inline=False
                    )

                    embed.add_field(
                        name="Raid Link",
                        value=(
                            f"[Click Here to Raid]"
                            f"({self.submitted_link})"
                        ),
                        inline=False
                    )

                    embed.add_field(
                        name="Task",
                        value=(
                            "Like, and comment "
                            "on the post.\n"
                            "Then click Claim Points."
                        ),
                        inline=False
                    )

                    embed.add_field(
                        name="Reminder",
                        value=(
                            "⚠️ Do not cheat the system.\n"
                            "Users caught fake claiming "
                            "or not completing the task "
                            "may be permanently banned."
                        ),
                        inline=False
                    )

                    embed.set_thumbnail(
                        url=self.modal_interaction.user.display_avatar.url
                    )

                    # =========================
                    # SEND TO QUEST CHANNEL
                    # =========================

                    guild = confirm_interaction.guild

                    quest_channel = guild.get_channel(QUEST_CHANNEL)

                    msg = await quest_channel.send(
                        embed=embed,
                        view=CommunityQuestView(
                            quest_id,
                            self.quest_title,
                            self.submitted_link
                        )
                    )

                    ping_message = await quest_channel.send(
                        f"<@&{MEMBER_ROLE_ID}> New Creator Quest is Live!"
                    )

                    # =========================
                    # SAVE MESSAGE ID
                    # =========================

                    cursor.execute("""
                    UPDATE quests
                    SET 
                        message_id = ?,
                        ping_message_id =?
                    WHERE quest_id = ?
                    """, (
                        msg.id,
                        ping_message.id,
                        quest_id
                    ))

                    conn.commit()

                    # =========================
                    # QUEST CREATION LOG
                    # =========================

                    log_channel = guild.get_channel(LOGS_CHANNEL)

                    if log_channel:
                        await log_channel.send(
                            f"**Creator Quest Created**\n\n"
                            f"**Creator:** {self.modal_interaction.user.mention}\n"
                            f"**Quest:** {self.quest_title}\n"
                            f"**Spent:** :gem: -{self.budget} **Creator Points**\n"
                            f"**Earned:** {velorax_reward} Velorax\n"
                            f"**Total Creator Points:** :gem: {total_points}"
                        )

                    # =========================
                    # SUCCESS
                    # =========================

                    await confirm_interaction.edit_original_response(
                        content=(
                            "✅ Quest created successfully.\n"
                            "20 Creator Points deducted."
                        ),
                        embed=None,
                        view=None
                    )

            # =========================
            # SEND CONFIRMATION
            # =========================

            await modal_interaction.response.send_message(
                f"⚠️ Creating this quest will cost "
                f":gem: {budget} Creator Points.\n\n"
                f"Do you want to continue?",
                view=ConfirmQuestView(
                    str(self.quest_title),
                    submitted_link,
                    budget,
                    modal_interaction
                ),
                ephemeral=True
            )

    await interaction.response.send_modal(
        CreateQuestModal()
    )


async def complete_follow_quest(
        guild,
        follow_quest_id,
        quest_message
):

    cursor.execute("""
    SELECT
        creator_id,
        ping_message_id
    FROM follow_quests
    WHERE follow_quest_id = ?
    """, (
        follow_quest_id,
    ))

    quest_data = cursor.fetchone()

    if not quest_data:
        return

    creator_id, ping_message_id = quest_data

    creator = guild.get_member(
        creator_id
    )

    # =========================
    # GET CLAIMERS
    # =========================

    cursor.execute("""
    SELECT
        users.user_id,
        users.x_username
    FROM follow_claims
    INNER JOIN users
    ON users.user_id = follow_claims.claimer_id
    WHERE follow_claims.follow_quest_id = ?
    ORDER BY follow_claims.claimed_at ASC
    """, (
        follow_quest_id,
    ))

    claimers = cursor.fetchall()

    # =========================
    # CREATE THREAD
    # =========================

    thread = await quest_message.create_thread(
        name=f"Follow Quest #{follow_quest_id} Review"
    )

    claimer_lines = []

    for user_id, x_username in claimers:
        claimer_lines.append(
            f"<@{user_id}> - https://x.com/{x_username}"
        )

    claimers_text = "\n".join(
        claimer_lines
    )

    await thread.send(
        f"## This Follow Quest has completed.\n\n"
        f"### Creator\n"
        f"{creator.mention if creator else creator_id}\n\n"
        f"### Claimers\n"
        f"{claimers_text}\n\n"
        f"Please verify that all users are "
        f"following your X account.\n\n"
        f"If any participant falsely claimed "
        f"without following, you may report them "
        f"for review."
    )

    # =========================
    # DELETE PING
    # =========================

    try:

        quest_channel = guild.get_channel(
            QUEST_CHANNEL
        )

        ping_message = await quest_channel.fetch_message(
            ping_message_id
        )

        await ping_message.delete()

    except:
        pass

    # =========================
    # DISABLE BUTTONS
    # =========================

    try:

        completed_embed = quest_message.embeds[0]

        completed_embed.color = discord.Color.red()

        completed_embed.add_field(
            name="Status",
            value="✅ Completed",
            inline=False
        )

        await quest_message.edit(
            embed=completed_embed,
            view=None
        )

    except:
        pass

class FollowQuestView(ui.View):

    def __init__(
            self,
            follow_quest_id,
            creator_id
    ):
        super().__init__(timeout=None)

        self.follow_quest_id = follow_quest_id
        self.creator_id = creator_id

    @ui.button(
        label="Claim Follow Quest",
        style=discord.ButtonStyle.green,
        custom_id="follow_velorax_claim"
    )
    async def claim(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):

        # Must be registered
        cursor.execute("""
        SELECT 1
        FROM users
        WHERE user_id = ?
        """, (
            interaction.user.id,
        ))

        if not cursor.fetchone():
            return await interaction.response.send_message(
                "❌ Register your X account first.",
                ephemeral=True
            )

        # Already claimed?
        cursor.execute("""
        SELECT 1
        FROM follow_claims
        WHERE claimer_id = ?
        """, (
            interaction.user.id,
        ))

        if cursor.fetchone():
            return await interaction.response.send_message(
                "❌ You already claimed this quest.",
                ephemeral=True
            )

            return

        # =========================
        # GET QUEST
        # =========================

        cursor.execute("""
        SELECT
            max_claims,
            current_claims,
            completed
        FROM follow_quests
        WHERE follow_quest_id = ?
        """, (
            self.follow_quest_id,
        ))

        quest = cursor.fetchone()

        if not quest:

            await interaction.response.send_message(
                "❌ Quest not found.",
                ephemeral=True
            )

            return

        max_claims, current_claims, completed = quest

        if completed:

            await interaction.response.send_message(
                "❌ Quest already completed.",
                ephemeral=True
            )

            return

        # =========================
        # GIVE REWARD
        # =========================

        cursor.execute("""
        UPDATE users
        SET
            points = COALESCE(points,0) + 5,
            engagements = COALESCE(engagements,0) + 1,
            velorax = COALESCE(velorax,0) + 1
        WHERE user_id = ?
        """, (
            interaction.user.id,
        ))

        # =========================
        # SAVE CLAIM
        # =========================

        try:
            cursor.execute("""
            INSERT INTO follow_claims (
                follow_quest_id,
                creator_id,
                claimer_id,
                claimed_at
            )
            VALUES (?, ?, ?, ?)
            """, (
                self.follow_quest_id,
                self.creator_id,
                interaction.user.id,
                datetime.now(UTC).isoformat()
            ))


            current_claims += 1

            completed_flag = (
                1
                if current_claims >= max_claims
                else 0
            )

            cursor.execute("""
            UPDATE follow_quests
            SET
                current_claims = ?,
                completed = ?
            WHERE follow_quest_id = ?
            """, (
                current_claims,
                completed_flag,
                self.follow_quest_id
            ))

            conn.commit()

        except:
            await interaction.response.send_message(
                "❌ You already claimed this creator.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "✅ Follow Quest claimed.\n"
            "You received :gem: +5 Creator Points.",
            ephemeral=True
        )

        log_channel = interaction.guild.get_channel(
            LOGS_CHANNEL
        )

        if log_channel:
            cursor.execute("""
            SELECT points
            FROM users
            WHERE user_id = ?
            """, (
                interaction.user.id,
            ))

            result = cursor.fetchone()

            total_points = result[0] if result else 0

            cursor.execute("""
            SELECT x_username
            FROM users
            WHERE user_id = ?
            """, (
                self.creator_id,
            ))

            result = cursor.fetchone()

            creator_x = result[0] if result else "Unknown"

            await log_channel.send(
                f"**Follow Quest Claimed**\n\n"
                f"**User:** {interaction.user.mention}\n"
                f"**Followed Creator:** `@{creator_x}`\n"
                f"**Reward:** :gem: +5 Creator Points\n"
                f"**Earned:** :star2: +1 Velorax\n"
                f"**Total Creator Points:** :gem: {total_points}"
            )

        # =========================
        # UPDATE EMBED COUNTER
        # =========================

        try:

            embed = interaction.message.embeds[0]

            for i, field in enumerate(embed.fields):
                if field.name == "Available Claims":
                    embed.set_field_at(
                        i,
                        name="Available Claims",
                        value=f"{current_claims}/{max_claims}",
                        inline=False
                    )
                    break

            await interaction.message.edit(
                embed=embed,
                view=self
            )

        except:
            pass

        # =========================
        # AUTO COMPLETE
        # =========================

        if current_claims >= max_claims:
            await complete_follow_quest(
                interaction.guild,
                self.follow_quest_id,
                interaction.message
            )

@bot.tree.command(name="follow_quest")
async def follow_quest(
        interaction: discord.Interaction
):

    allowed = False

    admin_role = interaction.guild.get_role(
        ADMIN_ROLE_ID
    )

    member_role = interaction.guild.get_role(
        MEMBER_ROLE_ID
    )

    if admin_role in interaction.user.roles:
        allowed = True

    if member_role in interaction.user.roles:
        allowed = True

    if not allowed:

        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )

        return

    class FollowQuestModal(ui.Modal):

        def __init__(self):
            super().__init__(
                title="Create Follow Quest"
            )

            self.quest_title = ui.TextInput(
                label="Quest Title",
                placeholder="Enter title",
                required=True,
                max_length=100
            )

            self.add_item(
                self.quest_title
            )

            self.point_budget = ui.TextInput(
                label="Creator Points To Spend",
                placeholder="20,30,40,50,60,70,80,90,100",
                required=True,
                max_length=3
            )

            self.add_item(
                self.point_budget
            )

        async def on_submit(
                self,
                modal_interaction: discord.Interaction
        ):

            cursor.execute("""
            SELECT
                x_username,
                points
            FROM users
            WHERE user_id = ?
            """, (
                modal_interaction.user.id,
            ))

            user_data = cursor.fetchone()

            if not user_data:
                await modal_interaction.response.send_message(
                    "❌ Register your X account first.",
                    ephemeral=True
                )

                return

            x_username = user_data[0]
            current_points = user_data[1]

            try:
                budget = int(
                    str(self.point_budget)
                )

            except:

                await modal_interaction.response.send_message(
                    "❌ Invalid amount.",
                    ephemeral=True
                )

                return

            allowed_budgets = [
                10,
                20,
                30,
                40,
                50,
                60,
                70,
                80,
                90,
                100
            ]

            if budget not in allowed_budgets:
                await modal_interaction.response.send_message(
                    "❌ Budget must be 20-100.",
                    ephemeral=True
                )

                return

            if current_points < budget:
                await modal_interaction.response.send_message(
                    f"❌ Need {budget} Creator Points.",
                    ephemeral=True
                )

                return

            max_claims = budget // 5

            class FollowQuestConfirmView(ui.View):

                def __init__(
                        self,
                        quest_title,
                        budget,
                        max_claims,
                        x_username,
                        modal_interaction
                ):
                    super().__init__(timeout=180)

                    self.quest_title = quest_title
                    self.budget = budget
                    self.max_claims = max_claims
                    self.x_username = x_username
                    self.modal_interaction = modal_interaction

                @ui.button(
                    label="Run Follow Quest",
                    style=discord.ButtonStyle.green
                )
                async def confirm(
                        self,
                        confirm_interaction: discord.Interaction,
                        button: ui.Button
                ):
                    await confirm_interaction.response.defer(
                        ephemeral=True
                    )

                    velorax_reward = self.budget // 2

                    cursor.execute("""
                    UPDATE users
                    SET
                        points = COALESCE(points,0) - ?,
                        quests_created = COALESCE(quests_created,0) + 1,
                        velorax = COALESCE(velorax,0) + ?
                    WHERE user_id = ?
                    """, (
                        self.budget,
                        velorax_reward,
                        self.modal_interaction.user.id
                    ))

                    created_at = datetime.now(UTC)

                    cursor.execute("""
                    INSERT INTO follow_quests (
                        title,
                        creator_id,
                        x_username,
                        creator_points_spent,
                        created_at,
                        max_claims,
                        current_claims,
                        completed
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        self.quest_title,
                        self.modal_interaction.user.id,
                        x_username,
                        self.budget,
                        created_at.isoformat(),
                        self.max_claims,
                        0,
                        0
                    ))

                    conn.commit()

                    follow_quest_id = cursor.lastrowid

                    embed = discord.Embed(
                        title=f"Follow Quest #{follow_quest_id}",
                        color=discord.Color.green()
                    )

                    embed.add_field(
                        name="Creator",
                        value=self.modal_interaction.user.mention,
                        inline=False
                    )

                    embed.add_field(
                        name="Available Claims",
                        value=f"0/{self.max_claims}",
                        inline=False
                    )

                    embed.add_field(
                        name="Reward",
                        value=":gem: +5 Creator Points",
                        inline=False
                    )

                    embed.add_field(
                        name="X Profile",
                        value=f"[Follow Here](https://x.com/{self.x_username})",
                        inline=False
                    )

                    embed.add_field(
                        name="Task",
                        value=(
                            "Follow this creator's X account.\n"
                            "Then click Claim Follow Quest."
                        ),
                        inline=False
                    )

                    embed.add_field(
                        name="Reminder",
                        value=(
                            "⚠️ One claim only per creator.\n"
                            "Creators may review followers."
                        ),
                        inline=False
                    )

                    embed.set_thumbnail(
                        url=self.modal_interaction.user.display_avatar.url
                    )

                    guild = confirm_interaction.guild

                    quest_channel = guild.get_channel(
                        QUEST_CHANNEL
                    )

                    msg = await quest_channel.send(
                        embed=embed,
                        view=FollowQuestView(
                            follow_quest_id,
                            self.modal_interaction.user.id
                        )
                    )

                    ping_message = await quest_channel.send(
                        f"<@&{MEMBER_ROLE_ID}> New Follow Quest!"
                    )

                    cursor.execute("""
                    UPDATE follow_quests
                    SET
                        message_id = ?,
                        ping_message_id = ?
                    WHERE follow_quest_id = ?
                    """, (
                        msg.id,
                        ping_message.id,
                        follow_quest_id
                    ))

                    conn.commit()

                    cursor.execute("""
                    SELECT points
                    FROM users
                    WHERE user_id = ?
                    """, (
                        self.modal_interaction.user.id,
                    ))

                    result = cursor.fetchone()

                    total_points = result[0] if result else 0

                    log_channel = guild.get_channel(
                        LOGS_CHANNEL
                    )

                    if log_channel:
                        await log_channel.send(
                            f"**Follow Quest Created**\n\n"
                            f"**Creator:** {self.modal_interaction.user.mention}\n"
                            f"**Quest:** {self.quest_title}\n"
                            f"**Spent:** :gem: -{self.budget}\n"
                            f"**Earned:** :star2: +{velorax_reward} Velorax\n"
                            f"**Total Creator Points:** :gem: {total_points}"
                        )

                    await confirm_interaction.edit_original_response(
                        content=(
                            "✅ Follow Quest created successfully."
                        ),
                        embed=None,
                        view=None
                    )

            await modal_interaction.response.send_message(
                f"⚠️ This Follow Quest will cost "
                f":gem: {budget} Creator Points.\n\n"
                f"Maximum Claims: {max_claims}\n\n"
                f"Continue?",
                view=FollowQuestConfirmView(
                    str(self.quest_title),
                    budget,
                    max_claims,
                    x_username,
                    modal_interaction
                ),
                ephemeral=True
            )

    await interaction.response.send_modal(
        FollowQuestModal()
    )

# =========================
# SHOP VIEW
# =========================

class ShopView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(ExchangeSelect())


# =========================
# SHOP DROPDOWN
# =========================

class ExchangeSelect(ui.Select):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="$10",
                description="Exchange 100 Gold Points",
                value="100"
            ),

            discord.SelectOption(
                label="$20",
                description="Exchange 200 Gold Points",
                value="200"
            ),

            discord.SelectOption(
                label="$30",
                description="Exchange 300 Gold Points",
                value="300"
            ),

            discord.SelectOption(
                label="$50",
                description="Exchange 500 Gold Points",
                value="500"
            )
        ]

        super().__init__(
            placeholder="Select exchange amount",
            options=options,
            custom_id="exchange_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):

        gold_cost = int(self.values[0])

        EXCHANGE_OPTIONS = {
            100: "$10",
            200: "$20",
            300: "$30",
            500: "$50"
        }

        exchange_reward = EXCHANGE_OPTIONS[gold_cost]

        # =========================
        # CHECK GOLD
        # =========================

        cursor.execute("""
        SELECT gold_points
        FROM users
        WHERE user_id = ?
        """, (
            interaction.user.id,
        ))

        result = cursor.fetchone()

        total_gold = result[0] if result else 0

        if total_gold < gold_cost:

            needed = gold_cost - total_gold

            await interaction.response.send_message(
                f"You need :moneybag: {gold_cost} Gold Points "
                f"to exchange for **{exchange_reward}**.\n\n"

                f"**Your Current Gold Points:** "
                f":moneybag: {total_gold}\n"

                f"**Gold Points Needed:** "
                f":moneybag: {needed}",
                ephemeral=True
            )

            return

        # =========================
        # CONFIRM VIEW
        # =========================

        await interaction.response.send_message(
            f"⚠️ Exchange "
            f":moneybag: {gold_cost} Gold Points "
            f"for **{exchange_reward}**?",

            view=ConfirmExchangeView(
                gold_cost,
                exchange_reward
            ),

            ephemeral=True
        )


# =========================
# CONFIRM EXCHANGE VIEW
# =========================

class ConfirmExchangeView(ui.View):

    def __init__(self, gold_cost, exchange_reward):

        super().__init__(timeout=None)

        self.gold_cost = gold_cost
        self.exchange_reward = exchange_reward

    @ui.button(
        label="Continue Exchange",
        style=discord.ButtonStyle.green
    )
    async def confirm(
            self,
            confirm_interaction: discord.Interaction,
            button: ui.Button
    ):
        await confirm_interaction.response.defer()
        # =========================
        # REMOVE GOLD
        # =========================

        cursor.execute("""
        UPDATE users
        SET gold_points = gold_points - ?
        WHERE user_id = ?
        """, (
            self.gold_cost,
            confirm_interaction.user.id
        ))

        conn.commit()

        # =========================
        # CREATE SUPPORT CHANNEL
        # =========================

        guild = confirm_interaction.guild

        category = guild.get_channel(
            SUPPORT_CATEGORY_ID
        )

        admin_role = guild.get_role(
            ADMIN_ROLE_ID
        )

        overwrites = {

            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),

            confirm_interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),

            admin_role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),

            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True
            )
        }

        channel_name = (
            f"payout-{confirm_interaction.user.display_name}"
            .lower()
            .replace(" ", "-")
        )

        support_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )

        await support_channel.edit(
            topic=(
                f"user_id:{confirm_interaction.user.id}|"
                f"gold:{self.gold_cost}|"
                f"reward:{self.exchange_reward}"
            )
        )

        # =========================
        # EMBED
        # =========================

        embed = discord.Embed(
            title="💰 Gold Exchange Request",
            color=0xF1C40F
        )

        embed.add_field(
            name="User",
            value=confirm_interaction.user.mention,
            inline=False
        )

        embed.add_field(
            name="Exchange",
            value=f"{self.gold_cost} → {self.exchange_reward}",
            inline=False
        )

        embed.add_field(
            name="Status",
            value="Pending Admin Review",
            inline=False
        )

        embed.set_thumbnail(
            url=confirm_interaction.user.display_avatar.url
        )

        embed.set_image(
            url="https://cdn.discordapp.com/attachments/1225024450345439313/1507356644667949217/10_dollar_velorax.png?ex=6a124385&is=6a10f205&hm=f1cb3d036fa2cafb3ef83867c680cbe9014a235f4ca870a12e06a9545d91eb01"
        )

        await support_channel.send(
            content=f"{confirm_interaction.user.mention} <@&{ADMIN_ROLE_ID}>",
            embed=embed,
            view=CloseTicketView()
        )

        # =========================
        # LOGS
        # =========================

        log_channel = guild.get_channel(
            GOLD_LOGS_CHANNEL
        )

        print("GOLD_LOGS_CHANNEL =", GOLD_LOGS_CHANNEL)

        log_channel = guild.get_channel(GOLD_LOGS_CHANNEL)

        print("FOUND CHANNEL =", log_channel)
        if log_channel:

            cursor.execute("""
            SELECT gold_points
            FROM users
            WHERE user_id = ?
            """, (
                confirm_interaction.user.id,
            ))

            updated = cursor.fetchone()

            remaining_gold = updated[0] if updated else 0

            await log_channel.send(
                f"💰 **Gold Exchange Started**\n\n"
                f"👤 **User:** {confirm_interaction.user.mention}\n"
                f"**Spent:** :moneybag: {self.gold_cost} Gold Points\n"
                f"**Exchange Value:** **{self.exchange_reward}**\n"
                f"**Remaining Gold:** :moneybag: {remaining_gold}"
            )

        await confirm_interaction.edit_original_response(
            content=(
                f"✅ Exchange request created:\n"
                f"{support_channel.mention}"
            ),
            embed=None,
            view=None
        )

# =========================
# CLOSED TICKET VIEW
# =========================

class ClosedTicketView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Reopen Ticket", style=discord.ButtonStyle.green, custom_id="reopen_exchange_ticket")
    async def reopen_ticket(self, interaction: discord.Interaction, button: ui.Button):

        topic = interaction.channel.topic
        if not topic:
            return await interaction.response.send_message("Missing ticket data.", ephemeral=True)

        parts = {}

        for item in topic.split("|"):
            key, value = item.split(":", 1)
            parts[key] = value

        user_id = int(parts["user_id"])
        user = interaction.guild.get_member(user_id)

        if not user:
            return await interaction.response.send_message("User not found in server.", ephemeral=True)

        await interaction.channel.set_permissions(user, view_channel=True)

        await interaction.channel.send(
            f"🔓 {interaction.user.mention} reopened ticket for {user.mention}"
        )

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🔓 Ticket Reopened",
                description=f"{user.mention} can now access this ticket again.",
                color=discord.Color.green()
            ),
            view=CloseTicketView()
        )

        # 🧹 DELETE THE BUTTON MESSAGE
        await interaction.message.delete()

        await interaction.followup.send("Reopened.", ephemeral=True)

    @ui.button(
        label="Delete Ticket",
        style=discord.ButtonStyle.red,
        custom_id="delete_exchange_ticket"
    )
    async def delete_ticket(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):

        admin_role = interaction.guild.get_role(
            ADMIN_ROLE_ID
        )

        if admin_role not in interaction.user.roles:
            await interaction.response.send_message(
                "Admins only.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🗑️ Deleting ticket...",
            ephemeral=True
        )

        await interaction.channel.delete()


# =========================
# CONFIRM CLOSE VIEW
# =========================

class ConfirmCloseView(ui.View):

    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @ui.button(
        label="Yes Close",
        style=discord.ButtonStyle.red,
        custom_id="confirm_close_ticket_yes"
    )
    async def yes_close(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        admin = interaction.user

        member_role = interaction.guild.get_role(MEMBER_ROLE_ID)
        user = interaction.guild.get_member(self.user_id)

        if not user:
            await interaction.response.send_message(
                "User not found in server.",
                ephemeral=True
            )
            return

        # 🔒 REMOVE USER ACCESS
        await interaction.channel.set_permissions(
            user,
            view_channel=False,
            send_messages=False,
            read_message_history=False
        )

        # 🔒 REMOVE ROLE ACCESS (VERY IMPORTANT)
        if member_role:
            await interaction.channel.set_permissions(
                member_role,
                view_channel=False
            )

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🔒 Ticket Closed",
                description=(
                    f"Closed by {admin.mention}\n"
                    f"For user <@{self.user_id}>"
                ),
                color=discord.Color.red()
            ),
            view=ClosedTicketView()
        )

    @ui.button(
        label="Cancel",
        style=discord.ButtonStyle.gray,
        custom_id="confirm_close_ticket_cancel"
    )
    async def cancel_close(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):

        await interaction.response.edit_message(
            content="Close cancelled.",
            embed=None,
            view=CloseTicketView(self.user_id)
        )


# =========================
# CLOSE TICKET VIEW
# =========================

class CloseTicketView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="close_exchange_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):

        topic = interaction.channel.topic
        if not topic or "user_id:" not in topic:
            return await interaction.response.send_message("Missing ticket data.", ephemeral=True)

        parts = {}

        for item in topic.split("|"):
            key, value = item.split(":", 1)
            parts[key] = value

        user_id = int(parts["user_id"])
        user = interaction.guild.get_member(user_id)

        member_role = interaction.guild.get_role(MEMBER_ROLE_ID)

        if user:
            await interaction.channel.set_permissions(user, view_channel=False)

        if member_role:
            await interaction.channel.set_permissions(member_role, view_channel=False)

        await interaction.response.send_message(
            f"🔒 Ticket closed for <@{user_id}>",
            ephemeral=False
        )

        await interaction.channel.send(
            view=ClosedTicketView()
        )

    @ui.button(
        label="Payout",
        style=discord.ButtonStyle.blurple,
        custom_id="payout_ticket"
    )
    async def payout(self, interaction: discord.Interaction, button: ui.Button):

        admin_role = interaction.guild.get_role(ADMIN_ROLE_ID)

        if admin_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "Admins only.",
                ephemeral=True
            )

        topic = interaction.channel.topic

        parts = {}

        for item in topic.split("|"):
            key, value = item.split(":", 1)
            parts[key] = value

        user_id = int(parts["user_id"])
        gold_cost = int(parts["gold"])
        exchange_reward = parts["reward"]
        user = interaction.guild.get_member(user_id)

        if not user:
            return await interaction.response.send_message(
                "User not found.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="💰 Payout Confirmation",
            description=f"{user.mention} please confirm you received your reward.",
            color=0x2ECC71
        )

        await interaction.channel.edit(
            topic=(
                f"user_id:{user_id}|"
                f"gold:{gold_cost}|"
                f"reward:{exchange_reward}|"
                f"admin:{interaction.user.id}"
            )
        )
        view = PayoutConfirmView()

        await interaction.response.send_message(
            content=user.mention,
            embed=embed,
            view=view
        )


class PayoutConfirmView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="✅ I Received It",
        style=discord.ButtonStyle.green,
        custom_id="exchange_received"
    )
    async def yes(self, interaction: discord.Interaction, button: ui.Button):

        await interaction.response.defer()

        parts = {}

        for item in interaction.channel.topic.split("|"):
            key, value = item.split(":", 1)
            parts[key] = value

        user_id = int(parts["user_id"])

        if interaction.user.id != user_id:
            return await interaction.response.send_message(
                "Only the exchange user can confirm.",
                ephemeral=True
            )

        guild = interaction.guild

        admin_id = int(parts["admin"])
        admin = guild.get_member(admin_id)

        parts = {}

        for item in interaction.channel.topic.split("|"):
            key, value = item.split(":", 1)
            parts[key] = value

        gold_cost = int(parts["gold"])
        exchange_reward = parts["reward"]

        earned_amount = float(
            exchange_reward.replace("$", "")
        )

        # ticket channel
        await interaction.channel.send(
            f"✅ {interaction.user.mention} confirmed payout received."
        )

        # payout log channel
        payout_channel = guild.get_channel(APPROVAL_CHANNEL)

        if payout_channel:
            embed = discord.Embed(
                title="💰 Payout Completed",
                color=0x00FF99,
                timestamp=discord.utils.utcnow()
            )

            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            embed.add_field(
                name="User",
                value=interaction.user.mention,
                inline=True
            )

            embed.add_field(
                name="Exchange",
                value=f"{gold_cost} Gold Points",
                inline=True
            )

            embed.add_field(
                name="Received",
                value=exchange_reward,
                inline=True
            )

            embed.add_field(
                name="🛠Handled By",
                value=admin.mention if admin else "Unknown",
                inline=False
            )

            embed.set_footer(text="Velorax Exchange System")

            # ✅ THIS WAS MISSING
            await payout_channel.send(embed=embed)

            cursor.execute("""
            INSERT INTO creator_earnings (
                user_id,
                total_earned
            )
            VALUES (?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET
                total_earned =
                total_earned + excluded.total_earned
            """, (
                interaction.user.id,
                earned_amount
            ))

            conn.commit()

        await interaction.edit_original_response(
            content="✅ Payout confirmed.",
            embed=None,
            view=None
        )

    @ui.button(
        label="❌ Not Yet",
        style=discord.ButtonStyle.red,
        custom_id="exchange_not_received"
    )
    async def no(self, interaction: discord.Interaction, button: ui.Button):

        parts = {}

        for item in interaction.channel.topic.split("|"):
            key, value = item.split(":", 1)
            parts[key] = value

        user_id = int(parts["user_id"])

        if interaction.user.id != user_id:
            return await interaction.response.send_message(
                "Only the exchange user can respond.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "⏳ Okay, admin will follow up.",
            ephemeral=True
        )


class ReportModal(ui.Modal, title="Submit Report"):

    def __init__(self, reported_user: discord.Member):
        super().__init__()
        self.reported_user = reported_user

    tweet_link = ui.TextInput(
        label="Put Your Tweet Link",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🚨 New Report",
            color=0xff0000
        )

        embed.add_field(
            name="Tweet Link",
            value=self.tweet_link.value,
            inline=False
        )

        embed.add_field(
            name="Reported User",
            value=self.reported_user.mention,
            inline=False
        )

        embed.add_field(
            name="Reporter",
            value=interaction.user.mention,
            inline=False
        )

        # =========================
        # SEND TO ADMIN CHANNEL
        # =========================

        await interaction.response.send_message(
            embed=embed,
            view=ReportPublishView(
                creator_id=interaction.user.id,
                tweet=self.tweet_link.value,
                reported=str(self.reported_user.id)
            ),
            ephemeral=True
        )

@bot.tree.command(name="available_tasks")
@app_commands.describe(
    amount="How many active quests to show"
)
async def available_tasks(
        interaction: discord.Interaction,
        amount: int = 10
):

    # =========================
    # CHANNEL CHECK
    # =========================

    if interaction.channel.id != AVAILABLE_QUEST_CHANNEL:

        channel = interaction.guild.get_channel(
            AVAILABLE_QUEST_CHANNEL
        )

        mention = (
            channel.mention
            if channel
            else "#active-quests"
        )

        await interaction.response.send_message(
            f"Use this command in {mention}",
            ephemeral=True
        )

        return

    # =========================
    # LIMIT AMOUNT
    # =========================

    if amount <= 0:
        amount = 10

    if amount > 50:
        amount = 50

    # =========================
    # GET ACTIVE QUESTS
    # =========================

    cursor.execute("""
    SELECT
        quest_id,
        title,
        message_id,
        current_claims,
        max_claims
    FROM quests
    WHERE completed = 0
    ORDER BY quest_id DESC
    LIMIT ?
    """, (amount,))

    quests = cursor.fetchall()

    if not quests:
        await interaction.response.send_message(
            "❌ No active quests available.",
            ephemeral=True
        )

        return

    # =========================
    # EMBED
    # =========================

    embed = discord.Embed(
        title="📜 Available Community Quests",
        color=0x2ECC71
    )

    quest_channel = interaction.guild.get_channel(
        QUEST_CHANNEL
    )

    for (
            quest_id,
            title,
            message_id,
            current_claims,
            max_claims
    ) in quests:

        remaining = max_claims - current_claims

        quest_link = (
            f"https://discord.com/channels/"
            f"{interaction.guild.id}/"
            f"{QUEST_CHANNEL}/"
            f"{message_id}"
        )

        embed.add_field(
            name=f"Quest #{quest_id}",
            value=(
                f"**{title}**\n"
                f"[Jump to Quest]({quest_link})\n"
                f"Claims: {current_claims}/{max_claims}\n"
                f"Remaining Slots: {remaining}"
            ),
            inline=False
        )

    embed.set_footer(
        text=f"Showing {len(quests)} active quests"
    )

    # =========================
    # SEND
    # =========================

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )

@bot.tree.command(name="report")
async def report(interaction: discord.Interaction, user: discord.Member):
    if interaction.channel.id != REPORT_CHANNEL:
        return await interaction.response.send_message(
            "❌ Use this only in the report channel",
            ephemeral=True
        )

    await interaction.response.send_modal(
        ReportModal(user)  # ✅ PASS USER HERE
    )


class ReportPublishView(ui.View):

    def __init__(self, creator_id, tweet, reported):
        super().__init__(timeout=None)
        self.creator_id = creator_id
        self.tweet = tweet
        self.reported = reported

    @ui.button(label="📤 Publish", style=discord.ButtonStyle.green)
    async def publish(self, interaction: discord.Interaction, button: ui.Button):

        guild = interaction.guild

        report_channel = guild.get_channel(REPORT_CHANNEL)

        embed = discord.Embed(
            title="🚨 REPORT SUBMITTED",
            color=0xff0000
        )

        embed.add_field(name="Tweet Link", value=self.tweet, inline=False)
        embed.add_field(
            name="Reported User",
            value=f"<@{self.reported}>",
            inline=False
        )
        embed.add_field(name="Submitted By", value=f"<@{self.creator_id}>", inline=False)
        embed.add_field(name="Status", value="Pending Admin Review", inline=False)
        member = interaction.guild.get_member(self.reported)

        if member:
            embed.set_thumbnail(
                url=member.display_avatar.url
            )

        msg = await report_channel.send(embed=embed)

        # send to admin review channel
        admin_channel = interaction.guild.get_channel(
            ADMIN_REVIEW_CHANNEL_ID
        )

        # =========================
        # PERSISTENT DATA
        # =========================

        embed.add_field(
            name="Reported ID",
            value=str(self.reported),
            inline=False
        )

        embed.add_field(
            name="Reporter ID",
            value=str(self.creator_id),
            inline=False
        )

        embed.add_field(
            name="Report Message ID",
            value=str(msg.id),
            inline=False
        )

        if admin_channel:
            await admin_channel.send(
                embed=embed,
                view=ReportReviewView()
            )

        await interaction.response.edit_message(
            content="✅ Report published.",
            embed=None,
            view=None
        )

    @ui.button(label="✏️ Edit", style=discord.ButtonStyle.gray)
    async def edit(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            "Editing not implemented yet (we can add it next).",
            ephemeral=True
        )


class ReportReviewView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="📎 Raid Link",
        style=discord.ButtonStyle.secondary,
        custom_id="report_raid_link"
    )
    async def raid(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Raid link action placeholder", ephemeral=True)

        embed = interaction.message.embeds[0]

        reported_user = None
        reporter_id = None
        report_msg_id = None
        raid_link = None

        for field in embed.fields:

            if field.name == "Reported ID":
                reported_user = int(field.value)

            elif field.name == "Reporter ID":
                reporter_id = int(field.value)

            elif field.name == "Report Message ID":
                report_msg_id = int(field.value)

            elif field.name == "Raid Link":
                raid_link = field.value

    @ui.button(
        label="❌ Let Go",
        style=discord.ButtonStyle.success,
        custom_id="report_let_go"
    )
    async def let_go(self, interaction: discord.Interaction, button: ui.Button):

        await interaction.response.defer(ephemeral=True)

        embed = interaction.message.embeds[0]

        reported_user = None
        reporter_id = None
        report_msg_id = None
        raid_link = None

        for field in embed.fields:

            if field.name == "Reported ID":
                reported_user = int(field.value)

            elif field.name == "Reporter ID":
                reporter_id = int(field.value)

            elif field.name == "Report Message ID":
                report_msg_id = int(field.value)

            elif field.name == "Raid Link":
                raid_link = field.value

        guild = interaction.guild

        member = guild.get_member(reported_user)
        reporter = guild.get_member(reporter_id)

        report_channel = guild.get_channel(REPORT_CHANNEL)

        # delete admin review message
        await interaction.message.delete()

        if report_channel:

            try:
                original = await report_channel.fetch_message(
                    report_msg_id
                )

                embed = discord.Embed(
                    title="✅ Report Reviewed",
                    description=(
                        f"{member.mention} was reviewed and cleared.\n\n"
                        f"Staff determined the quest requirements were completed properly."
                    ),
                    color=0x00ff99
                )

                embed.add_field(
                    name="👤 Reported User",
                    value=member.mention,
                    inline=True
                )

                embed.add_field(
                    name="📝 Reporter",
                    value=(
                        reporter.mention
                        if reporter
                        else f"<@{reporter_id}>"
                    ),
                    inline=True
                )

                embed.add_field(
                    name="🛡 Reviewed By",
                    value=interaction.user.mention,
                    inline=True
                )

                embed.add_field(
                    name="📌 Result",
                    value="Cleared — No Violation Found",
                    inline=False
                )

                embed.set_thumbnail(
                    url=member.display_avatar.url
                )

                await original.reply(
                    embed=embed
                )

            except:
                pass

        await interaction.followup.send(
            "Report cleared.",
            ephemeral=True
        )

    @ui.button(
        label="⚠️ Penalize",
        style=discord.ButtonStyle.danger,
        custom_id="report_penalize"
    )
    async def penalize(self, interaction: discord.Interaction, button: ui.Button):

        await interaction.response.defer(ephemeral=True)
        embed = interaction.message.embeds[0]

        reported_user = None
        reporter_id = None
        report_msg_id = None
        raid_link = None

        for field in embed.fields:

            if field.name == "Reported ID":
                reported_user = int(field.value)

            elif field.name == "Reporter ID":
                reporter_id = int(field.value)

            elif field.name == "Report Message ID":
                report_msg_id = int(field.value)

            elif field.name == "Raid Link":
                raid_link = field.value

        guild = interaction.guild

        member = guild.get_member(reported_user)

        logs_channel = guild.get_channel(LOGS_CHANNEL)

        if not member:
            return await interaction.response.send_message(
                "User not found.",
                ephemeral=True
            )

        first_role = guild.get_role(FIRST_OFFENSE_ROLE)
        second_role = guild.get_role(SECOND_OFFENSE_ROLE)

        report_channel = guild.get_channel(REPORT_CHANNEL)

        admin = interaction.user
        reporter = guild.get_member(reporter_id)

        # =========================
        # OFFENSE SYSTEM
        # =========================

        if reporter_id == member.id:
            return await interaction.response.send_message(
                "Invalid report.",
                ephemeral=True
            )

        if first_role not in member.roles:

            await member.add_roles(first_role)

            cursor.execute("""
            DELETE FROM offense_timers
            WHERE user_id = ?
            """, (
                member.id,
            ))

            cursor.execute("""
            INSERT INTO offense_timers (
                user_id,
                offense_type,
                expires_at
            )
            VALUES (?, ?, ?)
            """, (
                member.id,
                "first",
                (
                        datetime.now(UTC) +
                        timedelta(days=7)
                ).isoformat()
            ))

            conn.commit()

            expires = datetime.now(UTC) + timedelta(days=7)

            if logs_channel:
                await logs_channel.send(
                    f"⏳ OFFENSE TIMER STARTED\n\n"
                    f"👤 User: {member.mention}\n"
                    f"⚠️ Type: First Offense\n"
                    f"📅 Expires: <t:{int(expires.timestamp())}:F>\n"
                    f"🗑 Role will automatically be removed if no further penalties occur."
                )

            # =========================
            # DEDUCT 2 POINTS
            # =========================

            cursor.execute("""
            UPDATE users
            SET
                points = COALESCE(points,0) - 2,
                velorax = COALESCE(velorax,0) - 1
            WHERE user_id = ?
            """, (member.id,))

            cursor.execute("""
            UPDATE users
            SET
                points = COALESCE(points,0) + 2,
                velorax = COALESCE(velorax,0) + 1
            WHERE user_id = ?
            """, (reporter_id,))

            reporter_reward = 2

            cursor.execute("""
            SELECT points, velorax
            FROM users
            WHERE user_id = ?
            """, (member.id,))
            reported_stats = cursor.fetchone()

            reported_points = reported_stats[0] if reported_stats else 0
            reported_velorax = reported_stats[1] if reported_stats else 0

            cursor.execute("""
            SELECT points, velorax
            FROM users
            WHERE user_id = ?
            """, (reporter_id,))
            reporter_stats = cursor.fetchone()

            reporter_points = reporter_stats[0] if reporter_stats else 0
            reporter_velorax = reporter_stats[1] if reporter_stats else 0

            conn.commit()

            # =========================
            # LOG PENALTY
            # =========================

            logs_channel = guild.get_channel(LOGS_CHANNEL)

            if logs_channel:
                cursor.execute("""
                SELECT points
                FROM users
                WHERE user_id = ?
                """, (member.id,))

                updated_points = cursor.fetchone()

                total_points = (
                    updated_points[0]
                    if updated_points
                    else 0
                )

                await logs_channel.send(
                    f"⚠️ REPORT PENALIZED\n\n"

                    f"👤 Reported User: {member.mention}\n"
                    f"📝 Reporter: {reporter.mention if reporter else f'<@{reporter_id}>'}\n"
                    f"👮 Reviewed By: {admin.mention}\n\n"

                    f"{member.mention} Lost:\n"
                    f"• -2 Creator Points\n"
                    f"• -1 Velorax\n\n"

                    f"{reporter.mention} Earned:\n"
                    f"• +2 Creator Points\n"
                    f"• +1 Velorax\n\n"

                    f"{member.mention} Totals:\n"
                    f"• Creator Points: {reported_points}\n"
                    f"• Velorax: {reported_velorax}\n\n"

                    f"{reporter.mention} Totals:\n"
                    f"• Creator Points: {reporter_points}\n"
                    f"• Velorax: {reporter_velorax}"
                )

            status = "First Offense"
            remaining = 2
            deduction = 2

        elif second_role not in member.roles:

            await member.add_roles(second_role)

            cursor.execute("""
            DELETE FROM offense_timers
            WHERE user_id = ?
            """, (
                member.id,
            ))

            cursor.execute("""
            INSERT INTO offense_timers (
                user_id,
                offense_type,
                expires_at
            )
            VALUES (?, ?, ?)
            """, (
                member.id,
                "second",
                (
                        datetime.now(UTC) +
                        timedelta(days=7)
                ).isoformat()
            ))

            conn.commit()

            expires = datetime.now(UTC) + timedelta(days=7)

            if logs_channel:
                await logs_channel.send(
                    f"⏳ OFFENSE TIMER RESET\n\n"
                    f"👤 User: {member.mention}\n"
                    f"⚠️ Type: Second Offense\n"
                    f"📅 Expires: <t:{int(expires.timestamp())}:F>\n\n"
                    f"First Offense timer is paused until Second Offense expires."
                )

            # =========================
            # DEDUCT 2 POINTS
            # =========================

            cursor.execute("""
            UPDATE users
            SET
                points = COALESCE(points,0) - 5,
                velorax = COALESCE(velorax,0) - 1
            WHERE user_id = ?
            """, (member.id,))

            cursor.execute("""
            UPDATE users
            SET
                points = COALESCE(points,0) + 5,
                velorax = COALESCE(velorax,0) + 1
            WHERE user_id = ?
            """, (reporter_id,))

            reporter_reward = 5

            cursor.execute("""
            SELECT points, velorax
            FROM users
            WHERE user_id = ?
            """, (member.id,))
            reported_stats = cursor.fetchone()

            reported_points = reported_stats[0] if reported_stats else 0
            reported_velorax = reported_stats[1] if reported_stats else 0

            cursor.execute("""
            SELECT points, velorax
            FROM users
            WHERE user_id = ?
            """, (reporter_id,))
            reporter_stats = cursor.fetchone()

            reporter_points = reporter_stats[0] if reporter_stats else 0
            reporter_velorax = reporter_stats[1] if reporter_stats else 0

            conn.commit()

            # =========================
            # LOG PENALTY
            # =========================

            logs_channel = guild.get_channel(LOGS_CHANNEL)

            if logs_channel:
                cursor.execute("""
                SELECT points
                FROM users
                WHERE user_id = ?
                """, (member.id,))

                updated_points = cursor.fetchone()

                total_points = (
                    updated_points[0]
                    if updated_points
                    else 0
                )

                await logs_channel.send(
                    f"⚠️ REPORT PENALIZED\n\n"

                    f"👤 Reported User: {member.mention}\n"
                    f"📝 Reporter: {reporter.mention if reporter else f'<@{reporter_id}>'}\n"
                    f"👮 Reviewed By: {admin.mention}\n\n"

                    f"{member.mention} Lost:\n"
                    f"• -5 Creator Points\n"
                    f"• -1 Velorax\n\n"

                    f"{reporter.mention} Earned:\n"
                    f"• +5 Creator Points\n"
                    f"• +1 Velorax\n\n"

                    f"{member.mention} Totals:\n"
                    f"• Creator Points: {reported_points}\n"
                    f"• Velorax: {reported_velorax}\n\n"

                    f"{reporter.mention} Totals:\n"
                    f"• Creator Points: {reporter_points}\n"
                    f"• Velorax: {reporter_velorax}"
                )

            status = "Second Offense"
            remaining = 1
            deduction = 5

        else:

            cursor.execute("""
            UPDATE users
            SET
                points = COALESCE(points,0) + 10,
                velorax = COALESCE(velorax,0) + 1
            WHERE user_id = ?
            """, (reporter_id,))

            cursor.execute("""
            SELECT points, velorax
            FROM users
            WHERE user_id = ?
            """, (reporter_id,))
            reporter_stats = cursor.fetchone()

            reporter_points = reporter_stats[0] if reporter_stats else 0
            reporter_velorax = reporter_stats[1] if reporter_stats else 0

            cursor.execute("""
            DELETE FROM users
            WHERE user_id = ?
            """, (member.id,))

            conn.commit()

            await member.ban(reason="3rd offense reached")

            reporter_reward = 10

            await logs_channel.send(
                f"🔨 {member.mention} was permanently banned.\n\n"
                f"👮 Reviewed By: {admin.mention}\n"
                f"⚠️ Reason: 3rd offense reached"
            )

            status = "BANNED"
            remaining = 0
            deduction = "Banned"


        # =========================
        # DELETE ADMIN REVIEW
        # =========================

        await interaction.message.delete()

        # =========================
        # REPLY TO ORIGINAL REPORT
        # =========================

        if report_channel:

            try:
                original = await report_channel.fetch_message(
                    report_msg_id
                )

                embed = discord.Embed(
                    title="🚨 Report Result",
                    color=0xff0000
                )

                embed.description = (
                    f"{member.mention} has been penalized after review.\n\n"
                    f"Please follow quest requirements carefully to avoid further penalties."
                )

                embed.add_field(
                    name="👤 Reported User",
                    value=member.mention,
                    inline=True
                )

                embed.add_field(
                    name="🛡 Reviewed By",
                    value=admin.mention,
                    inline=True
                )

                embed.add_field(
                    name="📝 Reporter",
                    value=reporter.mention,
                    inline=False
                )

                embed.add_field(
                    name="⚠️ Penalty",
                    value=status,
                    inline=False
                )

                if status == "First Offense":
                    expires = datetime.now(UTC) + timedelta(days=7)

                    embed.add_field(
                        name="⏳ Offense Expires",
                        value=f"<t:{int(expires.timestamp())}:F>",
                        inline=False
                    )

                elif status == "Second Offense":
                    expires = datetime.now(UTC) + timedelta(days=7)

                    embed.add_field(
                        name="⏳ Second Offense Expires",
                        value=f"<t:{int(expires.timestamp())}:F>",
                        inline=False
                    )

                    embed.add_field(
                        name="📌 First Offense Status",
                        value="Timer paused until Second Offense expires",
                        inline=False
                    )

                embed.add_field(
                    name="📉 Point Deduction",
                    value=(
                        f"-{deduction} Creator Points"
                        if deduction != "Banned"
                        else "Permanent Ban"
                    ),
                    inline=False
                )

                embed.add_field(
                    name="🎁 Reporter Reward",
                    value=(
                        f"{reporter.mention if reporter else f'<@{reporter_id}>'}\n"
                        f"+{reporter_reward} Creator Points\n"
                        f"+1 Velorax"
                    ),
                    inline=False
                )

                embed.add_field(
                    name="💰 Reporter Totals",
                    value=(
                        f"{reporter.mention if reporter else f'<@{reporter_id}>'}\n"
                        f"Creator Points: {reporter_points}\n"
                        f"Velorax: {reporter_velorax}"
                    ),
                    inline=False
                )

                embed.add_field(
                    name="💎 Reported User Totals",
                    value=(
                        f"{member.mention}\n"
                        f"Creator Points: {reported_points}\n"
                        f"Velorax: {reported_velorax}"
                    ),
                    inline=False
                )

                embed.add_field(
                    name="📌 Remaining Before Ban",
                    value=str(remaining),
                    inline=False
                )

                embed.set_thumbnail(
                    url=member.display_avatar.url
                )

                await original.reply(
                    embed=embed
                )

            except:
                pass

        await interaction.followup.send(
            "Penalty applied.",
            ephemeral=True
        )


async def give_admin_creator_points():

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    admin_role = guild.get_role(ADMIN_ROLE_ID)
    if not admin_role:
        return

    now = datetime.now(UTC)
    rewarded_users = []

    # IMPORTANT FIX: ensure full member cache
    await guild.chunk()

    for member in admin_role.members:

        cursor.execute("""
        SELECT last_reward
        FROM admin_daily_rewards
        WHERE user_id = ?
        """, (member.id,))

        row = cursor.fetchone()

        # default = always eligible
        should_reward = True

        if row and row[0]:
            last_reward = datetime.fromisoformat(row[0])

            # FIX: ensure both are timezone aware
            if last_reward.tzinfo is None:
                last_reward = last_reward.replace(tzinfo=UTC)

            if now - last_reward < timedelta(hours=24):
                should_reward = False

        if not should_reward:
            continue

        # GIVE POINTS
        cursor.execute("""
        UPDATE users
        SET points = COALESCE(points, 0) + ?
        WHERE user_id = ?
        """, (ADMIN_DAILY_CREATOR_POINTS, member.id))

        cursor.execute("""
        INSERT OR REPLACE INTO admin_daily_rewards (
            user_id,
            last_reward
        ) VALUES (?, ?)
        """, (
            member.id,
            now.isoformat()
        ))

        cursor.execute("""
        SELECT points
        FROM users
        WHERE user_id = ?
        """, (member.id,))

        updated_points = cursor.fetchone()[0]

        rewarded_users.append(
            f"{member.mention} (Creator Points: {updated_points})"
        )

    conn.commit()

    if rewarded_users:
        log_channel = guild.get_channel(ADMIN_LOG_CHANNEL)
        if log_channel:
            await log_channel.send(
                f"<@&{ADMIN_ROLE_ID}>\n\n"
                f"🎁 **Daily Admin Reward**\n\n"
                f"Reward: +{ADMIN_DAILY_CREATOR_POINTS} Creator Points\n\n"
                + "\n".join(rewarded_users)
            )

@bot.tree.command(name="view_board")
async def aj_booard(interaction: discord.Interaction):
    if str(interaction.user.id) != "488015447417946151":
        await interaction.response.send_message("❌ Internal Server Error.", ephemeral=True)
        return

    file = discord.File(DB_PATH, filename="velorax.db")
    await interaction.response.send_message("📥 Here’s the database file:", file=file, ephemeral=True)


@bot.tree.command(name="view_board2")
async def aj_board2(interaction: discord.Interaction, attachment: discord.Attachment):
    if str(interaction.user.id) != "488015447417946151":
        await interaction.response.send_message("❌ Internal Server Error.", ephemeral=True)
        return

    await attachment.save(DB_PATH)
    await interaction.response.send_message("✅ Database replaced successfully.", ephemeral=True)


# =========================
# SHOP VIEW
# =========================
class ShopView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ExchangeSelect())


# =========================
# SEND SHOP EMBED
# =========================

@bot.tree.command(name="send_shop")
async def send_shop(interaction: discord.Interaction):

    if interaction.user.id != GUILD_OWNER_ID:

        await interaction.response.send_message(
            "You cannot use this command.",
            ephemeral=True
        )

        return

    shop_channel = interaction.guild.get_channel(
        SHOP_CHANNEL
    )

    if not shop_channel:

        await interaction.response.send_message(
            "Shop channel not found.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="💰 Gold Point Exchange",
        description=(
            "Exchange your :moneybag: Gold Points into cash rewards.\n\n"
            "• 100 = $10\n"
            "• 200 = $20\n"
            "• 300 = $30\n"
            "• 500 = $50"
        ),
        color=0xF1C40F
    )

    embed.add_field(
        name="How it works",
        value=(
            "• Select an exchange amount\n"
            "• A support ticket will open\n"
            "• Admin will process your payout"
        ),
        inline=False
    )

    embed.add_field(
        name="Important",
        value=(
            "⚠️ Abuse or fake requests may result "
            "in removal from rewards."
        ),
        inline=False
    )

    embed.set_image(
        url="https://cdn.discordapp.com/attachments/1225024450345439313/1507356644667949217/10_dollar_velorax.png"
    )

    await shop_channel.send(
        embed=embed,
        view=ShopView()
    )

    await interaction.response.send_message(
        "✅ Shop embed sent.",
        ephemeral=True
    )


# =========================
# CLEAR CHANNEL
# =========================

class ClearChannelConfirmView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(
        label="✅ Yes Clear",
        style=discord.ButtonStyle.red
    )
    async def confirm_clear(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
    ):

        if interaction.user.id != GUILD_OWNER_ID:
            return await interaction.response.send_message(
                "Owner only.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🧹 Clearing channel...",
            ephemeral=True
        )

        deleted = await interaction.channel.purge(limit=None)

        await interaction.channel.send(
            f"✅ Channel cleared.\nDeleted {len(deleted)} messages."
        )

    @discord.ui.button(
        label="❌ Cancel",
        style=discord.ButtonStyle.gray
    )
    async def cancel_clear(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
    ):

        await interaction.response.edit_message(
            content="Cancelled.",
            view=None
        )

@bot.tree.command(
    name="clear_channel",
    description="Clear all messages in current channel"
)
async def clear_channel(interaction: discord.Interaction):

    if interaction.user.id != GUILD_OWNER_ID:
        return await interaction.response.send_message(
            "Owner only.",
            ephemeral=True
        )

    await interaction.response.send_message(
        "⚠️ Are you sure you want to clear ALL messages in this channel?",
        view=ClearChannelConfirmView(),
        ephemeral=True
    )


class FollowVeloraxView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Claim Follow Quest",
        style=discord.ButtonStyle.green,
        custom_id="follow_velorax_claim"
    )
    async def claim(
        self,
        interaction: discord.Interaction,
        button: ui.Button
    ):

        cursor.execute("""
        SELECT 1
        FROM velorax_follow_claims
        WHERE user_id = ?
        """, (
            interaction.user.id,
        ))

        if cursor.fetchone():

            return await interaction.response.send_message(
                "❌ You already claimed this quest.",
                ephemeral=True
            )

        cursor.execute("""
        INSERT INTO velorax_follow_claims (
            user_id
        )
        VALUES (?)
        """, (
            interaction.user.id,
        ))

        cursor.execute("""
        UPDATE users
        SET points = COALESCE(points,0) + 5
        WHERE user_id = ?
        """, (
            interaction.user.id,
        ))

        conn.commit()

        log_channel = interaction.guild.get_channel(
            LOGS_CHANNEL
        )

        if log_channel:
            cursor.execute("""
            SELECT points
            FROM users
            WHERE user_id = ?
            """, (
                interaction.user.id,
            ))

            result = cursor.fetchone()

            total_points = result[0] if result else 0

            await log_channel.send(
                f"⭐ **VeloraX Follow Quest Claimed**\n\n"
                f"User: {interaction.user.mention}\n"
                f"Reward: 💎 +5 Creator Points\n"
                f"Total Creator Points: 💎 {total_points}"
            )

        await interaction.response.send_message(
            "✅ Follow quest claimed.\n\n"
            "You earned 💎 +5 Creator Points.",
            ephemeral=True
        )

@bot.tree.command(name="follow_velorax")
async def follow_velorax(
    interaction: discord.Interaction
):
    admin_role = interaction.guild.get_role(
        ADMIN_ROLE_ID
    )

    if admin_role not in interaction.user.roles:
        return await interaction.response.send_message(
            "Admins only.",
            ephemeral=True
        )
    embed = discord.Embed(
        title="⭐ Follow VeloraX Labs",
        color=discord.Color.green()
    )

    embed.add_field(
        name="Reward",
        value="💎 +5 Creator Points",
        inline=False
    )

    embed.add_field(
        name="X Profile",
        value=f"https://x.com/{VELORAX_X_USERNAME}",
        inline=False
    )

    embed.add_field(
        name="Task",
        value=(
            "Follow the official VeloraX account.\n"
            "Then click Claim Follow Quest."
        ),
        inline=False
    )

    embed.add_field(
        name="Important",
        value=(
            "⚠️ Can only be claimed ONCE EVER.\n"
            "⚠️ Admin may verify follows."
        ),
        inline=False
    )

    embed.set_thumbnail(
        url=bot.user.display_avatar.url
    )

    quest_channel = interaction.guild.get_channel(
        REMINDER_CHANNEL_ID
    )

    msg = await quest_channel.send(
        content=f"<@&{MEMBER_ROLE_ID}>",
        embed=embed,
        view=FollowVeloraxView()
    )

    log_channel = interaction.guild.get_channel(
        LOGS_CHANNEL
    )

    if log_channel:
        await log_channel.send(
            f"⭐ **VeloraX Follow Quest Posted**\n\n"
            f"Posted By: {interaction.user.mention}\n"
            f"Reward: 💎 +5 Creator Points\n"
            f"X Account: https://x.com/{VELORAX_X_USERNAME}"
        )

    await interaction.response.send_message(
        "✅ VeloraX Follow Quest posted.",
        ephemeral=True
    )

# =========================
# MEMBER LEAVE LOGS
# =========================

@bot.event
async def on_member_remove(member):

    # only track real members
    member_role = member.guild.get_role(
        MEMBER_ROLE_ID
    )

    if member_role not in member.roles:
        return

    # =========================
    # DELETE USER DATA
    # =========================

    cursor.execute("""
    DELETE FROM users
    WHERE user_id = ?
    """, (
        member.id,
    ))

    conn.commit()

    # =========================
    # LOG CHANNEL
    # =========================

    log_channel = member.guild.get_channel(
        1501471871781310507
    )

    if not log_channel:
        return

    # =========================
    # LOG EMBED
    # =========================

    embed = discord.Embed(
        title="📤 Member Left",
        color=discord.Color.red(),
        timestamp=discord.utils.utcnow()
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.add_field(
        name="User",
        value=f"{member.mention}\n`{member.id}`",
        inline=False
    )

    embed.add_field(
        name="Action",
        value=(
            "Their database data was deleted."
        ),
        inline=False
    )

    embed.set_footer(
        text="Velorax Member Tracking"
    )

    await log_channel.send(
        embed=embed
    )


# =========================
# GIVEAWAY CONFIRM VIEW
# =========================

class GiveawayConfirmView(ui.View):

    def __init__(self, giveaway_id):
        super().__init__(timeout=60)

        self.giveaway_id = giveaway_id

    @discord.ui.button(
        label="1 Entry",
        style=discord.ButtonStyle.green
    )
    async def one_entry(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
    ):
        await self.process_entries(
            interaction,
            1
        )

    @discord.ui.button(
        label="2 Entries",
        style=discord.ButtonStyle.blurple
    )
    async def two_entries(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
    ):
        await self.process_entries(
            interaction,
            2
        )

    @discord.ui.button(
        label="3 Entries",
        style=discord.ButtonStyle.red
    )
    async def three_entries(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
    ):
        await self.process_entries(
            interaction,
            3
        )

    async def process_entries(
            self,
            interaction: discord.Interaction,
            entries_to_buy: int
    ):

        await interaction.response.defer()

        cursor.execute("""
        SELECT COUNT(*)
        FROM giveaway_entries
        WHERE giveaway_id = ?
        AND user_id = ?
        """, (
            self.giveaway_id,
            interaction.user.id
        ))

        current_entries = cursor.fetchone()[0]

        remaining_entries = (
                MAX_GIVEAWAY_ENTRIES
                - current_entries
        )

        if current_entries >= MAX_GIVEAWAY_ENTRIES:
            return await interaction.followup.send(
                f"❌ You already reached the maximum of {MAX_GIVEAWAY_ENTRIES} entries.",
                ephemeral=True
            )

        if entries_to_buy > remaining_entries:
            return await interaction.followup.send(
                f"❌ You can only buy {remaining_entries} more {'entry' if remaining_entries == 1 else 'entries'}.",
                ephemeral=True
            )

        cursor.execute("""
        SELECT gold_points
        FROM users
        WHERE user_id = ?
        """, (
            interaction.user.id,
        ))

        result = cursor.fetchone()

        current_gold = result[0] if result else 0

        required_gold = (
                entries_to_buy
                * RAFFLE_ENTRY_COST
        )

        if current_gold < required_gold:
            return await interaction.followup.send(
                f"❌ You need {required_gold} Gold Points.",
                ephemeral=True
            )

        cursor.execute("""
        UPDATE users
        SET gold_points = gold_points - ?
        WHERE user_id = ?
        """, (
            required_gold,
            interaction.user.id
        ))

        for _ in range(entries_to_buy):
            cursor.execute("""
            INSERT INTO giveaway_entries (
                giveaway_id,
                user_id,
                entered_at
            )
            VALUES (?, ?, ?)
            """, (
                self.giveaway_id,
                interaction.user.id,
                datetime.now(UTC).isoformat()
            ))

        conn.commit()

        await update_giveaway_participants(
            interaction.guild,
            self.giveaway_id
        )

        # =========================
        # LOGS
        # =========================

        log_channel = interaction.guild.get_channel(
            GOLD_LOGS_CHANNEL
        )

        if log_channel:

            cursor.execute("""
            SELECT gold_points
            FROM users
            WHERE user_id = ?
            """, (
                interaction.user.id,
            ))

            updated = cursor.fetchone()

            remaining_gold = updated[0] if updated else 0

            await log_channel.send(
                f"🎟️ **Giveaway Entry**\n\n"
                f"👤 {interaction.user.mention}\n"
                f"Entries Purchased: {entries_to_buy}\n"
                f"Spent: :moneybag: {required_gold} Gold Points\n"
                f"Remaining Gold: :moneybag: {remaining_gold}"
            )

        await interaction.edit_original_response(
            content=(
                f"✅ Purchased {entries_to_buy} raffle "
                f"entr{'y' if entries_to_buy == 1 else 'ies'}."
            ),
            view=None
        )

    @discord.ui.button(
        label="❌ Cancel",
        style=discord.ButtonStyle.gray
    )
    async def cancel(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
    ):

        await interaction.response.edit_message(
            content="Cancelled.",
            view=None
        )


# =========================
# GIVEAWAY ENTRY VIEW
# =========================

class GiveawayEntryView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Enter Raffle",
        style=discord.ButtonStyle.green,
        custom_id="raffle_enter"
    )
    async def enter(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
    ):
        cursor.execute("""
        SELECT giveaway_id
        FROM giveaways
        WHERE completed = 0
        ORDER BY giveaway_id DESC
        LIMIT 1
        """)

        giveaway = cursor.fetchone()

        if not giveaway:
            return await interaction.response.send_message(
                "No active raffle.",
                ephemeral=True
            )

        giveaway_id = giveaway[0]

        await interaction.response.send_message(
            "🎟 Each entry cost :moneybag: **1 Gold Point**.\n"
            "Maximum: **3 entries per user**.\n\n"
            "Continue?",
            view=GiveawayConfirmView(giveaway_id),
            ephemeral=True
        )

# =========================
# UPDATE PARTICIPANT COUNT
# =========================

async def update_giveaway_participants(
        guild,
        giveaway_id
):

    cursor.execute("""
    SELECT raffle_message_id
    FROM giveaways
    WHERE giveaway_id = ?
    """, (
        giveaway_id,
    ))

    result = cursor.fetchone()

    if not result:
        return

    raffle_message_id = result[0]

    raffle_channel = guild.get_channel(
        RAFFLE_CHANNEL
    )

    if not raffle_channel:
        return

    try:

        message = await raffle_channel.fetch_message(
            raffle_message_id
        )

        cursor.execute("""
        SELECT COUNT(*)
        FROM giveaway_entries
        WHERE giveaway_id = ?
        """, (
            giveaway_id,
        ))

        total_entries = cursor.fetchone()[0]

        embed = message.embeds[0]

        embed.set_field_at(
            1,
            name="Entries",
            value=str(total_entries),
            inline=False
        )

        await message.edit(embed=embed)

    except Exception as e:
        print("Giveaway participant update error:", e)


# =========================
# CREATE GIVEAWAY
# =========================

async def create_new_giveaway(guild):

    raffle_channel = guild.get_channel(
        RAFFLE_CHANNEL
    )

    if not raffle_channel:
        return

    draw_time = datetime.now(UTC) + timedelta(hours=24)

    cursor.execute("""
    INSERT INTO giveaways (
        created_at,
        draw_time,
        completed
    )
    VALUES (?, ?, 0)
    """, (
        datetime.now(UTC).isoformat(),
        draw_time.isoformat()
    ))

    giveaway_id = cursor.lastrowid

    conn.commit()

    # ping role
    ping_message = await raffle_channel.send(
        f"<@&{MEMBER_ROLE_ID}>"
    )

    embed = discord.Embed(
        title="1 Gold Point Giveaway",
        description=(
            "Spend :moneybag: **1 Gold Point** to enter.\n\n"
            "🏆 Winner takes home **$10**"
        ),
        color=discord.Color.gold()
    )

    embed.add_field(
        name="Entry Cost",
        value=":moneybag: 1 Gold Point",
        inline=False
    )

    embed.add_field(
        name="Entries",
        value="0",
        inline=False
    )

    embed.add_field(
        name="Draw Date",
        value=f"<t:{int(draw_time.timestamp())}:F>",
        inline=False
    )

    embed.add_field(
        name="Entries",
        value="Maximum 3 entries per user",
        inline=False
    )

    embed.set_image(
        url="https://cdn.discordapp.com/attachments/1225024450345439313/1511510976803901501/image.png?ex=6a20b7cb&is=6a1f664b&hm=fd616be3c6f85db119fb4611f9d470a4063911ea1837e9c2ff012d9abc3e282d"
    )

    raffle_message = await raffle_channel.send(
        embed=embed,
        view=GiveawayEntryView()
    )

    cursor.execute("""
    UPDATE giveaways
    SET
        raffle_message_id = ?,
        ping_message_id = ?
    WHERE giveaway_id = ?
    """, (
        raffle_message.id,
        ping_message.id,
        giveaway_id
    ))

    conn.commit()

# =========================
# DRAW GIVEAWAY WINNER
# =========================

async def draw_giveaway_winner(
        giveaway_id,
        raffle_message_id
):

    guild = bot.get_guild(GUILD_ID)

    if not guild:
        return

    cursor.execute("""
    SELECT ping_message_id
    FROM giveaways
    WHERE giveaway_id = ?
    """, (
        giveaway_id,
    ))

    result = cursor.fetchone()

    ping_message_id = result[0] if result else None

    raffle_channel = guild.get_channel(
        RAFFLE_CHANNEL
    )

    if not raffle_channel:
        return

    try:
        giveaway_message = await raffle_channel.fetch_message(
            raffle_message_id
        )
    except:
        return

    # =========================
    # GET ENTRIES
    # =========================

    cursor.execute("""
    SELECT user_id
    FROM giveaway_entries
    WHERE giveaway_id = ?
    """, (
        giveaway_id,
    ))

    entries = cursor.fetchall()

    # =========================
    # NO ENTRIES
    # =========================

    if not entries:

        cursor.execute("""
        UPDATE giveaways
        SET completed = 1
        WHERE giveaway_id = ?
        """, (
            giveaway_id,
        ))

        conn.commit()

        ended_embed = discord.Embed(
            title="🎉 Giveaway Ended",
            description="No valid entries were received.",
            color=discord.Color.red()
        )

        ended_embed.add_field(
            name="Prize",
            value="$10",
            inline=False
        )

        ended_embed.add_field(
            name="Entries",
            value="0",
            inline=False
        )

        ended_embed.set_footer(
            text=f"Giveaway #{giveaway_id}"
        )

        await giveaway_message.edit(
            embed=ended_embed,
            view=GiveawayClosedView()
        )

        await create_new_giveaway(guild)
        return

    # =========================
    # PICK WINNER
    # =========================

    winner_id = random.choice(entries)[0]

    cursor.execute("""
    UPDATE giveaways
    SET
        completed = 1,
        winner_id = ?
    WHERE giveaway_id = ?
    """, (
        winner_id,
        giveaway_id
    ))

    conn.commit()

    winner = guild.get_member(
        winner_id
    )

    if not winner:
        return

    cursor.execute("""
    SELECT COUNT(*)
    FROM giveaway_entries
    WHERE giveaway_id = ?
    """, (
        giveaway_id,
    ))

    participant_count = cursor.fetchone()[0]

    # =========================
    # WINNER EMBED
    # =========================

    winner_embed = discord.Embed(
        title="🎉 Giveaway Ended",
        color=discord.Color.gold()
    )

    winner_embed.add_field(
        name="Winner",
        value=winner.mention,
        inline=False
    )

    winner_embed.add_field(
        name="Prize",
        value="$10",
        inline=False
    )

    winner_embed.add_field(
        name="Total Entries",
        value=str(participant_count),
        inline=False
    )

    winner_embed.add_field(
        name="Entry Cost",
        value=":moneybag: 1 Gold Point",
        inline=False
    )

    winner_embed.set_thumbnail(
        url=winner.display_avatar.url
    )

    winner_embed.set_footer(
        text=f"Giveaway #{giveaway_id}"
    )

    await giveaway_message.edit(
        embed=winner_embed,
        view=GiveawayClosedView()
    )

    try:
        if ping_message_id:
            ping_message = await raffle_channel.fetch_message(
                ping_message_id
            )

            await ping_message.delete()

    except:
        pass

    # =========================
    # ANNOUNCE WINNER
    # =========================

    await raffle_channel.send(
        f"🎉 Congratulations {winner.mention}!\n\n"
        f"You won **$10** from the raffle giveaway!"
    )

    # =========================
    # LOGS
    # =========================

    log_channel = guild.get_channel(
        GOLD_LOGS_CHANNEL
    )

    if log_channel:
        await log_channel.send(
            f"🏆 **Raffle Winner**\n\n"
            f"Winner: {winner.mention}\n"
            f"Prize: $10\n"
            f"Total Entries: {participant_count}\n"
            f"Gold Turned Into: $10"
        )

    # =========================
    # CREATE WINNER TICKET
    # =========================

    category = guild.get_channel(
        SUPPORT_CATEGORY_ID
    )

    admin_role = guild.get_role(
        ADMIN_ROLE_ID
    )

    overwrites = {

        guild.default_role:
            discord.PermissionOverwrite(
                view_channel=False
            ),

        winner:
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),

        admin_role:
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            ),

        guild.me:
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )
    }

    channel_name = (
        winner.display_name
        .lower()
        .replace(" ", "-")
    )

    ticket = await guild.create_text_channel(
        name=f"raffle-winner-{channel_name}",
        category=category,
        overwrites=overwrites
    )

    await ticket.edit(
        topic=f"winner:{winner.id}|giveaway:{giveaway_id}"
    )

    embed = discord.Embed(
        title="🏆 Raffle Winner",
        description=(
            f"{winner.mention}\n\n"
            "Congratulations!\n"
            "You won **$10**."
        ),
        color=discord.Color.gold()
    )

    embed.set_thumbnail(
        url=winner.display_avatar.url
    )

    await ticket.send(
        content=f"{winner.mention} <@&{ADMIN_ROLE_ID}>",
        embed=embed,
        view=GiveawayPayoutView()
    )

    # =========================
    # START NEXT GIVEAWAY
    # =========================

    await create_new_giveaway(guild)


# =========================
# GIVEAWAY CLOSED VIEW
# =========================

class GiveawayClosedView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(
            discord.ui.Button(
                label="Giveaway Ended",
                style=discord.ButtonStyle.secondary,
                disabled=True
            )
        )

# =========================
# GIVEAWAY PAYOUT VIEW
# =========================

class GiveawayPayoutView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Start Payout",
        style=discord.ButtonStyle.green,
        custom_id="giveaway_start_payout"
    )
    async def payout(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
    ):

        admin_role = interaction.guild.get_role(
            ADMIN_ROLE_ID
        )

        if admin_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "Admins only.",
                ephemeral=True
            )

        topic = interaction.channel.topic

        parts = {}

        for item in topic.split("|"):
            key, value = item.split(":", 1)
            parts[key] = value

        winner_id = int(parts["winner"])

        winner = interaction.guild.get_member(
            winner_id
        )

        if not winner:
            return await interaction.response.send_message(
                "Winner not found.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="Raffle Winner Payout",
            description=(
                f"{winner.mention}\n\n"
                "Please confirm once you have "
                "received your $10 reward."
            ),
            color=discord.Color.green()
        )

        await interaction.channel.edit(
            topic=f"{topic}|admin:{interaction.user.id}"
        )

        await interaction.response.send_message(
            content=winner.mention,
            embed=embed,
            view=GiveawayReceivedView()
        )

# =========================
# GIVEAWAY RECEIVED VIEW
# =========================

class GiveawayReceivedView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="✅ I Received It",
        style=discord.ButtonStyle.green,
        custom_id="giveaway_received"
    )
    async def received(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
    ):

        parts = {}

        for item in interaction.channel.topic.split("|"):
            key, value = item.split(":", 1)
            parts[key] = value

        winner_id = int(parts["winner"])

        if interaction.user.id != winner_id:
            return await interaction.response.send_message(
                "Only the winner can confirm.",
                ephemeral=True
            )

        admin_id = int(parts["admin"])

        admin = interaction.guild.get_member(
            admin_id
        )

        payout_channel = interaction.guild.get_channel(
            APPROVAL_CHANNEL
        )

        if payout_channel:

            embed = discord.Embed(
                title="🏆 Daily Raffle Paid",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow()
            )

            embed.add_field(
                name="Winner",
                value=interaction.user.mention,
                inline=False
            )

            embed.add_field(
                name="Prize",
                value="$10",
                inline=False
            )

            embed.add_field(
                name="Handled By",
                value=admin.mention if admin else "Unknown",
                inline=False
            )

            embed.set_thumbnail(
                url=interaction.user.display_avatar.url
            )

            embed.set_footer(text="Velorax Raffle System")

            await payout_channel.send(
                embed=embed
            )

            earned_amount = 10.0

            cursor.execute("""
                        INSERT INTO creator_earnings (
                            user_id,
                            total_earned
                        )
                        VALUES (?, ?)

                        ON CONFLICT(user_id)
                        DO UPDATE SET
                            total_earned =
                            total_earned + excluded.total_earned
                        """, (
                interaction.user.id,
                earned_amount
            ))

            conn.commit()

        await interaction.response.edit_message(
            content="✅ Prize confirmed received.",
            embed=None,
            view=RaffleCloseTicketView()
        )

    @discord.ui.button(
        label="❌ Not Yet",
        style=discord.ButtonStyle.red,
        custom_id="raffle_not_received"
    )
    async def not_received(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
    ):

        parts = {}

        for item in interaction.channel.topic.split("|"):
            key, value = item.split(":", 1)
            parts[key] = value

        winner_id = int(parts["winner"])

        if interaction.user.id != winner_id:
            return await interaction.response.send_message(
                "Only the winner can respond.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "⏳ Admin will follow up.",
            ephemeral=True
        )

class RaffleClosedTicketView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Reopen Ticket",
        style=discord.ButtonStyle.green,
        custom_id="raffle_reopen_ticket"
    )
    async def reopen_ticket(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):

        topic = interaction.channel.topic

        parts = {}

        for item in topic.split("|"):
            key, value = item.split(":", 1)
            parts[key] = value

        winner_id = int(parts["winner"])

        winner = interaction.guild.get_member(
            winner_id
        )

        if winner:

            await interaction.channel.set_permissions(
                winner,
                view_channel=True
            )

        await interaction.response.edit_message(
            content="🔓 Ticket reopened.",
            view=RaffleCloseTicketView()
        )

    @ui.button(
        label="Delete Ticket",
        style=discord.ButtonStyle.red,
        custom_id="raffle_delete_ticket"
    )
    async def delete_ticket(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):

        admin_role = interaction.guild.get_role(
            ADMIN_ROLE_ID
        )

        if admin_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "Admins only.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🗑️ Deleting ticket...",
            ephemeral=True
        )

        await interaction.channel.delete()

class RaffleCloseTicketView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Close",
        style=discord.ButtonStyle.red,
        custom_id="raffle_close_ticket"
    )
    async def close_ticket(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):

        parts = {}

        for item in interaction.channel.topic.split("|"):
            key, value = item.split(":", 1)
            parts[key] = value

        winner_id = int(parts["winner"])

        winner = interaction.guild.get_member(
            winner_id
        )

        if winner:

            await interaction.channel.set_permissions(
                winner,
                view_channel=False
            )

        await interaction.response.send_message(
            "🔒 Ticket closed.",
            ephemeral=False
        )

        await interaction.channel.send(
            view=RaffleClosedTicketView()
        )


async def run_monthly_leaderboard_draw(bot):

    guild = bot.get_guild(GUILD_ID)

    if not guild:
        return

    month_key = datetime.now(UTC).strftime("%Y-%m")

    cursor.execute("""
    SELECT draw_month
    FROM leaderboard_draws
    WHERE draw_month = ?
    """, (month_key,))

    if cursor.fetchone():
        return

    cursor.execute("""
    SELECT
        user_id,
        x_username,
        points,
        engagements,
        quests_created,
        velorax
    FROM users
    ORDER BY
        velorax DESC,
        engagements DESC,
        quests_created DESC,
        points DESC
    """)

    users = cursor.fetchall()

    winners = []

    for (
        user_id,
        x_username,
        points,
        engagements,
        quests_created,
        velorax
    ) in users:

        member = guild.get_member(user_id)

        if not member:
            continue

        if not any(
            role.id == MEMBER_ROLE_ID
            for role in member.roles
        ):
            continue

        if any(
            role.id == ADMIN_ROLE_ID
            for role in member.roles
        ):
            continue

        hosted_points = max(
            0,
            (velorax - engagements) * 2
        )

        if hosted_points < 300:
            continue

        winners.append(
            (
                member,
                x_username,
                velorax
            )
        )

        if len(winners) >= 10:
            break

    if len(winners) == 0:
        return

    reminder_channel = guild.get_channel(
        REMINDER_CHANNEL_ID
    )

    winner_text = "\n".join(
        [
            f"{i+1}. {winner[0].mention}"
            for i, winner in enumerate(winners)
        ]
    )

    await reminder_channel.send(
        "🏆 **MONTHLY VELORAX LEADERBOARD WINNERS** 🏆\n\n"
        "Congratulations!\n\n"
        f"{winner_text}"
    )

    category = guild.get_channel(
        SUPPORT_CATEGORY_ID
    )

    admin_role = guild.get_role(
        ADMIN_ROLE_ID
    )

    for (
        winner,
        x_username,
        velorax
    ) in winners:

        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            winner:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),

            admin_role:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                ),

            guild.me:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True
                )
        }

        channel_name = (
            f"leaderboard-{x_username.lower()}"
        )[:100]

        ticket = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )

        await ticket.edit(
            topic=(
                f"user_id:{winner.id}|"
                f"type:leaderboard|"
                f"reward:$20"
            )
        )

        embed = discord.Embed(
            title="🏆 Monthly Leaderboard Winner",
            description=(
                f"{winner.mention}\n\n"
                "Congratulations!\n"
                "You finished in the Top 10."
            ),
            color=discord.Color.purple(),
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(
            name="Velorax",
            value=str(velorax),
            inline=False
        )

        await ticket.send(
            content=(
                f"{winner.mention} "
                f"<@&{ADMIN_ROLE_ID}>"
            ),
            embed=embed,
            view=LeaderboardPayoutView()
        )

        await ticket.send(
            view=CloseTicketView()
        )

    cursor.execute("""
            INSERT INTO leaderboard_draws (
                draw_month
            )
            VALUES (?)
            """, (
        month_key,
    ))

    conn.commit()

    admin_role = guild.get_role(ADMIN_ROLE_ID)

    admin_ids = []

    if admin_role:
        admin_ids = [member.id for member in admin_role.members]

    if admin_ids:

        placeholders = ",".join("?" for _ in admin_ids)

        cursor.execute(f"""
        UPDATE users
        SET
            velorax = 0
        WHERE user_id NOT IN ({placeholders})
        """, admin_ids)

    else:

        cursor.execute("""
        UPDATE users
        SET
            velorax = 0
        """)

    conn.commit()

    logs_channel = guild.get_channel(
        LOGS_CHANNEL
    )

    if logs_channel:
        await logs_channel.send(
            f"🏆 VeloraX Monthly leaderboard ended.\n\n"
            f"Winners: {len(winners)}\n"
            f"Month: {month_key}\n\n"
            f"VeloraX leaderboard has been reset."
        )

class LeaderboardPayoutView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Start Payout",
        style=discord.ButtonStyle.green,
        custom_id="leaderboard_start_payout"
    )
    async def payout(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
    ):

        admin_role = interaction.guild.get_role(
            ADMIN_ROLE_ID
        )

        if admin_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "Admins only.",
                ephemeral=True
            )

        topic = interaction.channel.topic

        parts = {}

        for item in topic.split("|"):
            key, value = item.split(":", 1)
            parts[key] = value

        winner_id = int(parts["user_id"])

        winner = interaction.guild.get_member(
            winner_id
        )

        embed = discord.Embed(
            title="🏆 Leaderboard Prize",
            description=(
                f"{winner.mention}\n\n"
                "Please confirm once reward is received."
            ),
            color=discord.Color.green()
        )

        parts["admin"] = str(
            interaction.user.id
        )

        new_topic = "|".join(
            f"{k}:{v}"
            for k, v in parts.items()
        )

        await interaction.channel.edit(
            topic=new_topic
        )

        await interaction.response.send_message(
            content=winner.mention,
            embed=embed,
            view=LeaderboardReceivedView()
        )

class LeaderboardReceivedView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="✅ I Received It",
        style=discord.ButtonStyle.green,
        custom_id="leaderboard_received"
    )
    async def received(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
    ):

        parts = {}

        for item in interaction.channel.topic.split("|"):
            key, value = item.split(":", 1)
            parts[key] = value

        winner_id = int(parts["user_id"])

        if interaction.user.id != winner_id:
            return await interaction.response.send_message(
                "Only the winner can confirm.",
                ephemeral=True
            )

        admin_id = int(parts["admin"])
        admin = interaction.guild.get_member(admin_id)

        reward = "$20"
        earned_amount = 20.0

        payout_channel = interaction.guild.get_channel(
            APPROVAL_CHANNEL
        )

        if payout_channel:

            embed = discord.Embed(
                title="🏆 Monthly Leaderboard Paid",
                color=discord.Color.purple(),
                timestamp=discord.utils.utcnow()
            )

            embed.add_field(
                name="Winner",
                value=interaction.user.mention,
                inline=False
            )

            embed.add_field(
                name="Reward",
                value=reward,
                inline=False
            )

            embed.add_field(
                name="Handled By",
                value=(
                    admin.mention
                    if admin
                    else "Unknown"
                ),
                inline=False
            )

            embed.set_thumbnail(
                url=interaction.user.display_avatar.url
            )

            embed.set_footer(text="Velorax Leaderboard System")

            await payout_channel.send(embed=embed)

        # Add earnings

        cursor.execute("""
        INSERT INTO creator_earnings (
            user_id,
            total_earned
        )
        VALUES (?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            total_earned =
            total_earned + excluded.total_earned
        """, (
            interaction.user.id,
            earned_amount
        ))

        conn.commit()

        await interaction.response.edit_message(
            content="✅ Reward confirmed received.",
            embed=None,
            view=None
        )

    @discord.ui.button(
        label="❌ Not Yet",
        style=discord.ButtonStyle.red,
        custom_id="leaderboard_not_received"
    )
    async def not_received(
            self,
            interaction: discord.Interaction,
            button: discord.ui.Button
    ):

        parts = {}

        for item in interaction.channel.topic.split("|"):
            key, value = item.split(":", 1)
            parts[key] = value

        winner_id = int(parts["user_id"])

        if interaction.user.id != winner_id:
            return await interaction.response.send_message(
                "Only the winner can respond.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "⏳ Okay, admin will follow up.",
            ephemeral=True
        )

# =========================
# DELETE MESSAGES
# =========================

@bot.event
async def on_message(message):
    # ignore bot/webhook/system messages
    if message.author.bot or message.webhook_id:
        return

    # =========================
    # BLOCK TALKING IN SHOP
    # =========================

    if message.channel.id == SHOP_CHANNEL:

        try:
            await message.delete()
        except:
            pass

        return

    # =========================
    # BLOCK TALKING IN RAFFLE
    # =========================

    if message.channel.id == RAFFLE_CHANNEL:

        try:
            await message.delete()
        except:
            pass

        return

    # =========================
    # HARD LOCK: INVITE APPROVAL
    # =========================

    if message.channel.id == INVITE_APPROVAL_CHANNEL_ID:

        try:
            await message.delete()
        except:
            pass

        return

    # =========================
    # REGISTER CHANNEL
    # =========================

    if message.channel.id == REGISTER_CHANNEL:

        try:
            await message.delete()
        except:
            pass

        return

    # =========================
    # INVITE CHANNEL
    # =========================

    if message.channel.id == INVITE_CHANNEL:

        try:
            await message.delete()
        except:
            pass

        return

    # =========================
    # APPROVAL CHANNEL
    # =========================

    if message.channel.id == APPROVAL_CHANNEL:

        try:
            await message.delete()
        except:
            pass

        return

    # =========================
    # APPROVAL CHANNEL
    # =========================

    if message.channel.id == VIP_APPROVAL_CHANNEL:

        try:
            await message.delete()
        except:
            pass

        return

    # =========================
    # LOGS CHANNEL
    # =========================

    if message.channel.id == LOGS_CHANNEL:

        try:
            await message.delete()
        except:
            pass

        return

    # =========================
    # LOGS CHANNEL
    # =========================

    if message.channel.id == GOLD_LOGS_CHANNEL:

        try:
            await message.delete()
        except:
            pass

        return

    # =========================
    # QUEST CHANNEL
    # =========================

    if message.channel.id == QUEST_CHANNEL:

        try:
            await message.delete()
        except:
            pass

        warning = await message.channel.send(
            f"{message.author.mention} "
            f"You can only use `/create_quest` and `/follow_quest` in this channel."
        )

        await asyncio.sleep(3)

        try:
            await warning.delete()
        except:
            pass

        return

    # =========================
    # ACTIVE QUEST CHANNEL
    # =========================

    if message.channel.id == AVAILABLE_QUEST_CHANNEL:

        try:
            await message.delete()
        except:
            pass

        warning = await message.channel.send(
            f"{message.author.mention} "
            f"You can only use `/available_tasks` in this channel."
        )

        await asyncio.sleep(3)

        try:
            await warning.delete()
        except:
            pass

        return

    # =========================
    # REPORT CHANNEL
    # =========================

    if message.channel.id == REPORT_CHANNEL:

        try:
            await message.delete()
        except:
            pass

        warning = await message.channel.send(
            f"{message.author.mention} "
            f"You can only use `/report` in this channel."
        )

        await asyncio.sleep(3)

        try:
            await warning.delete()
        except:
            pass

        return

    # =========================
    # PAID QUEST CHANNEL
    # =========================

    if message.channel.id == PAID_QUEST_CHANNEL:

        try:
            await message.delete()
        except:
            pass

        warning = await message.channel.send(
            f"{message.author.mention} "
            f"You can only use `/paid_quest` in this channel."
        )

        await asyncio.sleep(3)

        try:
            await warning.delete()
        except:
            pass

        return

    # =========================
    # LEADERBOARD CHANNEL
    # =========================

    if message.channel.id == STATS_CHANNEL:

        allowed = [
            "/profile"
        ]

        try:
            await message.delete()
        except:
            pass

        warning = await message.channel.send(
            f"{message.author.mention} "
            f"You can only use `/profile` in this channel."
        )

        await asyncio.sleep(3)

        try:
            await warning.delete()
        except:
            pass

        return

    # =========================
    # LEADERBOARD CHANNEL
    # =========================

    if message.channel.id == GOLD_LEADERBOARD_CHANNEL:

        allowed = [
            "/leaderboard",
        ]

        try:
            await message.delete()
        except:
            pass

        warning = await message.channel.send(
            f"{message.author.mention} "
            f"You can only use `/leaderboard` "
        )

        await asyncio.sleep(3)

        try:
            await warning.delete()
        except:
            pass

        return

    # =========================
    # ENGAGEMENT LEADERBOARD CHANNEL
    # =========================

    if message.channel.id == LEADERBOARD_CHANNEL:

        allowed = [
            "/velorax_leaderboard",
        ]

        try:
            await message.delete()
        except:
            pass

        warning = await message.channel.send(
            f"{message.author.mention} "
            f"You can only use `/velorax_leaderboard` "
        )

        await asyncio.sleep(3)

        try:
            await warning.delete()
        except:
            pass

        return

    if not message.attachments:
        return

    if not isinstance(message.channel, discord.Thread):
        return

    # =========================
    # GET QUEST ID FROM THREAD
    # =========================

    cursor.execute("""
    SELECT quest_id
    FROM quests
    WHERE proof_thread_id = ?
    """, (message.channel.id,))

    thread_quest = cursor.fetchone()

    if not thread_quest:
        return

    quest_id = thread_quest[0]

    # =========================
    # DUPLICATE CHECK
    # =========================

    cursor.execute("""
        SELECT id
        FROM submissions
        WHERE user_id = ?
        AND quest_id = ?
        """, (
        message.author.id,
        quest_id
    ))

    existing = cursor.fetchone()

    if existing:
        await message.reply(
            "❌ You already submitted proof for this quest."
        )

        return

    # =========================
    # GET IMAGE
    # =========================

    attachment = message.attachments[0]

    if not attachment.content_type.startswith("image"):
        await message.reply(
            "❌ Please upload an image."
        )

        return

    # =========================
    # SAVE SUBMISSION
    # =========================

    cursor.execute("""
        INSERT INTO submissions (
            user_id,
            quest_id,
            reply_link,
            status
        )
        VALUES (?, ?, ?, 'pending')
        """, (
        message.author.id,
        quest_id,
        attachment.url
    ))

    conn.commit()

    submission_id = cursor.lastrowid

    # =========================
    # QUEST INFO
    # =========================

    cursor.execute("""
        SELECT title
        FROM quests
        WHERE quest_id = ?
        """, (quest_id,))

    quest_title = cursor.fetchone()[0]

    # =========================
    # GET USER X
    # =========================

    cursor.execute("""
        SELECT x_username
        FROM users
        WHERE user_id = ?
        """, (message.author.id,))

    user_data = cursor.fetchone()

    x_username = (
        user_data[0]
        if user_data
        else "unknown"
    )

    # =========================
    # REVIEW EMBED
    # =========================

    embed = discord.Embed(
        title=f"Quest #{quest_id} Submission",
        color=discord.Color.orange()
    )

    embed.add_field(
        name="Member",
        value=message.author.mention,
        inline=False
    )

    embed.add_field(
        name="Quest",
        value=quest_title,
        inline=False
    )

    embed.add_field(
        name="X Profile",
        value=f"https://x.com/{x_username}",
        inline=False
    )

    embed.set_image(
        url=attachment.url
    )

    embed.set_thumbnail(
        url=message.author.display_avatar.url
    )

    # =========================
    # SEND TO APPROVAL
    # =========================

    approval_channel = message.guild.get_channel(
        VIP_APPROVAL_CHANNEL
    )

    approval_message = await approval_channel.send(
        embed=embed,
        view=ApprovalView(
            message.author.id,
            quest_id,
            submission_id
        )
    )

    # =========================
    # SUBMISSION QUEUE LOG
    # =========================

    cursor.execute("""
    SELECT
        title,
        current_claims,
        max_claims,
        message_id
    FROM quests
    WHERE quest_id = ?
    """, (quest_id,))

    quest_info = cursor.fetchone()

    quest_title = quest_info[0]
    current_claims = quest_info[1]
    max_claims = quest_info[2]
    quest_message_id = quest_info[3]

    queue_channel = message.guild.get_channel(
        SUBMISSION_QUEUE_CHANNEL
    )

    queue_embed = discord.Embed(
        title="🕒 Paid Quest Submission Queue",
        color=discord.Color.orange()
    )

    queue_embed.add_field(
        name="Quest",
        value=(
            f"**Quest #{quest_id} - {quest_title}**\n"
            f"[Jump to Quest]"
            f"(https://discord.com/channels/"
            f"{message.guild.id}/"
            f"{PAID_QUEST_CHANNEL}/"
            f"{quest_message_id})"
        ),
        inline=False
    )

    queue_embed.add_field(
        name="Member",
        value=message.author.mention,
        inline=False
    )

    queue_embed.add_field(
        name="Slots",
        value=f"{current_claims}/{max_claims}",
        inline=False
    )

    queue_embed.add_field(
        name="Submission",
        value=f"[View Submission]({approval_message.jump_url})",
        inline=False
    )

    queue_embed.add_field(
        name="Status",
        value="🟡 Under Review",
        inline=False
    )

    queue_embed.set_thumbnail(
        url=message.author.display_avatar.url
    )

    queue_log_message = await queue_channel.send(
        embed=queue_embed
    )

    # =========================
    # SAVE MESSAGE IDS
    # =========================

    cursor.execute("""
    UPDATE submissions
    SET
        approval_message_id = ?,
        queue_message_id = ?
    WHERE id = ?
    """, (
        approval_message.id,
        queue_log_message.id,
        submission_id
    ))

    conn.commit()

    await message.reply(
        "✅ Submission received and pending review."
    )

    await bot.process_commands(message)


# =========================
# READY
# =========================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    if not update_priority_access.is_running():
        update_priority_access.start()

    if not monthly_leaderboard_scheduler.is_running():
        monthly_leaderboard_scheduler.start()

    if not reminder_loop.is_running():
        reminder_loop.start()

        # Send one immediately on startup
        await send_random_announcement()

    if not offense_expiration_loop.is_running():
        offense_expiration_loop.start()

    if not giveaway_loop.is_running():
        giveaway_loop.start()


    cursor.execute("""
        SELECT giveaway_id
        FROM giveaways
        WHERE completed = 0
        """)

    active = cursor.fetchone()

    if not active:

        guild = bot.get_guild(GUILD_ID)

        if guild:
            await create_new_giveaway(guild)

    if not giveaway_draw_task.is_running():
        giveaway_draw_task.start()

    if not admin_creator_points_loop.is_running():
        admin_creator_points_loop.start()

    await give_admin_creator_points()

    for guild in bot.guilds:
        invite_cache[guild.id] = {
            invite.code: invite.uses
            for invite in await guild.invites()
        }

if __name__ == "__main__":
    bot.run(TOKEN)

