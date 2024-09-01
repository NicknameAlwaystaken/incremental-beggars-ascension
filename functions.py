from __future__ import annotations
from discord.ext import commands, tasks
from datetime import datetime
import discord

tree = None

MAX_MESSAGE_LENGTH = 2000

class Player:
    def __init__(self, player_id: str, display_name: str):
        self.player_id: str = player_id
        self.display_name = display_name
        self.materials = 0
        self.last_update = datetime.now()

    def update(self, current_time):
        time_difference = current_time - self.last_update
        self.materials += time_difference.total_seconds()
        self.last_update = datetime.now()

    def __str__(self):
        return f'Player: {self.display_name}\nCurrency: {self.materials:.2f}'


class IncrementalGameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players: dict[str, Player] = {}

    # Command to send a message with the button
    @commands.command(name='play')
    async def play(self, ctx):
        player = self.get_player(ctx.author.id)
        view = self.MyView(self, player_found=bool(player))
        if not player:
            await ctx.send(f"You aren't registered yet!", view=view)
        else:
            await ctx.send(player, view=view)

    def get_player(self, user_id: str):
        if user_id in self.players:
            player = self.players[user_id]
            player.update(datetime.now())
            return player
        return None

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
            player = self.cog.get_player(user.id)
            if player:
                player.update(datetime.now())
                await interaction.response.edit_message(content=player, view=self)

        async def register_callback(self, interaction: discord.Interaction):
            user = interaction.user
            # Register the player and update the message
            if user.id not in self.cog.players:
                self.cog.register_player(user.id, user.display_name)
                player = self.cog.get_player(user.id)
                self.clear_items()
                button = discord.ui.Button(label='Update', style=discord.ButtonStyle.primary)
                button.callback = self.update_callback
                self.add_item(button)
                await interaction.response.edit_message(content=player, view=self)
            else:
                message = f'{user.display_name} has already registered!'
                await interaction.response.edit_message(content=message, view=self)


    def update_player(self, player_id):
        if player_id in self.players:
            player = self.players[player_id]
            current_time = datetime.now()
            player.update(current_time)
            return True
        return False

    def register_player(self, player_id: str, display_name: str):
        self.players[player_id] = Player(player_id, display_name)


    @commands.command(name='register')
    async def register_command(self, ctx):
        self.register_player(ctx.author.id, ctx.author.display_name)
        await ctx.send(f"Welcome {ctx.author.display_name}, you have been registered!")

    @commands.command(name='materials')
    async def print_materials(self, ctx):
        user_id = ctx.author.id
        if not user_id in self.players:
            await ctx.send(f"You need to register first!")
            return

        player = self.players[user_id]
        self.update_player(user_id)
        await ctx.send(f"Player {ctx.author.display_name} - Materials: {player.materials:.2f}")


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

        if not self.countdown_seconds.is_running():
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


async def setup(bot):
    global tree
    tree = bot.tree

    await bot.add_cog(CountdownCog(bot))
    await bot.add_cog(IncrementalGameCog(bot))

