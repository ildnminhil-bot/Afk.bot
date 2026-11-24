import os
import threading
import discord
from discord.ext import commands
from flask import Flask

# --- 1. Web server nhỏ để Render Web Service bind PORT ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Discord AFK Bot is running!", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- 2. Cấu hình Discord Bot ---
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Lưu trạng thái AFK: {user_id: {"reason": str}}
afk_users = {}

@bot.event
async def on_ready():
    print(f"[OK] Bot đã đăng nhập: {bot.user} (ID: {bot.user.id})")

@bot.command(name="afk")
async def afk_cmd(ctx, *, reason: str = "Đang AFK"):
    afk_users[ctx.author.id] = {"reason": reason}
    await ctx.send(f"💤 **{ctx.author.display_name}** đã bật AFK: *{reason}*")

@bot.command(name="joinvoice")
async def join_voice(ctx):
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("❌ Bạn cần vào một kênh thoại trước.")
        return
    channel = ctx.author.voice.channel
    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()
    await ctx.send(f"🔊 Đã vào kênh thoại **{channel.name}**.")

@bot.command(name="leavevoice")
async def leave_voice(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Đã rời kênh thoại.")
    else:
        await ctx.send("❌ Bot hiện không ở trong kênh thoại nào.")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Nếu người đang AFK nhắn tin (trừ lệnh !afk) -> gỡ AFK
    if message.author.id in afk_users and not message.content.startswith("!afk"):
        afk_users.pop(message.author.id, None)
        await message.channel.send(f"☀️ Chào mừng **{message.author.display_name}** quay lại! Đã tắt chế độ AFK.")

    # Nếu tin nhắn nhắc đến người đang AFK
    for mentioned in message.mentions:
        if mentioned.id in afk_users and mentioned.id != message.author.id:
            reason = afk_users[mentioned.id]["reason"]
            await message.channel.send(f"💤 **{mentioned.display_name}** hiện đang AFK: *{reason}*")

    await bot.process_commands(message)

if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("Thiếu biến môi trường DISCORD_TOKEN!")

    threading.Thread(target=run_web, daemon=True).start()
    bot.run(token)
