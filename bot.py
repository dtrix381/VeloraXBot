import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import sqlite3
import asyncio
from datetime import datetime, timedelta, UTC
import re
import os

GUILD_OWNER_ID = 488015447417946151
ADMIN_ROLE_ID = 1501472062903156756 #Team
MEMBER_ROLE_ID = 1501473138188353616 #Creator
VERIFIED_ROLE_ID = 1501473283852472380 #Engager
WELCOME_CHANNEL_ID = 1501481909337718824
INVITE_APPROVAL_CHANNEL_ID = 1507312406395752458
BOT_INVITER_ID = 1501868266614947880
SUPPORT_CATEGORY_ID = 1501483613529706528
ADMIN_REVIEW_CHANNEL_ID = 1507604124366147735
FIRST_OFFENSE_ROLE = 1507613554910433320
SECOND_OFFENSE_ROLE = 1507613855587766302

CATEGORY_NAME = 1507640053315407904
REGISTER_CHANNEL = 1507640055680733244
INVITE_CHANNEL = 1507640057287409786
QUEST_CHANNEL = 1507640059560595536
REPORT_CHANNEL = 1507640061787639901
LOGS_CHANNEL = 1507640063666946221
STATS_CHANNEL = 1507640065826754630

VIP_CATEGORY_NAME = 1507640088413339802
PAID_QUEST_CHANNEL = 1507640090418086019
VIP_APPROVAL_CHANNEL = 1507640092494266418
GOLD_LOGS_CHANNEL = 1507640096290242612
GOLD_LEADERBOARD_CHANNEL = 1507640098521481236
SHOP_CHANNEL = 1507640118616391802
APPROVAL_CHANNEL = 1507640094951997460


EXCHANGE_GOLD_COST = 100
EXCHANGE_REWARD = "$10"

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
bot = commands.Bot(command_prefix="!", intents=intents)

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

def get_user_rank(user_id):

    cursor.execute("""
    SELECT user_id
    FROM users
    ORDER BY points DESC
    """)

    users = cursor.fetchall()

    for index, (uid,) in enumerate(users, start=1):
        if uid == user_id:
            return index

    return "Unranked"

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
            f"You can only use `/create_quest` in this channel."
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

    if message.channel.id== REPORT_CHANNEL:

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
            f"or `/profile` in this channel."
        )

        await asyncio.sleep(3)

        try:
            await warning.delete()
        except:
            pass

        return

    await bot.process_commands(message)


