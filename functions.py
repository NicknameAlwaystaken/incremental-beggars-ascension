from __future__ import annotations
from discord.ext import commands, tasks
from datetime import datetime
import discord
import aiosqlite
import math

tree = None

DB_NAME = 'game.db'

MAX_MESSAGE_LENGTH = 2000

GAME_NAME = "Beggar's Ascension"


class Player:
    def __init__(self, player_id: str, display_name: str):
        self.player_id: str = player_id
        self.title = 'Beggar'
        self.display_name = display_name
        self.materials = 0
        self.last_update = datetime.now()

    def update(self, current_time):
        time_difference = current_time - self.last_update
        self.materials += time_difference.total_seconds()
        self.last_update = datetime.now()

    def __str__(self):
        return f'{self.title}: {self.display_name} ' + \
            f'Currency: {format_number(self.materials)}'


class IncrementalGameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players: dict[str, Player] = {}

    # Command to send a message with the button
    @commands.hybrid_command(name='play', with_app_command=True)
    async def play(self, ctx):
        f"""This command allows you to play {GAME_NAME}"""
        player = await self.get_player(ctx.author.id)
        print(player)
        view = self.MyView(self, player_found=bool(player))
        if not player:
            await ctx.send("You aren't registered yet!", view=view)
        else:
            await ctx.send(player, view=view)

    class MyView(discord.ui.View):
        def __init__(self, cog, player_found: bool):
            super().__init__(timeout=None)
            self.cog = cog

            if player_found:
                button = discord.ui.Button(label='Update', style=discord.ButtonStyle.primary)
                button.callback = self.update_callback
                self.add_item(button)
            else:
                button = discord.ui.Button(label='Register', style=discord.ButtonStyle.success)
                button.callback = self.register_callback
                self.add_item(button)

        async def update_callback(self, interaction: discord.Interaction):
            user = interaction.user
            player = await self.cog.get_player(user.id)
            if player:
                await interaction.response.edit_message(content=player, view=self)
            else:
                self.clear_items()
                button = discord.ui.Button(label='Register', style=discord.ButtonStyle.success)
                button.callback = self.register_callback
                self.add_item(button)
                message = f"{user.display_name} to play you need to register first!"
                await interaction.response.edit_message(content=message, view=self)

        async def register_callback(self, interaction: discord.Interaction):
            user = interaction.user
            # Register the player and update the message
            if not await self.cog.get_player(user.id):
                await self.cog.register_player(user.id, user.display_name)
                player = await self.cog.get_player(user.id)
                self.clear_items()
                button = discord.ui.Button(label='Update', style=discord.ButtonStyle.primary)
                button.callback = self.update_callback
                self.add_item(button)
                await interaction.response.edit_message(content=player, view=self)
            else:
                message = f'{user.display_name} has already registered!'
                await interaction.response.edit_message(content=message, view=self)

    async def get_player_from_db(self, player_id):

        async with aiosqlite.connect(DB_NAME) as db:

            async with db.execute('''
            SELECT player_id, player_display_name, materials, last_update_time
            FROM users
            WHERE player_id = ?''', (player_id,)) as cursor:

                found_player = await cursor.fetchone()

                if found_player:
                    player_id, display_name, materials, last_update_time = found_player
                    player = Player(player_id, display_name)
                    player.materials = materials
                    player.last_update = datetime.fromisoformat(last_update_time)
                    player.update(datetime.now())
                    self.players[player_id] = player
                    return player
                else:
                    return None

    async def get_player(self, player_id: str):
        if player_id not in self.players:
            player = await self.get_player_from_db(player_id)
            return player
        else:
            await self.update_database(player_id)
            player = self.players[player_id]
            return player

    def update_player(self, player_id):
        if player_id in self.players:
            player = self.players[player_id]
            current_time = datetime.now()
            player.update(current_time)
            return True
        return False

    async def update_database(self, player_id):
        async with aiosqlite.connect(DB_NAME) as db:

            async with db.execute('SELECT 1 FROM users WHERE player_id = ?', (player_id,)) as cursor:

                found_player = await cursor.fetchone()

                player = self.players[player_id]

                player.update(datetime.now())

                if found_player:
                    await db.execute('''
                    UPDATE users
                    SET materials = ?
                    WHERE player_id == ?
                    ''', (player.materials, player.player_id))
                else:
                    await db.execute('''
                    INSERT INTO users (player_id, player_display_name, materials, last_update_time)
                    VALUES (?, ?, ?, ?)
                    ''', (player.player_id, player.display_name, player.materials, player.last_update))

                await db.commit()

    async def register_player(self, player_id: str, display_name: str):

        self.players[player_id] = Player(player_id, display_name)
        await self.update_database(player_id)


class CountdownCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.countdown_time = 0
        self.channel = None

    @tasks.loop(seconds=1)
    async def countdown_seconds(self):
        if self.countdown_time > 0:
            self.countdown_time -= 1
            if self.channel:
                await self.channel.send(f"{self.countdown_time}")
        else:
            if self.channel:
                await self.channel.send('Countdown finished!')
            self.countdown_seconds.stop()

    @commands.command(name='start')
    async def start_countdown(self, ctx, *args):
        if not args:
            await ctx.send("You didn't give me a time value!")
            return

        seconds = args[0]

        if not seconds.isdigit():
            await ctx.send("Give me a valid number!")
            return

        if not self.countdown_seconds.is_running():  # type: ignore
            self.channel = ctx.channel
            self.countdown_time = int(seconds)
            self.countdown_seconds.start()
            await ctx.send(f'Countdown {seconds} seconds')
        else:
            await ctx.send('Countdown is already running!')

    @commands.command(name='stop')
    async def stop_countdown(self, ctx):
        if self.countdown_seconds.is_running():
            self.countdown_seconds.stop()
            self.countdown_time = 0
            await ctx.send("Countdown stopped!")
        else:
            await ctx.send("Countdown isn't running!")


@commands.command(name='sync')
async def tree_sync(ctx):
    global tree
    await tree.sync()  # type: ignore
    print("Tree is synchronized")


def format_number(number, sig_figs=3):
    prefixes = {
        0: '',
        3: 'K',
        6: 'M',
        9: 'B',
        12: 'T',
    }
    if number == 0:
        return "0"

    # Determine exponent and adjusted value
    exponent = int(math.floor(math.log10(abs(number)) / 3) * 3)
    value = number / (10 ** exponent)

    # Format the value with the specified significant figures
    format_string = "{:." + str(sig_figs - 1) + "f}"
    value_str = format_string.format(value).rstrip('0').rstrip('.')

    # Get the large number name
    prefix = prefixes.get(exponent, f"e{exponent}")

    if prefix:
        return f"{value_str}{prefix}"
    else:
        return value_str


async def create_table(database_name):
    async with aiosqlite.connect(database_name) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            player_id INTEGER PRIMARY KEY,
            player_display_name TEXT NOT NULL,
            materials DOUBLE,
            last_update_time TEXT
        )
        ''')
        await db.commit()


async def setup(bot):
    global tree
    tree = bot.tree
    bot.add_command(tree_sync)

    await create_table(DB_NAME)

    await bot.add_cog(CountdownCog(bot))
    await bot.add_cog(IncrementalGameCog(bot))
