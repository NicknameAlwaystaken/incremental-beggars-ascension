from __future__ import annotations
from discord.ext import commands
from datetime import datetime
import discord
import aiosqlite
import math
import json
import os
import copy
from functools import partial

tree = None

DB_NAME = 'game.db'

game_data_folder = 'game_data'

MAX_MESSAGE_LENGTH = 2000

GAME_NAME = "Beggar's Ascension"

BASELINE_STATS = {
    'coins': {'amount': 0, 'gain': 0.5, 'capacity': 10, 'last_gained': 0, 'unlocked': True}
}


class Activity:
    def __init__(self, id, name) -> None:
        pass


class Currency:
    def __init__(self, id, name, capacity):
        self.id = id
        self.name = name
        self.amount = 0
        self.capacity = capacity
        self.last_gained = 0

    def __str__(self):
        return f"{self.name}: {format_number(self.amount)}/{format_number(self.capacity)} " \
            f"{f'(+{format_number(self.last_gained)})' if self.last_gained > 0 else ''}"


class Upgrade:
    def __init__(self, id, name, stat, modifier_type, modifier_value, cost_material, cost, max_purchases, unlocks_activity, description):
        self.id = id
        self.name = name
        self.stat = stat
        self.modifier_type = modifier_type
        self.modifier_value = modifier_value
        self.cost_material = cost_material
        self.cost = cost
        self.count = 1
        self.max_purchases = max_purchases
        self.unlocks_activity = unlocks_activity
        self.description = description

    def __str__(self):
        return f'{self.name if self.count == 1 else self.name + " x" + str(self.count)}'


class Player:
    def __init__(self, player_id: str, display_name: str):
        self.player_id: str = player_id
        self.title = 'Beggar'
        self.display_name = display_name
        self.currencies: dict[int, Currency] = {}
        self.upgrades: dict[int, Upgrade] = {}
        self.stat_modifiers: dict[str, dict[str, float]] = {}
        self.last_update_time = datetime.now()
        self.current_activity = None

    def buy_upgrade(self, upgrade: Upgrade):
        new_upgrade = copy.deepcopy(upgrade)
        material_type = new_upgrade.cost_material
        cost = new_upgrade.cost

        currency = next((c for c in self.currencies.values() if c.name == material_type), None)

        if currency and currency.amount >= cost:
            upgrade_added = self.add_upgrade(new_upgrade)
            if upgrade_added:
                currency.amount -= cost

    def add_currency(self, currency: Currency):
        currency_id = currency.id
        if currency_id not in self.currencies:
            self.currencies[currency_id] = currency

    def add_upgrade(self, upgrade: Upgrade) -> bool:
        upgrade_id = upgrade.id
        if upgrade_id in self.upgrades:
            if upgrade.max_purchases > self.upgrades[upgrade_id].count:
                self.upgrades[upgrade_id].count += 1
            else:
                return False
        else:
            self.upgrades[upgrade_id] = upgrade

        self.recalculate_stat_modifiers()
        return True

    def recalculate_stat_modifiers(self):

        self.stat_modifiers = {}

        for upgrade in self.upgrades.values():
            stat = upgrade.stat
            modifier_type = upgrade.modifier_type
            modifier_value = upgrade.modifier_value

            if stat:
                if stat not in self.stat_modifiers:
                    self.stat_modifiers[stat] = {'increase': 0, 'multiplier': 1.0}

                if modifier_type == 'multiplier':
                    self.stat_modifiers[stat]['multiplier'] *= modifier_value

                if modifier_type == 'increase':
                    self.stat_modifiers[stat]['increase'] += modifier_value

        self.update(datetime.now())

    def update(self, current_time):

        self.last_update_time = datetime.now()

    def __str__(self):

        upgrades = 'Upgrades: ' + ' ,'.join([str(upgrade) for upgrade in self.upgrades.values()]) + '\n'

        return f'{self.title}: {self.display_name}\n' + \
            f'{upgrades if self.upgrades else ''}'


class IncrementalGameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players: dict[str, Player] = {}
        self.upgrades: dict[int, Upgrade] = {}
        self.currencies: dict[int, Currency] = {}

    # Command to send a message with the button
    @commands.hybrid_command(name='play', with_app_command=True)
    async def play(self, ctx):
        """Interactive play command"""
        user_id = ctx.author.id
        player = await self.get_player(user_id)
        view = self.MyView(self, user_id)
        if not player:
            view.create_register_menu()
            await ctx.send(content="You have not registered yet!", view=view)
        else:
            view.create_main_menu()
            await ctx.send(content='', embed=self.player_stats_embed_message(player), view=view)

    class MyView(discord.ui.View):
        def __init__(self, cog, user_id):
            super().__init__(timeout=None)
            self.cog = cog
            self.user_id = user_id

        async def shop_menu_callback(self, interaction: discord.Interaction):
            user = interaction.user
            if user.id != self.user_id:
                return
            player = await self.cog.get_player(user.id)
            if player:
                self.create_shop_menu(player)
                await interaction.response.edit_message(content='', embed=self.cog.player_shop_embed_message(player), view=self)

        async def update_callback(self, interaction: discord.Interaction):
            user = interaction.user
            if user.id != self.user_id:
                return
            player = await self.cog.get_player(user.id)
            if player:
                player.update(datetime.now())

        async def main_menu_callback(self, interaction: discord.Interaction):
            user = interaction.user
            if user.id != self.user_id:
                return
            player = await self.cog.get_player(user.id)
            if player:
                self.create_main_menu()
                await interaction.response.edit_message(content='', embed=self.cog.player_stats_embed_message(player), view=self)
            else:
                self.create_register_menu()
                message = f"{user.display_name} to play you need to register first!"
                await interaction.response.edit_message(content=message, view=self)

        async def buy_upgrade_callback(self, interaction: discord.Interaction, upgrade: Upgrade):
            user = interaction.user
            if user.id != self.user_id:
                return
            player = await self.cog.get_player(user.id)

            if player:
                player.buy_upgrade(upgrade)
                self.create_shop_menu(player)
                await interaction.response.edit_message(content='', embed=self.cog.player_shop_embed_message(player), view=self)

        async def register_callback(self, interaction: discord.Interaction):
            user = interaction.user
            if user.id != self.user_id:
                return

            player = await self.cog.get_player(user.id)

            if not player:
                # Register the player and update the message
                await self.cog.register_player(user.id, user.display_name)
                player = await self.cog.get_player(user.id)
                self.create_main_menu()
                await interaction.response.edit_message(content='', embed=self.cog.player_stats_embed_message(player), view=self)

        def create_main_menu(self):
            self.clear_items()
            shop_button = discord.ui.Button(label='Shop', style=discord.ButtonStyle.primary)
            shop_button.callback = self.shop_menu_callback
            self.add_item(shop_button)

            update_button = discord.ui.Button(label='Update', style=discord.ButtonStyle.secondary, row=1)
            update_button.callback = self.main_menu_callback
            self.add_item(update_button)

        def create_shop_menu(self, player):
            self.clear_items()

            missing_upgrades = self.cog.get_missing_upgrades(player)

            for upgrade in missing_upgrades.values():
                if upgrade.max_purchases > 0:
                    buy_upgrade_button = discord.ui.Button(label=f'Buy {upgrade.name}', style=discord.ButtonStyle.success)
                    buy_upgrade_button.callback = partial(self.buy_upgrade_callback, upgrade=upgrade)
                    self.add_item(buy_upgrade_button)

            back_button = discord.ui.Button(label='Back', style=discord.ButtonStyle.danger)
            back_button.callback = self.main_menu_callback
            self.add_item(back_button)

            update_button = discord.ui.Button(label='Update', style=discord.ButtonStyle.secondary, row=1)
            update_button.callback = self.shop_menu_callback
            self.add_item(update_button)

        def create_register_menu(self):
            register_button = discord.ui.Button(label='Register', style=discord.ButtonStyle.success)
            register_button.callback = self.register_callback
            self.add_item(register_button)

    async def get_currencies_from_db(self):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('''
            SELECT currency_id, name, default_capacity
            FROM currencies''') as cursor:

                currencies = await cursor.fetchall()

                self.currencies = {}
                for currency in currencies:
                    self.currencies[currency[0]] = Currency(
                        currency[0], currency[1],
                        currency[2])

    async def get_upgrades_from_db(self):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('''
            SELECT upgrade_id, name, stat, modifier_type, modifier_value, cost_material, cost, max_purchases, unlocks_activity, description
            FROM upgrades''') as cursor:

                upgrades = await cursor.fetchall()

                self.upgrades = {}
                for upgrade in upgrades:
                    self.upgrades[upgrade[0]] = Upgrade(
                        upgrade[0], upgrade[1],
                        upgrade[2], upgrade[3],
                        upgrade[4], upgrade[5],
                        upgrade[6], upgrade[7],
                        upgrade[8], upgrade[9])

    async def get_player_currencies_from_db(self, player_id):
        await self.get_currencies_from_db()
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('''
            SELECT player_id, currency_id, amount
            FROM player_currencies
            WHERE player_id = ?''', (player_id,)) as cursor:

                player_currencies = await cursor.fetchall()

                for player_currency in player_currencies:
                    player_id, currency_id, amount = player_currency
                    player = self.players[player_id]
                    currency = self.currencies[currency_id]
                    currency.amount = amount
                    player.add_currency(currency)

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
                    player.add_upgrade(upgrade)

    async def get_player_from_db(self, player_id):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute('''
            SELECT player_id, player_display_name, current_activity, last_update_time
            FROM players
            WHERE player_id = ?''', (player_id,)) as cursor:

                found_player = await cursor.fetchone()

                if found_player:
                    player_id, display_name, current_activity, last_update_time = found_player
                    player = Player(player_id, display_name)
                    player.last_update_time = datetime.fromisoformat(last_update_time)
                    player.current_activity = current_activity
                    self.players[player_id] = player
                    await self.get_player_upgrades_from_db(player_id)
                    await self.get_player_currencies_from_db(player_id)
                    player.update(datetime.now())
                    return player
                else:
                    return None

    async def get_player(self, player_id: str):
        if player_id not in self.players:
            player = await self.get_player_from_db(player_id)
            if player:
                self.players[player_id] = player
                return player
            else:
                return None
        else:
            await self.player_to_database_update(player_id)
            return self.players[player_id]

    def update_player(self, player_id):
        if player_id in self.players:
            player = self.players[player_id]
            current_time = datetime.now()
            player.update(current_time)
            return True
        return False

    async def player_to_database_update(self, player_id):
        async with aiosqlite.connect(DB_NAME) as db:

            player = self.players[player_id]
            player_upgrades = [(id, upgrade.count) for id, upgrade in player.upgrades.items()]
            player_currencies = [(id, currency.amount) for id, currency in player.currencies.items()]

            placeholders_upgrades = ', '.join('?' for _ in player_upgrades)
            placeholders_currencies = ', '.join('?' for _ in player_currencies)

            await db.execute('BEGIN')

            # Clear all upgrades that player doesn't have anymore
            if player_upgrades:
                query = f"DELETE FROM player_upgrades WHERE player_id = ? AND upgrade_id NOT IN ({placeholders_upgrades})"

                params_upgrades = [player_id] + [upgrade[0] for upgrade in player_upgrades]

                await db.execute(query, params_upgrades)
            else:
                await db.execute("DELETE FROM player_upgrades WHERE player_id = ?", (player_id,))

            # Clear all upgrades that player doesn't have anymore
            if player_currencies:
                query = f"DELETE FROM player_currencies WHERE player_id = ? AND currency_id NOT IN ({placeholders_currencies})"

                params_currencies = [player_id] + [currency[0] for currency in player_currencies]

                await db.execute(query, params_currencies)
            else:
                await db.execute("DELETE FROM player_upgrades WHERE player_id = ?", (player_id,))

            # Add or update changed upgrades
            for player_upgrade in player_upgrades:
                await db.execute('''
                    INSERT OR REPLACE INTO player_upgrades (player_id, upgrade_id, count)
                    VALUES (?, ?, ?)
                ''', (player_id, player_upgrade[0], player_upgrade[1]))

            # Add or update changed currencies
            for player_currency in player_currencies:
                await db.execute('''
                    INSERT OR REPLACE INTO player_currencies (player_id, currency_id, amount)
                    VALUES (?, ?, ?)
                ''', (player_id, player_currency[0], player_currency[1]))

            # Check if the player exists in the database
            async with db.execute('SELECT 1 FROM players WHERE player_id = ?', (player_id,)) as cursor:
                found_player = await cursor.fetchone()

            player.update(datetime.now())

            if found_player:
                await db.execute('''
                UPDATE players
                SET player_display_name = ?, current_activity = ?, last_update_time = ?
                WHERE player_id == ?
                ''', (player.display_name, player.current_activity, player.last_update_time, player_id))
            else:
                await db.execute('''
                INSERT INTO players (player_id, player_display_name, current_activity, last_update_time)
                VALUES (?, ?, ?, ?)
                ''', (player_id, player.display_name, player.current_activity, player.last_update_time))

            await db.commit()

    async def register_player(self, player_id: str, display_name: str):
        new_player = Player(player_id, display_name)
        new_player.add_currency(self.currencies[0])
        self.players[player_id] = new_player

        await self.player_to_database_update(player_id)

    def player_stats_embed_message(self, player):
        embed = discord.Embed(
            title="🎩 Player Status",
            description=f"**{player.title}**: __{player.display_name}__",
            color=discord.Color.green()
        )
        formatted_currencies = []
        for currency in player.currencies.values():
            formatted_currencies.append(f"{currency.name.capitalize()}: {format_number(currency.amount)}/{format_number(currency.capacity)} (+{format_number(currency.last_gained)})")

        embed.add_field(name="💰 Currencies", value='\n'.join(formatted_currencies), inline=False)

        if player.upgrades:
            embed.add_field(name="🛠️ Upgrades", value=', '.join([str(upgrade) for upgrade in player.upgrades.values()]), inline=False)

        return embed

    def player_shop_embed_message(self, player):
        embed = discord.Embed(
            title="🛒 Upgrade shop",
            description=f"**{player.title}**: __{player.display_name}__",
            color=discord.Color.green()
        )
        formatted_currencies = []
        for currency in player.currencies.values():
            formatted_currencies.append(f"{currency.name.capitalize()}: {format_number(currency.amount)}/{format_number(currency.capacity)} (+{format_number(currency.last_gained)})")

        embed.add_field(name="💰 Currencies", value='\n'.join(formatted_currencies), inline=False)

        missing_upgrades = self.get_missing_upgrades(player)

        if missing_upgrades:
            embed.add_field(
                name="🛠️ Buyable Upgrades",
                value='\n\n'.join([
                    f"**{upgrade.name}**\n"
                    f"• Cost: `{upgrade.cost} {upgrade.cost_material}{'s' if upgrade.cost > 1 else ''}`\n"
                    f"• Remaining: `{upgrade.max_purchases}`\n"
                    f"• Effect: {self.format_upgrade_text(upgrade)}"
                    for upgrade in missing_upgrades.values()
                ]),
                inline=False
            )
        else:
            embed.add_field(
                name="🛠️ Buyable items",
                value='No more available upgrades to buy.',
                inline=False)

        return embed

    def format_upgrade_text(self, upgrade: Upgrade):
        material_type, material_modifier = upgrade.stat.split('.')
        amount = upgrade.modifier_value
        modifier_type = upgrade.modifier_type

        modifier_text = material_modifier
        modifier_type_text = modifier_type

        if material_modifier == "capacity":
            modifier_text = 'max capacity'

        return f'{modifier_type_text} {material_type.capitalize()} {modifier_text} by {format_number(amount)}'

    def get_missing_upgrades(self, player):
        missing_upgrades = {}
        upgrades_list = copy.deepcopy(self.upgrades)
        for id, upgrade in upgrades_list.items():
            if id in player.upgrades:
                upgrades_left = upgrade.max_purchases - player.upgrades[id].count
            else:
                upgrades_left = upgrade.max_purchases

            if upgrades_left > 0:
                upgrade.max_purchases = upgrades_left
                missing_upgrades[id] = upgrade
            else:
                if id in missing_upgrades:
                    del missing_upgrades[id]

        return missing_upgrades


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
            PRIMARY KEY (player_id, upgrade_id),
            FOREIGN KEY (upgrade_id) REFERENCES upgrades(upgrade_id)
        )
        ''')
        await db.commit()


async def create_upgrades_table(database_name):
    async with aiosqlite.connect(database_name) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS upgrades (
            upgrade_id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            stat TEXT,
            modifier_type TEXT,
            modifier_value INTEGER,
            cost_material TEXT,
            cost INTEGER,
            max_purchases INTEGER,
            unlocks_activity TEXT,
            description TEXT
        )
        ''')
        await db.commit()