# =========================
# APPROVAL CONFIRMATION VIEW
# =========================
class ApprovalConfirmView(ui.View):
    def __init__(self, original_embed, original_view, new_member, inviter, original_username):
        super().__init__(timeout=None)
        self.original_embed = original_embed
        self.original_view = original_view
        self.new_member = new_member
        self.inviter = inviter
        self.original_username = original_username
        self.ADMIN_ROLE_ID = 1501472062903156756
        self.VERIFIED_ROLE_ID = 1501473138188353616

    @ui.button(label="Yes", style=discord.ButtonStyle.success, custom_id="confirm_approve_yes")
    async def confirm_yes(self, interaction: discord.Interaction, button: ui.Button):

        admin_role = interaction.guild.get_role(self.ADMIN_ROLE_ID)
        if admin_role not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ Only Admins can click this button.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        # =========================
        # 1. GIVE ROLE TO USER
        # =========================
        try:
            verified_role = interaction.guild.get_role(self.VERIFIED_ROLE_ID)
            if verified_role and self.new_member:
                await self.new_member.add_roles(
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
        """, (self.new_member.id,))

        # =========================
        # 3. GIVE GOLD TO INVITER (EXCEPT BOT)
        # =========================
        is_bot_invite = False

        if self.inviter and self.inviter.id != BOT_INVITER_ID:
            cursor.execute("""
                UPDATE users
                SET gold_points = COALESCE(gold_points, 0) + 1
                WHERE user_id = ?
            """, (self.inviter.id,))
        else:
            is_bot_invite = True

        # =========================
        # 4. MARK INVITE REWARDED
        # =========================
        cursor.execute("""
            UPDATE invite_joins
            SET rewarded = 1
            WHERE invited_id = ?
        """, (self.new_member.id,))

        # =========================
        # 5. GET TOTAL GOLD (SAFE)
        # =========================
        total_gold = 0

        admin_role = interaction.guild.get_role(ADMIN_ROLE_ID)

        if (
                self.inviter
                and not is_bot_invite
                and admin_role not in self.inviter.roles
        ):
            cursor.execute("""
                SELECT gold_points
                FROM users
                WHERE user_id = ?
            """, (self.inviter.id,))

            result = cursor.fetchone()
            total_gold = result[0] if result else 0

        conn.commit()

        # =========================
        # 5. CREATOR LOGS
        # =========================
        log_channel = guild.get_channel(LOGS_CHANNEL)
        if log_channel:
            await log_channel.send(
                f"🎉 **Creator Approved**\n\n"
                f"👤 **Member:** {self.new_member.mention}\n"
                f"🪪 **Reward:** :gem: +25 Creator Points\n\n"
                f"👮 **Approved by:** {interaction.user.mention}"
            )

        # =========================
        # 6. GOLD LOGS (ONLY IF NOT BOT INVITE)
        # =========================
        gold_log_channel = guild.get_channel(GOLD_LOGS_CHANNEL)

        if (
                gold_log_channel
                and self.inviter
                and not is_bot_invite
                and admin_role not in self.inviter.roles
        ):
            await gold_log_channel.send(
                f"💰 **Golds Awarded via Invite Referral System**\n\n"
                f"👤 **Creator:** {self.new_member.mention}\n"
                f"👑 **Inviter:** {self.inviter.mention}\n\n"
                f"💰 **Reward:** :moneybag: +1 Gold Point\n"
                f"📊 **Total Gold Points:** :moneybag: {total_gold}\n\n"
                f"👮 **Approved by:** {interaction.user.mention}"
            )

        # =========================
        # 7. MOVE TO APPROVED CHANNEL
        # =========================
        approved_channel = interaction.guild.get_channel(1507427342967115866)

        if approved_channel:
            await approved_channel.send(embed=self.original_embed)

        try:
            await interaction.message.delete()
        except:
            pass

        # =========================
        # 8. UPDATE ORIGINAL EMBED
        # =========================
        self.original_embed.color = discord.Color.blue()
        self.original_embed.title = "Creator Registration - Approved ✅"
        self.original_embed.add_field(
            name="Approved By",
            value=interaction.user.mention,
            inline=False
        )

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
    def __init__(self, original_username, new_member, inviter):
        super().__init__(timeout=None)
        self.original_username = original_username
        self.new_member = new_member
        self.inviter = inviter
        self.ADMIN_ROLE_ID = 1501472062903156756

        # Add the baseline profile button link immediately
        self.add_item(ui.Button(label="Review Profile", url=f"https://x.com/{original_username}"))

    @ui.button(label="Approved Creator", style=discord.ButtonStyle.primary, custom_id="trigger_approve_flow")
    async def approve_creator_click(self, interaction: discord.Interaction, button: ui.Button):
        admin_role = interaction.guild.get_role(self.ADMIN_ROLE_ID)
        if admin_role not in interaction.user.roles:
            await interaction.response.send_message("❌ Only Admins can click this button.", ephemeral=True)
            return

        # Create confirmation screen overlay setup
        confirm_embed = discord.Embed(
            title="⚠️ Action Confirmation Required",
            description=f"Are you sure you want to approve {self.new_member.mention if self.new_member else 'this creator'}?",
            color=discord.Color.orange()
        )

        confirm_view = ApprovalConfirmView(
            original_embed=interaction.message.embeds[0],
            original_view=self,
            new_member=self.new_member,
            inviter=self.inviter,
            original_username=self.original_username
        )

        await interaction.response.edit_message(embed=confirm_embed, view=confirm_view)


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

        original_username = str(self.username).replace("@", "").strip()

        lowercase_username = original_username.lower()

        if not re.match(r"^[A-Za-z0-9_]+$", original_username):
            await interaction.response.send_message(
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

            # Brand new user: safe to award 25 points
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

        if invite_data:
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
                    value=inviter.mention if hasattr(inviter, "mention") else str(inviter),
                    inline=False
                )

                embed.add_field(
                    name="X Profile",
                    value=f"https://x.com/{original_username}",
                    inline=False
                )

                view = CreatorReviewView(
                    original_username,
                    interaction.user,
                    inviter
                )

                await approval_channel.send(embed=embed, view=view)

        await interaction.response.send_message(success_message, ephemeral=True)



        # Dynamic lookup for your stylized log channel name
        try:
            log_channel = guild.get_channel(LOGS_CHANNEL)
            if log_channel:
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

        # +1 gold to inviter
        cursor.execute("""
        UPDATE users
        SET gold_points = gold_points + 1
        WHERE user_id = ?
        """, (self.inviter_id,))

        cursor.execute("""
        UPDATE invite_joins
        SET rewarded = 1
        WHERE invited_id = ?
        """, (self.user_id,))

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
                max_age=0,   # Never expires
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

    def __init__(self, quest_id):
        super().__init__(title=f"Submit Quest #{quest_id}")
        self.quest_id = quest_id

    reply_link = ui.TextInput(
        label="Reply Link",
        placeholder="Paste your reply link here",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):

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
            await interaction.response.send_message(
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
            await interaction.response.send_message(
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
            await interaction.response.send_message(
                "Your submission is still pending.",
                ephemeral=True
            )
            return

        # =========================
        # VALIDATE REPLY LINK
        # =========================

        submitted_link = str(self.reply_link).strip().lower()

        expected_link = f"https://x.com/{registered_username}"

        if not submitted_link.startswith(expected_link):
            await interaction.response.send_message(
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

        embed = discord.Embed(
            title=f"Quest #{self.quest_id} Submission",
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

        await interaction.response.send_message(
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

        # SUBMIT BUTTON

        submit_button = ui.Button(
            label="Submit Quest",
            style=discord.ButtonStyle.green,
            custom_id=f"submit_quest_{quest_id}"
        )

        async def submit_callback(interaction: discord.Interaction):

            cursor.execute("""
            SELECT expires_at FROM quests
            WHERE quest_id = ?
            """, (self.quest_id,))

            quest = cursor.fetchone()

            if not quest:
                await interaction.response.send_message(
                    "Quest not found.",
                    ephemeral=True
                )
                return

            expires_at = datetime.fromisoformat(quest[0])

            if datetime.now(UTC) > expires_at:
                await interaction.response.send_message(
                    "This quest has expired.",
                    ephemeral=True
                )
                return

            await interaction.response.send_modal(
                SubmitQuestModal(self.quest_id)
            )

        submit_button.callback = submit_callback

        self.add_item(submit_button)

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

            # =========================
            # ADD POINT + QUEST COUNT
            # =========================

            cursor.execute("""
            UPDATE users
            SET gold_points = gold_points + 1,
                quests_completed = quests_completed + 1
            WHERE user_id = ?
            """, (self.user_id,))

            conn.commit()

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

            user = interaction.guild.get_member(
                self.user_id
            )

            await logs_channel.send(
                f"{user.mention} completed "
                f"**Quest #{self.quest_id} - {quest_title}** "
                f"and earned :moneybag:  1 **Gold Points**\n\n"
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

            cursor.execute("""
            UPDATE submissions
            SET status = 'denied'
            WHERE id = ?
            AND status != 'denied'
            """, (self.submission_id,))

            cursor.execute("""
            UPDATE users
            SET quests_denied = quests_denied + 1
            WHERE user_id = ?
            """, (self.user_id,))

            conn.commit()

            logs_channel = get_channel(
                interaction.guild,
                LOGS_CHANNEL
            )

            user = interaction.guild.get_member(
                self.user_id
            )

            await logs_channel.send(
                f"{user.mention}'s submission for "
                f"**Quest #{self.quest_id} - {quest_title}** "
                f"was denied by "
                f"{interaction.user.mention}"
            )

            await interaction.message.delete()

        deny_button.callback = deny_callback

        self.add_item(deny_button)

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

    register_channel = get_channel_by_name(guild, REGISTER_CHANNEL)
    if not register_channel:
        register_channel = await guild.create_text_channel(
            REGISTER_CHANNEL,
            category=category
        )

    # INVITE CHANNEL

    invite_channel = get_channel_by_name(guild, INVITE_CHANNEL)
    if not invite_channel:
        invite_channel = await guild.create_text_channel(
            INVITE_CHANNEL,
            category=category
        )

    # QUEST CHANNEL

    quest_channel = get_channel_by_name(guild, QUEST_CHANNEL)
    if not quest_channel:
        quest_channel = await guild.create_text_channel(
            QUEST_CHANNEL,
            category=category
        )

    # REPORT CHANNEL

    report_channel = get_channel_by_name(guild, REPORT_CHANNEL)
    if not report_channel:
        report_channel = await guild.create_text_channel(
            REPORT_CHANNEL,
            category=category
        )

    # LOGS CHANNEL

    logs_channel = get_channel_by_name(guild, LOGS_CHANNEL)
    if not logs_channel:
        logs_channel = await guild.create_text_channel(
            LOGS_CHANNEL,
            category=category
        )

    stats_channel = get_channel_by_name(guild, STATS_CHANNEL)
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

    approval_channel = get_channel_by_name(guild, APPROVAL_CHANNEL)
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
# QUEST CREATE COMMAND
# =========================

@bot.tree.command(name="paid_quest")
async def paid_quest(interaction: discord.Interaction):

    if interaction.channel.name != PAID_QUEST_CHANNEL:

        quest_channel = get_channel(
            interaction.guild,
            QUEST_CHANNEL
        )

        await interaction.response.send_message(
            f"You can only use this command in {quest_channel.mention}",
            ephemeral=True
        )

        return

    if not has_admin_role(interaction.user):

        await interaction.response.send_message(
            "No permission.",
            ephemeral=True
        )

        return

    class QuestModal(ui.Modal):

        def __init__(self):
            super().__init__(title="Create Quest")

            # =========================
            # QUEST TITLE
            # =========================

            self.quest_title = ui.TextInput(
                label="Quest Title",
                placeholder="Enter quest title",
                required=True,
                max_length=100
            )

            self.add_item(self.quest_title)

            # =========================
            # TWEET LINK
            # =========================

            self.tweet_link = ui.TextInput(
                label="Tweet Link",
                placeholder="Paste tweet link here",
                required=True
            )

            self.add_item(self.tweet_link)

        async def on_submit(
                self,
                modal_interaction: discord.Interaction
        ):
            created_at = datetime.now(UTC)
            expires_at = created_at + timedelta(hours=24)

            cursor.execute("""
            INSERT INTO quests (
                title,
                tweet_link,
                created_by,
                created_at,
                expires_at
            )
            VALUES (?, ?, ?, ?, ?)
            """, (
                str(self.quest_title),
                str(self.tweet_link),
                modal_interaction.user.id,
                created_at.isoformat(),
                expires_at.isoformat()
            ))

            conn.commit()

            quest_id = cursor.lastrowid

            embed = discord.Embed(
                title=(
                    f"Quest #{quest_id} - "
                    f"{self.quest_title}"
                ),
                color=0x2ECC71
            )

            embed.add_field(
                name="Time Left",
                value="24 Hours Left",
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
                value=(
                    "Like and Comment on the Post "
                    "and Submit your Reply Link"
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

            cursor.execute("""
            UPDATE quests
            SET message_id = ?
            WHERE quest_id = ?
            """, (
                msg.id,
                quest_id
            ))

            conn.commit()

            await modal_interaction.channel.send(
                f"<@&{MEMBER_ROLE_ID}> "
                f"Raid now to earn :moneybag:  **Gold Points**"
            )

            await modal_interaction.response.send_message(
                "Quest created.",
                ephemeral=True
            )

    await interaction.response.send_modal(QuestModal())

# =========================
# UPDATE QUEST STATUS
# =========================

@tasks.loop(minutes=1)
async def update_quests():

    for guild in bot.guilds:

        channel = get_channel(guild, QUEST_CHANNEL)

        if not channel:
            continue

        cursor.execute("""
        SELECT quest_id, expires_at, message_id
        FROM quests
        """)

        quests = cursor.fetchall()

        for quest_id, expires_at, message_id in quests:

            try:
                message = await channel.fetch_message(message_id)

                embed = message.embeds[0]

                new_time = time_left(expires_at)

                current_time = embed.fields[0].value

                # ONLY EDIT IF DIFFERENT

                if current_time != new_time:
                    embed.set_field_at(
                        0,
                        name="Time Left",
                        value=new_time,
                        inline=False
                    )

                    await message.edit(embed=embed)

            except:
                pass


async def load_persistent_views():

    # =========================
    # QUEST VIEWS
    # =========================

    cursor.execute("""
    SELECT quest_id, tweet_link
    FROM quests
    """)

    quests = cursor.fetchall()

    for quest_id, tweet_link in quests:

        try:

            bot.add_view(
                QuestView(
                    quest_id,
                    tweet_link
                )
            )

        except Exception as e:
            print(e)

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
            print(e)

        # =========================
        # SHOP VIEW
        # =========================

    try:
        bot.add_view(ShopView())
    except Exception as e:
        print(e)


@bot.tree.command(name="profile")
@app_commands.describe(member="Select member")
async def profile(
        interaction: discord.Interaction,
        member: discord.Member
):

    if interaction.channel.name != STATS_CHANNEL:
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
    SELECT x_username, points, gold_points, quests_completed, quests_denied
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
    LIMIT 10
    """, (member.id,))

    history = cursor.fetchall()

    if not data:

        await interaction.response.send_message(
            "User not registered.",
            ephemeral=True
        )

        return

    x_username, points, gold_points, completed, denied = data

    rank = get_user_rank(member.id)

    embed = discord.Embed(
        title=f"{member.display_name} - Rank #{rank}",
        color=discord.Color.gold()
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.add_field(
        name="Gold Points",
        value=f":moneybag: {points}",
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
        name="X Profile",
        value=f"https://x.com/{x_username}",
        inline=False
    )

    history_embed = discord.Embed(
        title="📜 Paid Quests History",
        color=discord.Color.blurple()
    )

    for (
            quest_id,
            quest_title,
            message_id,
            reply_link,
            completed_at
    ) in history:
        # QUEST CHANNEL
        quest_channel = get_channel(
            interaction.guild,
            QUEST_CHANNEL
        )

        # QUEST MESSAGE LINK
        quest_message_url = (
            f"https://discord.com/channels/"
            f"{interaction.guild.id}/"
            f"{quest_channel.id}/"
            f"{message_id}"
        )

        # FORMAT TIME
        completed_dt = datetime.fromisoformat(str(completed_at))

        discord_timestamp = int(
            completed_dt.timestamp()
        )

        history_embed.add_field(
            name=(
                f"[Quest #{quest_id} - {quest_title}]"
                f"({quest_message_url})"
            ),
            value=(
                f"[<t:{discord_timestamp}:R>]"
                f"({reply_link})"
            ),
            inline=False
        )

        await interaction.response.send_message(
            embeds=[embed, history_embed]
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

    if interaction.channel.name != GOLD_LEADERBOARD_CHANNEL:

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
    SELECT user_id, x_username, points, gold_points, quests_completed, quests_denied
    FROM users
    ORDER BY gold_points DESC,
             points DESC,
             quests_completed DESC,
             quests_denied ASC
    """)
    users = cursor.fetchall()

    print(users)

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
                gold_points,
                completed,
                denied
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

        # =========================
        # CHECK DUPLICATE CLAIM
        # =========================

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

            await interaction.response.send_message(
                "❌ You already claimed this quest.",
                ephemeral=True
            )

            return

        # =========================
        # GIVE 1 POINT
        # =========================

        cursor.execute("""
        UPDATE users
        SET points = COALESCE(points, 0) + 1
        WHERE user_id = ?
        """, (interaction.user.id,))

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

        # =========================
        # GET TOTAL POINTS
        # =========================

        cursor.execute("""
        SELECT points
        FROM users
        WHERE user_id = ?
        """, (interaction.user.id,))

        result = cursor.fetchone()

        total_points = result[0] if result else 0

        conn.commit()

        # =========================
        # LOG CLAIM
        # =========================

        log_channel = guild.get_channel(LOGS_CHANNEL)

        if log_channel:

            await log_channel.send(
                f"**Quest Claimed**\n\n"
                f"**Member:** {interaction.user.mention}\n"
                f"**Quest:** {self.quest_title}\n"
                f"**Reward:** :gem: +1 **Creator Point**\n"
                f"**Total Creator Points:** :gem: {total_points}"
            )

        await interaction.response.send_message(
            "✅ You successfully claimed :gem: +1 Creator Point.",
            ephemeral=True
        )


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

            if current_points < 20:

                await modal_interaction.response.send_message(
                    "❌ You need at least :gem: 20 Creator Points to create a quest.",
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
                f"{registered_username.lower()}"
            )

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

                def __init__(self, quest_title, submitted_link, modal_interaction):
                    super().__init__(timeout=180)

                    self.quest_title = quest_title
                    self.submitted_link = submitted_link
                    self.modal_interaction = modal_interaction

                @ui.button(
                    label="Run Quest (-20 Points)",
                    style=discord.ButtonStyle.green
                )
                async def confirm(
                        self,
                        confirm_interaction: discord.Interaction,
                        button: ui.Button
                ):
                    # =========================
                    # REMOVE 20 POINTS
                    # =========================

                    cursor.execute("""
                    UPDATE users
                    SET points = points - 20
                    WHERE user_id = ?
                    """, (
                        self.modal_interaction.user.id,
                    ))

                    created_at = datetime.now(UTC)

                    expires_at = (
                            created_at +
                            timedelta(hours=24)
                    )

                    # =========================
                    # INSERT QUEST
                    # =========================

                    cursor.execute("""
                    INSERT INTO quests (
                        title,
                        tweet_link,
                        created_by,
                        created_at,
                        expires_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """, (
                        self.quest_title,
                        self.submitted_link,
                        self.modal_interaction.user.id,
                        created_at.isoformat(),
                        expires_at.isoformat()
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
                        name="Time Left",
                        value="24 Hours Left",
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
                            "Like, repost, and comment "
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

                    quest_channel = guild.get_channel(QUEST_CHANNEL)

                    msg = await quest_channel.send(
                        embed=embed,
                        view=CommunityQuestView(
                            quest_id,
                            self.quest_title,
                            self.submitted_link
                        )
                    )

                    await quest_channel.send(
                        f"<@&{MEMBER_ROLE_ID}> New Creator Quest is Live!"
                    )

                    # =========================
                    # SAVE MESSAGE ID
                    # =========================

                    cursor.execute("""
                    UPDATE quests
                    SET message_id = ?
                    WHERE quest_id = ?
                    """, (
                        msg.id,
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
                            f"**Cost:** :gem: -20 **Creator Points**\n"
                            f"**Total Creator Points:** :gem: {total_points}"
                        )

                    # =========================
                    # SUCCESS
                    # =========================

                    await confirm_interaction.response.edit_message(
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
                f":gem: 20 Creator Points.\n\n"
                f"Do you want to continue?",
                view=ConfirmQuestView(
                    str(self.quest_title),
                    submitted_link,
                    modal_interaction
                ),
                ephemeral=True
            )

    await interaction.response.send_modal(
        CreateQuestModal()
    )


# =========================
# LOAD PERSISTENT VIEWS
# =========================

async def load_persistent_views():

    # =========================
    # COMMUNITY QUEST VIEWS
    # =========================

    cursor.execute("""
    SELECT quest_id, title, tweet_link
    FROM quests
    """)

    quests = cursor.fetchall()

    for quest_id, title, tweet_link in quests:

        try:

            bot.add_view(
                CommunityQuestView(
                    quest_id,
                    title,
                    tweet_link
                )
            )

        except Exception as e:
            print(e)

# =========================
# SHOP VIEW
# =========================

class ShopView(ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Exchange 100 Gold Points",
        style=discord.ButtonStyle.green,
        custom_id="exchange_gold_button"
    )
    async def exchange_gold(
            self,
            interaction: discord.Interaction,
            button: ui.Button
    ):

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

        if total_gold < EXCHANGE_GOLD_COST:
            needed = EXCHANGE_GOLD_COST - total_gold

            await interaction.response.send_message(
                f"You need :moneybag: {EXCHANGE_GOLD_COST} Gold Points to exchange for **$10**.\n\n"
                f"**Your Current Gold Points:** :moneybag: {total_gold}\n"
                f"**Gold Points Needed:** :moneybag: {needed}",
                ephemeral=True
            )

            return

        # =========================
        # CONFIRM VIEW
        # =========================

        class ConfirmExchangeView(ui.View):

            def __init__(self):
                super().__init__(timeout=180)

            @ui.button(
                label="Continue Exchange",
                style=discord.ButtonStyle.green
            )
            async def confirm(
                    self,
                    confirm_interaction: discord.Interaction,
                    button: ui.Button
            ):

                # =========================
                # REMOVE GOLD
                # =========================

                cursor.execute("""
                UPDATE users
                SET gold_points = gold_points - ?
                WHERE user_id = ?
                """, (
                    EXCHANGE_GOLD_COST,
                    interaction.user.id
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

                    interaction.user: discord.PermissionOverwrite(
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
                    interaction.user.display_name
                    .lower()
                    .replace(" ", "-")
                )

                support_channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites
                )

                # 🔥 IMPORTANT
                await support_channel.edit(
                    topic=f"user_id:{interaction.user.id}"
                )

                embed = discord.Embed(
                    title="💰 Gold Exchange Request",
                    color=0xF1C40F
                )

                embed.add_field(name="User", value=interaction.user.mention, inline=False)
                embed.add_field(name="Exchange", value=f"{EXCHANGE_GOLD_COST} → {EXCHANGE_REWARD}", inline=False)
                embed.add_field(name="Status", value="Pending Admin Review", inline=False)
                embed.set_thumbnail(url=interaction.user.display_avatar.url)

                # ✅ ADD IMAGE HERE
                embed.set_image(url="https://cdn.discordapp.com/attachments/1225024450345439313/1507356644667949217/10_dollar_velorax.png?ex=6a124385&is=6a10f205&hm=f1cb3d036fa2cafb3ef83867c680cbe9014a235f4ca870a12e06a9545d91eb01")

                await support_channel.send(
                    content=f"{interaction.user.mention} <@&{ADMIN_ROLE_ID}>",
                    embed=embed,
                    view=CloseTicketView()  # ✅ FIXED HERE
                )

                # =========================
                # LOGS
                # =========================

                log_channel = guild.get_channel(GOLD_LOGS_CHANNEL)

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
                        f"💰 **Gold Exchange Started**\n\n"
                        f"👤 **User:** {interaction.user.mention}\n"
                        f"**Spent:** :moneybag: "
                        f"{EXCHANGE_GOLD_COST} Gold Points\n"
                        f"**Exchange Value:** **{EXCHANGE_REWARD}**\n"
                        f"**Remaining Gold:** "
                        f":moneybag: {remaining_gold}"
                    )

                await confirm_interaction.response.edit_message(
                    content=(
                        f"✅ Exchange request created:\n"
                        f"{support_channel.mention}"
                    ),
                    embed=None,
                    view=None
                )

        await interaction.response.send_message(
            f"⚠️ Exchange "
            f":moneybag:  {EXCHANGE_GOLD_COST} Gold Points "
            f"for **{EXCHANGE_REWARD}**?",
            view=ConfirmExchangeView(),
            ephemeral=True
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

        user_id = int(topic.split(":")[1])
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

        await interaction.response.send_message("Reopened.", ephemeral=True)

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
            view=ClosedTicketView(self.user_id)
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

        user_id = int(topic.split(":")[1])
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
        user_id = int(topic.split(":")[1])
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

        view = PayoutConfirmView(user.id, interaction.user.id)

        await interaction.response.send_message(
            content=user.mention,
            embed=embed,
            view=view
        )

class PayoutConfirmView(ui.View):

    def __init__(self, user_id: int, admin_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.admin_id = admin_id

    @ui.button(label="✅ I Received It", style=discord.ButtonStyle.green)
    async def yes(self, interaction: discord.Interaction, button: ui.Button):

        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "Only the exchange user can confirm.",
                ephemeral=True
            )

        guild = interaction.guild
        admin = guild.get_member(self.admin_id)

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
                value=f"{EXCHANGE_GOLD_COST} Gold Points",
                inline=True
            )

            embed.add_field(
                name="Received",
                value=f"{EXCHANGE_REWARD}",
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

        await interaction.response.edit_message(
            content="✅ Payout confirmed.",
            embed=None,
            view=None
        )

    @ui.button(label="❌ Not Yet", style=discord.ButtonStyle.red)
    async def no(self, interaction: discord.Interaction, button: ui.Button):

        if interaction.user.id != self.user_id:
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


@bot.tree.command(name="report")
async def report(interaction: discord.Interaction, user: discord.Member):

    if interaction.channel.name != REPORT_CHANNEL:
        return await interaction.response.send_message(
            "❌ Use this only in the report channel",
            ephemeral=True
        )

    await interaction.response.send_modal(
        ReportModal(user)   # ✅ PASS USER HERE
    )

class ReportPublishView(ui.View):

    def __init__(self, creator_id, tweet, reported):
        super().__init__(timeout=300)
        self.creator_id = creator_id
        self.tweet = tweet
        self.reported = reported

    @ui.button(label="📤 Publish", style=discord.ButtonStyle.green)
    async def publish(self, interaction: discord.Interaction, button: ui.Button):

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
        admin_channel = interaction.guild.get_channel(ADMIN_REVIEW_CHANNEL_ID)

        if admin_channel:
            await admin_channel.send(
                embed=embed,
                view=ReportReviewView(
                    int(self.reported),
                    self.creator_id,
                    msg.id
                )
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

    def __init__(self, reported_user: int, reporter_id: int, report_msg_id: int):
        super().__init__(timeout=300)
        self.reported_user = reported_user
        self.reporter_id = reporter_id
        self.report_msg_id = report_msg_id

    @ui.button(label="📎 Raid Link", style=discord.ButtonStyle.secondary)
    async def raid(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Raid link action placeholder", ephemeral=True)

    @ui.button(label="❌ Let Go", style=discord.ButtonStyle.success)
    async def let_go(self, interaction: discord.Interaction, button: ui.Button):

        guild = interaction.guild

        member = guild.get_member(self.reported_user)

        report_channel = guild.get_channel(REPORT_CHANNEL)

        # delete admin review message
        await interaction.message.delete()

        if report_channel:

            try:
                original = await report_channel.fetch_message(
                    self.report_msg_id
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

        await interaction.response.send_message(
            "Report cleared.",
            ephemeral=True
        )

    @ui.button(label="⚠️ Penalize", style=discord.ButtonStyle.danger)
    async def penalize(self, interaction: discord.Interaction, button: ui.Button):

        guild = interaction.guild

        member = guild.get_member(self.reported_user)

        if not member:
            return await interaction.response.send_message(
                "User not found.",
                ephemeral=True
            )

        first_role = guild.get_role(FIRST_OFFENSE_ROLE)
        second_role = guild.get_role(SECOND_OFFENSE_ROLE)

        report_channel = guild.get_channel(REPORT_CHANNEL)

        admin = interaction.user

        # =========================
        # OFFENSE SYSTEM
        # =========================

        if first_role not in member.roles:

            await member.add_roles(first_role)

            status = "First Offense"
            remaining = 2

        elif second_role not in member.roles:

            await member.add_roles(second_role)

            status = "Second Offense"
            remaining = 1

        else:

            await member.ban(reason="3rd offense reached")

            status = "BANNED"
            remaining = 0

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
                    self.report_msg_id
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
                    name="⚠️ Penalty",
                    value=status,
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

        await interaction.response.send_message(
            "Penalty applied.",
            ephemeral=True
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
# READY
# =========================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")

    bot.add_view(RegisterView())
    bot.add_view(InviteView())
    bot.add_view(ShopView())
    bot.add_view(CloseTicketView())
    bot.add_view(ClosedTicketView())

    await load_persistent_views()

    await bot.tree.sync()

    if not update_quests.is_running():
        update_quests.start()

    for guild in bot.guilds:
        invite_cache[guild.id] = {
            invite.code: invite.uses
            for invite in await guild.invites()
        }

# Run the bot
if __name__ == "__main__":
    bot.run(TOKEN)
