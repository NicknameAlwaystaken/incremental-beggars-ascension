import os
import sys
from dotenv import load_dotenv
import discord
from discord.ext import commands
import asyncio


# Load the .env file
_ = load_dotenv()

mode = sys.argv[1] if len(sys.argv) > 1 else "test"

if mode == "test":
    TOKEN = os.getenv("DISCORD_TOKEN_TEST")
    print("Launching Test Bot")
elif mode == "stable":
    print("Launching Stable Bot")
    TOKEN = os.getenv("DISCORD_TOKEN_STABLE")
else:
    raise ValueError("Invalid mode. Use 'test' or 'stable'.")

if TOKEN is None:
    print("Token not found. Exiting.")
    sys.exit(1)

# Set the prefix for the bot commands
prefix = '!'

# Set the intents for the bot
# Intents are used to determine what the bot can see and do
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


# Create the bot
bot: commands.Bot = commands.Bot(command_prefix=prefix, intents=intents)

# Load the cogs
# asyncio.run(bot.load_extension("server_setup"))
asyncio.run(bot.load_extension("functions"))

# Run the bot
bot.run(TOKEN)
