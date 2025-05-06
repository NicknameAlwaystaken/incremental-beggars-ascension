import os
import sys
from dotenv import load_dotenv
import discord
from discord.ext import commands
import asyncio


# Load the .env file
_ = load_dotenv()

testing = True

# Get the token from the .env file
if testing:
    TOKEN = os.getenv("DISCORD_TOKEN_TEST")
else:
    TOKEN = os.getenv("DISCORD_TOKEN_STABLE")

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
