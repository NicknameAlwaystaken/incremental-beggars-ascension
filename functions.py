from __future__ import annotations
from discord.ext import commands
from datetime import datetime
import discord
import aiosqlite
import math
import json
import os
import copy

tree = None

DB_NAME = 'game.db'

game_data_folder = 'game_data'

MAX_MESSAGE_LENGTH = 2000

GAME_NAME = "Beggar's Ascension"

BASELINE_STATS = {
    'material': {'amount': 0, 'gain': 0.5, 'capacity': 10, 'last_gained': 0}
}

UPGRADE_CAPS = {
    'Pouch': 3
}


class Upgrade:
    def __init__(self, name, stat, modifier_type, value, cost):
        self.name = name
        self.stat = stat
        self.modifier_type = modifier_type
        self.value = value
        self.cost = cost
        self.count = 1

    def apply(self, player_stats):
        keys = self.stat.split('.')
        target = player_stats

        for key in keys[:-1]:
            target = target[key]

        if self.modifier_type == 'add':
            target[keys[-1]] += self.value * self.count
        elif self.modifier_type == 'multiply':
            target[keys[-1]] *= self.value * self.count

    def __str__(self):
        return f'{self.name if self.count == 1 else self.name + " x" + str(self.count)}'


class Player:
    def __init__(self, player_id: str, display_name: str):
        self.player_id: str = player_id
        self.title = 'Beggar'
        self.display_name = display_name
        self.stats = copy.deepcopy(BASELINE_STATS)
        self.upgrades: dict[str, Upgrade] = {}
        self.last_update = datetime.now()

    def add_upgrade(self, upgrade_id, upgrade: Upgrade):
        if upgrade_id in self.upgrades:
            if upgrade.name in UPGRADE_CAPS and UPGRADE_CAPS[upgrade.name] > self.upgrades[upgrade_id].count:
                self.upgrades[upgrade_id].count += 1
        else:
            self.upgrades[upgrade_id] = upgrade

        self.update_upgrades()

    def update_upgrades(self):
        current_material_amount = self.stats['material']['amount']
        self.stats = copy.deepcopy(BASELINE_STATS)
        self.stats['material']['amount'] = current_material_amount

        for upgrade in self.upgrades.values():
            upgrade.apply(self.stats)

        self.update(datetime.now())

    def update(self, current_time):
        time_difference = current_time - self.last_update
        material = self.stats["material"]
        max_gain = (material["gain"] * time_difference.total_seconds())
        new_amount = min(material["amount"] + max_gain, material["capacity"])
        material["last_gained"] = new_amount - material["amount"]
        material["amount"] = new_amount
        self.last_update = datetime.now()

    def __str__(self):
        material = self.stats["material"]
        material_last_gained = material["last_gained"]
        material_message = f'Currency: {format_number(material["amount"])}' + \
            f'/{format_number(material["capacity"])}' + \
            f'{f" +{format_number(material_last_gained)}\n" if material_last_gained > 0 else "\n"}'

        upgrades = 'Upgrades: ' + ' ,'.join([str(upgrade) for upgrade in self.upgrades.values()]) + '\n'

        return f'{self.title}: {self.display_name}\n' + \
            f'{material_message}{upgrades if self.upgrades else ''}'


class IncrementalGameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players: dict[str, Player] = {}
        self.upgrades: dict[int, Upgrade] = {}

    # Delete this after testing
    @commands.command(name='pouch')
    async def get_pouch(self, ctx):
        """Get free pouch, should be deleted after testing"""
        player = await self.get_player(ctx.author.id)
        if player:
            upgrade_id, upgrade = [(id, upgrade) for id, upgrade in self.upgrades.items() if upgrade.name == 'Pouch'][0]
            player.add_upgrade(upgrade_id, upgrade)

    # Command to send a message with the button
    @commands.hybrid_command(name='play', with_app_command=True)
    async def play(self, ctx):
        """Interactive play command"""
        player = await self.get_player(ctx.author.id)
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

    async def get_upgrades_from_db(self):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('''
            SELECT id, name, stat, modifier_type, value, cost
            FROM upgrades''') as cursor:

                upgrades = await cursor.fetchall()

                self.upgrades = {}
                for upgrade in upgrades:
                    self.upgrades[upgrade[0]] = Upgrade(
                        upgrade[1], upgrade[2],
                        upgrade[3], upgrade[4],
                        upgrade[5])

    async def get_player_upgrades_from_db(self, player_id):
        await self.get_upgrades_from_db()
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('''
            SELECT player_id, upgrade_id, count
            FROM player_upgrades
            WHERE player_id = ?''', (player_id,)) as cursor:

                player_upgrades = await cursor.fetchall()

                for player_upgrade in player_upgrades:
                    player_id, upgrade_id, count = player_upgrade
                    player = self.players[player_id]
                    upgrade = self.upgrades[upgrade_id]
                    upgrade.count = count
                    player.add_upgrade(upgrade_id, upgrade)

    async def get_player_from_db(self, player_id):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('''
            SELECT player_id, player_display_name, materials, last_update_time
            FROM players
            WHERE player_id = ?''', (player_id,)) as cursor:

                found_player = await cursor.fetchone()

                if found_player:
                    player_id, display_name, materials, last_update_time = found_player
                    player = Player(player_id, display_name)
                    player.stats['material']["amount"] = materials
                    player.last_update = datetime.fromisoformat(last_update_time)
                    self.players[player_id] = player
                    await self.get_player_upgrades_from_db(player_id)
                    player.update(datetime.now())
                    return player
                else:
                    return None

    async def get_player(self, player_id: str):
        if player_id not in self.players:
            player = await self.get_player_from_db(player_id)
            return player
        else:
            await self.player_database_update(player_id)
            player = self.players[player_id]
            return player

    def update_player(self, player_id):
        if player_id in self.players:
            player = self.players[player_id]
            current_time = datetime.now()
            player.update(current_time)
            return True
        return False

    async def player_database_update(self, player_id):
        async with aiosqlite.connect(DB_NAME) as db:

            player_upgrades = [(id, upgrade.count) for id, upgrade in self.players[player_id].upgrades.items()]

            placeholders = ', '.join('?' for _ in player_upgrades)

            await db.execute('BEGIN')

            # Clear all upgrades that player doesn't have anymore
            if player_upgrades:
                query = f"DELETE FROM player_upgrades WHERE player_id = ? AND upgrade_id NOT IN ({placeholders})"

                params = [player_id] + [upgrade[0] for upgrade in player_upgrades]

                await db.execute(query, params)
            else:
                await db.execute("DELETE FROM player_upgrades WHERE player_id = ?", (player_id,))

            # Add or update changed upgrades
            for player_upgrade in player_upgrades:
                await db.execute('''
                    INSERT OR REPLACE INTO player_upgrades (player_id, upgrade_id, count)
                    VALUES (?, ?, ?)''',
                    (player_id, player_upgrade[0], player_upgrade[1]))

            async with db.execute('SELECT 1 FROM players WHERE player_id = ?', (player_id,)) as cursor:

                found_player = await cursor.fetchone()

                player = self.players[player_id]

                player.update(datetime.now())

                if found_player:
                    await db.execute('''
                    UPDATE players
                    SET materials = ?
                    WHERE player_id == ?
                    ''', (player.stats['material']["amount"], player.player_id))
                else:
                    await db.execute('''
                    INSERT INTO players (player_id, player_display_name, materials, last_update_time)
                    VALUES (?, ?, ?, ?)
                    ''', (player.player_id, player.display_name, player.stats['material']["amount"], player.last_update))

            await db.commit()

    async def register_player(self, player_id: str, display_name: str):

        self.players[player_id] = Player(player_id, display_name)
        await self.player_database_update(player_id)


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

    if number < 1:
        return f"{number:.2f}"

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


async def create_player_upgrades_table(database_name):
    async with aiosqlite.connect(database_name) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS player_upgrades (
            player_id INTEGER NOT NULL,
            upgrade_id INTEGER NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (player_id, upgrade_id)
        )
        ''')
        await db.commit()


async def create_upgrades_table(database_name):
    async with aiosqlite.connect(database_name) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS upgrades (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            stat TEXT,
            modifier_type TEXT,
            value INTEGER,
            cost INTEGER
        )
        ''')
        await db.commit()


async def create_players_table(database_name):
    async with aiosqlite.connect(database_name) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS players (
            player_id INTEGER PRIMARY KEY,
            player_display_name TEXT NOT NULL,
            materials DOUBLE,
            last_update_time TEXT
        )
        ''')
        await db.commit()


async def update_upgrades(database_name):
    with open(os.path.join(game_data_folder, 'upgrades.json')) as file:
        upgrades = json.load(file)

    async with aiosqlite.connect(database_name) as db:
        for upgrade in upgrades:
            await db.execute('''
                INSERT OR REPLACE INTO upgrades (id, name, stat, modifier_type, value, cost)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (upgrade['id'], upgrade['name'], upgrade['stat'], upgrade['modifier_type'], upgrade['value'], upgrade['cost']))
            await db.commit()


async def setup(bot):
    global tree
    tree = bot.tree
    bot.add_command(tree_sync)

    # create table if not exist
    await create_players_table(DB_NAME)
    await create_upgrades_table(DB_NAME)
    await update_upgrades(DB_NAME)
    await create_player_upgrades_table(DB_NAME)

    game_cog = IncrementalGameCog(bot)
    await bot.add_cog(game_cog)
    await game_cog.get_upgrades_from_db()