async def create_player_currencies_table(database_name):
    async with aiosqlite.connect(database_name) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS player_currencies (
            player_id INTEGER NOT NULL,
            currency_id INTEGER NOT NULL,
            amount DOUBLE NOT NULL DEFAULT 0,
            PRIMARY KEY (player_id, currency_id),
            FOREIGN KEY (currency_id) REFERENCES currencies(currency_id)
        )
        ''')
        await db.commit()


async def create_currencies_table(database_name):
    async with aiosqlite.connect(database_name) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS currencies (
            currency_id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            default_capacity INTEGER
        )
        ''')
        await db.commit()


async def create_items_table(database_name):
    async with aiosqlite.connect(database_name) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS items (
            item_id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS attributes (
            attribute_id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS item_attributes (
            item_id INTEGER NOT NULL,
            attribute_id INTEGER NOT NULL,
            value DOUBLE NOT NULL,
            PRIMARY KEY (item_id, attribute_id),
            FOREIGN KEY (item_id) REFERENCES items(item_id),
            FOREIGN KEY (attribute_id) REFERENCES attributes(attribute_id)
        )
        ''')
        await db.commit()


async def create_player_items_table(database_name):
    async with aiosqlite.connect(database_name) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS player_items (
            player_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (player_id, upgrade_id),
            FOREIGN KEY (item_id) REFERENCES ITEMS(item_id)
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
                current_activity TEXT,
                last_update_time TEXT
            )
        ''')
        await db.commit()


async def update_currencies_from_json_to_db(database_name):
    with open(os.path.join(game_data_folder, 'currencies.json')) as file:
        currencies = json.load(file)

    async with aiosqlite.connect(database_name) as db:
        for currency in currencies:
            await db.execute('''
                INSERT OR IGNORE INTO currencies (currency_id, name, default_capacity)
                VALUES (?, ?, ?)
            ''', (currency['id'], currency['name'], currency['capacity']))

        await db.commit()


# async def update_items_from_json_to_db(database_name):
#     with open(os.path.join(game_data_folder, 'items.json')) as file:
#         items = json.load(file)
#
#     async with aiosqlite.connect(database_name) as db:
#         for item in items:
#             item_name = item['name']
#             await db.execute('''
#                 INSERT OR IGNORE INTO items (name, default_amount, default_capacity, default_gain)
#                 VALUES (?, ?, ?, ?)
#             ''', (item_name))
#
#         await db.commit()


async def update_upgrades_from_json_to_db(database_name):
    with open(os.path.join(game_data_folder, 'upgrades.json')) as file:
        upgrades = json.load(file)

    async with aiosqlite.connect(database_name) as db:
        for upgrade in upgrades:
            await db.execute('''
                INSERT OR REPLACE INTO upgrades (upgrade_id, name, stat,
                modifier_type, modifier_value,
                cost_material, cost, max_purchases,
                unlocks_activity, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (upgrade['id'], upgrade['name'], upgrade['stat'],
                  upgrade['modifier_type'], upgrade['modifier_value'],
                  upgrade['cost_material'], upgrade['cost'], upgrade['max_purchases'],
                  upgrade['unlocks_activity'], upgrade['description']))
            await db.commit()


async def setup(bot):
    global tree
    tree = bot.tree
    bot.add_command(tree_sync)

    # create table if not exist
    await create_players_table(DB_NAME)

    await create_items_table(DB_NAME)
    # await update_items_from_json_to_db(DB_NAME)
    # await create_player_items_table(DB_NAME)

    await create_currencies_table(DB_NAME)
    await update_currencies_from_json_to_db(DB_NAME)
    await create_player_currencies_table(DB_NAME)

    await create_upgrades_table(DB_NAME)
    await update_upgrades_from_json_to_db(DB_NAME)
    await create_player_upgrades_table(DB_NAME)

    game_cog = IncrementalGameCog(bot)
    await bot.add_cog(game_cog)
    await game_cog.get_currencies_from_db()
    await game_cog.get_upgrades_from_db()
