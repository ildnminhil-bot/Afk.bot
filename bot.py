Cho tôi biết thêm về nội dung này trong 1 đoạn văn.

import os
import sys
import asyncio
import time
import discord
from discord.ext import commands
from aiohttp import web

# Ép in log ngay lập tức lên Render
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# ==========================================
# CẤU HÌNH (KHÔNG DÁN TOKEN VÀO ĐÂY)
# ==========================================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "").strip()
PREFIX = os.environ.get("BOT_PREFIX", "!")

# ==========================================
# 1. WEB SERVER CHO RENDER (MỞ PORT NGAY)
# ==========================================
bot_status = {"connected": False, "last_error": "Đang khởi động..."}

async def health_check(request):
    status_text = (
        f"Bot Online: {bot_status['connected']} | "
        f"Info: {bot_status['last_error']}"
    )
    return web.Response(text=status_text, status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[WEB] Đã mở cổng {port} thành công.", flush=True)

# ==========================================
# 2. CẤU HÌNH DISCORD BOT & AFK
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Lưu trạng thái AFK: {user_id: {"reason": str, "since": float}}
afk_users = {}

def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} giây"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} phút {sec} giây"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} giờ {minutes} phút"

@bot.event
async def on_ready():
    bot_status["connected"] = True
    bot_status["last_error"] = f"Đã đăng nhập: {bot.user}"
    print(f"[BOT] Đã kết nối thành công: {bot.user} (ID: {bot.user.id})", flush=True)

@bot.command(name="afk")
async def afk_command(ctx: commands.Context, *, reason: str = "Đang bận"):
    afk_users[ctx.author.id] = {
        "reason": reason,
        "since": time.time(),
    }
    await ctx.reply(
        f"💤 **{ctx.author.display_name}** đã bật chế độ AFK: *{reason}*",
        mention_author=False,
    )

@bot.command(name="afklist")
async def afk_list_command(ctx: commands.Context):
    if not afk_users:
        await ctx.send("Hiện không có ai đang AFK.")
        return

    lines = []
    now = time.time()
    for user_id, data in afk_users.items():
        member = ctx.guild.get_member(user_id) if ctx.guild else None
        name = member.display_name if member else f"User `{user_id}`"
        elapsed = format_duration(now - data["since"])
        lines.append(f"• **{name}**: *{data['reason']}* ({elapsed} trước)")

    await ctx.send("📋 **Danh sách đang AFK:**\n" + "\n".join(lines))

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # 1. Nếu người đang AFK nhắn tin (không phải lệnh !afk) -> tự tắt AFK
    if message.author.id in afk_users:
        content_lower = message.content.strip().lower()
        if not content_lower.startswith(f"{PREFIX}afk"):
            data = afk_users.pop(message.author.id)
            elapsed = format_duration(time.time() - data["since"])
            await message.channel.send(
                f"☀️ Chào mừng **{message.author.display_name}** quay lại sau {elapsed}! Đã tắt AFK."
            )

    # 2. Nếu tin nhắn tag người đang AFK -> thông báo
    if message.mentions:
        notified = set()
        now = time.time()
        for user in message.mentions:
            if user.id in afk_users and user.id != message.author.id and user.id not in notified:
                notified.add(user.id)
                data = afk_users[user.id]
                elapsed = format_duration(now - data["since"])
                await message.reply(
                    f"💤 **{user.display_name}** hiện đang AFK ({elapsed} trước): *{data['reason']}*",
                    mention_author=False,
                )

    await bot.process_commands(message)

# ==========================================
# 3. CHẠY BOT VỚI CƠ CHẾ TỰ THỬ LẠI (TRÁNH LỖI CLOUDFLARE)
# ==========================================
async def main():
    print("[INIT] Bắt đầu khởi chạy bot.py...", flush=True)
    await start_web_server()

    if not DISCORD_TOKEN:
        print("[LỖI] Chưa cài đặt biến môi trường DISCORD_TOKEN trên Render!", flush=True)
        while True:
            await asyncio.sleep(60)

    retry_delay = 30
    while True:
        try:
            print("[BOT] Đang kết nối tới Discord...", flush=True)
            async with bot:
                await bot.start(DISCORD_TOKEN)
        except discord.LoginFailure:
            bot_status["connected"] = False
            bot_status["last_error"] = "Token không hợp lệ (LoginFailure). Hãy kiểm tra lại DISCORD_TOKEN."
            print("[LỖI NGHIÊM TRỌNG] Token sai hoặc đã bị thu hồi! Vui lòng cập nhật DISCORD_TOKEN mới.", flush=True)
            await asyncio.sleep(300)
        except discord.HTTPException as e:
            bot_status["connected"] = False
            bot_status["last_error"] = f"HTTPException {e.status} - Đang đợi thử lại..."
            print(f"[CẢNH BÁO] Discord/Cloudflare trả về lỗi HTTP {e.status}. Đợi {retry_delay}s trước khi thử lại...", flush=True)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 300)
        except Exception as e:
            bot_status["connected"] = False
            bot_status["last_error"] = f"Lỗi: {type(e).__name__}"
            print(f"[LỖI] Gặp sự cố {type(e).__name__}: {e}. Thử lại sau {retry_delay}s...", flush=True)
            await asyncio.sleep(retry_delay)

if __name__ == "__main__":
    asyncio.run(main())
