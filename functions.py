from __future__ import annotations
from discord.ext import commands
from datetime import datetime
import discord
import aiosqlite
import math
import json
import os
import copy
from views import ShopMenuView, MainMenuView, ActivitiesMenuView
from typing import Optional

tree = None

game_data_folder = 'game_data'

GAME_DB_LOCATION = os.path.join(game_data_folder, 'game.db')

MAX_MESSAGE_LENGTH = 2000

GAME_NAME = "Beggar's Ascension"


class Activity:
    def __init__(self, id, name, activity_type, output_item, output_amount, duration_seconds, unlock_conditions, description, status_description):
        self.id = id
        self.name = name
        self.activity_type = activity_type
        self.output_item = output_item
        self.output_amount = output_amount
        self.duration_seconds = duration_seconds
        self.unlock_conditions = unlock_conditions
        self.description = description
        self.status_description = status_description

    def __str__(self):
        return f'{self.description}'


class Currency:
    def __init__(self, id, name, capacity):
        self.id = id
        self.name = name
        self.amount = 0
        self.capacity = capacity
        self.base_capacity = capacity
        self.last_gained = 0

    def add_amount(self, amount: float):
        current_amount = self.amount
        self.amount += amount
        self.amount = min(self.amount, self.capacity)
        self.last_gained = self.amount - current_amount

    def __str__(self):
        return f"{self.name}: {format_number(self.amount)}/{format_number(self.capacity)} " \
            f"{f'(+{format_number(self.last_gained)})' if self.last_gained > 0 else ''}"


class Upgrade:
    def __init__(self, id, name, stat, modifier_type, modifier_value, cost_material, cost, max_purchases, description):
        self.id = id
        self.name = name
        self.stat = stat
        self.modifier_type = modifier_type
        self.modifier_value = modifier_value
        self.cost_material = cost_material
        self.cost = cost
        self.count = 1
        self.max_purchases = max_purchases
        self.unlocks = []
        self.description = description

    def __str__(self):
        return f'{self.name if self.count == 1 else self.name + " x" + str(self.count)}'


class Player:
    def __init__(self, player_id: str, display_name: str):
        self.id: str = player_id
        self.title = 'Beggar'
        self.display_name = display_name
        self.currencies: dict[int, Currency] = {}
        self.upgrades: dict[int,  Upgrade] = {}
        self.stat_modifiers: dict[str, dict[str, float]] = {}
        self.unlock_conditions = []
        self.last_update_time = datetime.now()
        self.current_activity: Optional[Activity] = None

    def buy_upgrade(self, upgrade:  Upgrade):
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

        self.apply_currency_modifiers()

    def add_upgrade(self, upgrade:  Upgrade, count=1) -> bool:
        new_upgrade = upgrade
        upgrade_id = new_upgrade.id
        if upgrade_id in self.upgrades:
            if new_upgrade.max_purchases >= self.upgrades[upgrade_id].count + count:
                self.upgrades[upgrade_id].count += count
            else:
                return False
        else:
            new_upgrade.count = count
            self.upgrades[upgrade_id] = new_upgrade

        self.recalculate_stat_modifiers()
        self.update_unlock_conditions()
        return True

    def update_unlock_conditions(self):
        self.unlock_conditions = []

        for upgrade in self.upgrades.values():
            if upgrade.unlocks:
                self.unlock_conditions.extend(upgrade.unlocks)

    def recalculate_stat_modifiers(self):

        self.stat_modifiers = {}

        for upgrade in self.upgrades.values():
            stat = upgrade.stat
            modifier_type = upgrade.modifier_type
            modifier_value = upgrade.modifier_value

            if stat:
                for _ in range(upgrade.count):
                    if stat not in self.stat_modifiers:
                        self.stat_modifiers[stat] = {'increase': 0, 'multiplier': 1.0}

                    if modifier_type == 'multiplier':
                        self.stat_modifiers[stat]['multiplier'] *= modifier_value

                    if modifier_type == 'increase':
                        self.stat_modifiers[stat]['increase'] += modifier_value

        self.apply_currency_modifiers()

    def apply_currency_modifiers(self):
        for currency in self.currencies.values():
            if currency.name == 'coins':
                capacity_modifiers = self.stat_modifiers.get('coins.capacity', {'increase': 0, 'multiplier': 1.0})

                new_capacity = (currency.base_capacity + capacity_modifiers['increase']) * capacity_modifiers['multiplier']

                currency.capacity = new_capacity

    def change_activity(self, activity: Activity):
        self.update(datetime.now())

        self.current_activity = activity

    def update(self, current_time):
        if self.current_activity:
            current_activity = self.current_activity

            output_amount = current_activity.output_amount
            duration_seconds = current_activity.duration_seconds

            time_difference = (current_time - self.last_update_time).total_seconds()
            amount_to_add = (output_amount / duration_seconds) * time_difference

            player_currency = self.currencies[0]
            if player_currency.name in self.stat_modifiers:
                currency_modifier = self.stat_modifiers[player_currency.name]
                amount_to_add *= currency_modifier['multiplier']

            player_currency.add_amount(amount_to_add)

        self.last_update_time = current_time

    def __str__(self):

        upgrades = 'Upgrades: ' + ' ,'.join([str(upgrade) for upgrade in self.upgrades.values()]) + '\n'

        return f'{self.title}: {self.display_name}\n' + \
            f'{upgrades if self.upgrades else ''}'


class IncrementalGameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players: dict[str, Player] = {}
        self.upgrades: dict[int,  Upgrade] = {}
        self.activities: dict[int, Activity] = {}
        self.currencies: dict[int, Currency] = {}
        self.views: dict[int, discord.ui.View] = {}

    # Command to send a message with the button
    @commands.hybrid_command(name='play', with_app_command=True)
    async def play(self, ctx):
        """Interactive play command"""
        user_id = ctx.author.id
        player = await self.get_player(user_id)

        if not player:
            view = MainMenuView(self, user_id)
            view.create_register_menu()
            message = await ctx.send(content="You have not registered yet!", view=view)
            self.views[message.id] = view
        else:
            view = MainMenuView(self, user_id)
            message = await ctx.send(content='', embed=self.player_stats_embed_message(player), view=view)
            self.views[message.id] = view

    async def shop_menu_callback(self, interaction: discord.Interaction):
        user = interaction.user
        if not await self._is_valid_interaction(interaction):
            return

        player = await self.get_player(str(user.id))
        if player:
            await self.update_player(player)
            view = ShopMenuView(self, user.id, player)
            await interaction.response.edit_message(content='', embed=self.player_shop_embed_message(player), view=view)

    async def update_callback(self, interaction: discord.Interaction):
        user = interaction.user
        if not await self._is_valid_interaction(interaction):
            return

        player = await self.get_player(str(user.id))
        if player:
            await self.update_player(player)

    async def main_menu_callback(self, interaction: discord.Interaction):
        user = interaction.user
        if not await self._is_valid_interaction(interaction):
            return

        player = await self.get_player(str(user.id))
        if player:
            await self.update_player(player)
            view = MainMenuView(self, user.id)
            await interaction.response.edit_message(content='', embed=self.player_stats_embed_message(player), view=view)

    async def activities_menu_callback(self, interaction: discord.Interaction):
        user = interaction.user
        if not await self._is_valid_interaction(interaction):
            return

        player = await self.get_player(str(user.id))
        if player:
            await self.update_player(player)
            view = ActivitiesMenuView(self, user.id, player)
            await interaction.response.edit_message(content='', embed=self.player_activities_embed_message(player), view=view)

    async def buy_upgrade_callback(self, interaction: discord.Interaction, upgrade:  Upgrade):
        user = interaction.user
        if not await self._is_valid_interaction(interaction):
            return

        player = await self.get_player(str(user.id))

        if player:
            player.buy_upgrade(upgrade)
            await self.update_player(player)
            view = ShopMenuView(self, user.id, player)
            await interaction.response.edit_message(content='', embed=self.player_shop_embed_message(player), view=view)

    async def start_activity_callback(self, interaction: discord.Interaction, activity: Activity):
        user = interaction.user
        if not await self._is_valid_interaction(interaction):
            return

        player = await self.get_player(str(user.id))

        if player:
            player.change_activity(activity)
            await self.update_player(player)
            view = ActivitiesMenuView(self, user.id, player)
            await interaction.response.edit_message(content='', embed=self.player_activities_embed_message(player), view=view)

    async def register_callback(self, interaction: discord.Interaction):
        user = interaction.user
        if not await self._is_valid_interaction(interaction):
            return

        player = await self.get_player(str(user.id))

        if not player:
            # Register the player and update the message
            await self.register_player(str(user.id), user.display_name)
            player = await self.get_player(str(user.id))
            await self.update_player(player)
            view = MainMenuView(self, user.id)
            await interaction.response.edit_message(content='', embed=self.player_stats_embed_message(player), view=view)

    async def _is_valid_interaction(self, interaction: discord.Interaction):
        view = self.views.get(interaction.message.id)

        if view and not view.is_owner(interaction):
            return False
        return True

    async def get_currencies_from_db(self):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT currency_id, name, default_capacity
            FROM currencies''') as cursor:

                currencies = await cursor.fetchall()

                self.currencies = {}
                for currency in currencies:
                    self.currencies[currency[0]] = Currency(
                        currency[0], currency[1],
                        currency[2])

    async def get_activities_from_db(self):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT activity_id, name, type, output_item, output_amount, duration_seconds, unlock_conditions, description, status_description
            FROM activities''') as cursor:

                activities = await cursor.fetchall()

                self.activities = {}
                for activity in activities:
                    unlock_conditions = activity[6]
                    if unlock_conditions is None or unlock_conditions == "":
                        unlock_conditions = []
                    else:
                        unlock_conditions = unlock_conditions.split(',')

                    self.activities[activity[0]] = Activity(
                        activity[0], activity[1],
                        activity[2], activity[3],
                        activity[4], activity[5],
                        unlock_conditions, activity[7],
                        activity[8]
                    )

    async def get_upgrades_from_db(self):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT upgrade_id, name, stat, modifier_type, modifier_value, cost_material, cost, max_purchases, description
            FROM upgrades''') as cursor:

                upgrades = await cursor.fetchall()

                self.upgrades = {}
                for upgrade in upgrades:
                    self.upgrades[upgrade[0]] = Upgrade(
                        upgrade[0], upgrade[1],
                        upgrade[2], upgrade[3],
                        upgrade[4], upgrade[5],
                        upgrade[6], upgrade[7],
                        upgrade[8])

            async with db.execute('''
            SELECT upgrade_id, condition
            FROM upgrade_unlock_conditions''') as cursor:

                unlock_conditions = await cursor.fetchall()

                for condition in unlock_conditions:
                    upgrade_id = condition[0]
                    condition_text = condition[1]

                    if upgrade_id in self.upgrades:
                        self.upgrades[upgrade_id].unlocks.append(condition_text)

    async def get_player_activities_from_db(self, player_id):
        await self.get_activities_from_db()
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT player_id, activity_id
            FROM player_activities
            WHERE player_id = ?''', (player_id,)) as cursor:

                player_activities = await cursor.fetchall()

                for player_activity in player_activities:
                    player_id, activity_id = player_activity
                    player = self.players[player_id]
                    player.current_activity = self.activities[activity_id]

    async def get_player_currencies_from_db(self, player_id):
        await self.get_currencies_from_db()
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT player_id, currency_id, amount
            FROM player_currencies
            WHERE player_id = ?''', (player_id,)) as cursor:

                player_currencies = await cursor.fetchall()

                for player_currency in player_currencies:
                    player_id, currency_id, amount = player_currency
                    player = self.players[player_id]
                    currency = self.currencies[currency_id]
                    player.add_currency(currency)
                    currency.add_amount(amount)

    async def get_player_upgrades_from_db(self, player_id):
        await self.get_upgrades_from_db()
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT player_id, upgrade_id, count
            FROM player_upgrades
            WHERE player_id = ?''', (player_id,)) as cursor:

                player_upgrades = await cursor.fetchall()

                for player_upgrade in player_upgrades:
                    player_id, upgrade_id, count = player_upgrade
                    player = self.players[player_id]
                    upgrade = self.upgrades[upgrade_id]
                    player.add_upgrade(upgrade, count)

    async def get_player_from_db(self, player_id):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT player_id, player_display_name, last_update_time
            FROM players
            WHERE player_id = ?''', (player_id,)) as cursor:

                found_player = await cursor.fetchone()

                if found_player:
                    player_id, display_name, last_update_time = found_player
                    player = Player(player_id, display_name)
                    player.last_update_time = datetime.fromisoformat(last_update_time)
                    self.players[player_id] = player
                    await self.get_player_upgrades_from_db(player_id)
                    await self.get_player_currencies_from_db(player_id)
                    await self.get_player_activities_from_db(player_id)
                    await self.update_player(player)
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

    async def update_player(self, player):
        current_time = datetime.now()
        player.update(current_time)
        await self.player_to_database_update(player.id)

    async def player_to_database_update(self, player_id):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:

            player = self.players[player_id]
            player_upgrades = [(id, upgrade.count) for id, upgrade in player.upgrades.items()]
            player_currencies = [(id, currency.amount) for id, currency in player.currencies.items()]
            player_activity = player.current_activity

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

            # Clear all currencies that player doesn't have anymore
            if player_currencies:
                query = f"DELETE FROM player_currencies WHERE player_id = ? AND currency_id NOT IN ({placeholders_currencies})"

                params_currencies = [player_id] + [currency[0] for currency in player_currencies]

                await db.execute(query, params_currencies)
            else:
                await db.execute("DELETE FROM player_upgrades WHERE player_id = ?", (player_id,))

            # Clear all activities that player doesn't have anymore
            if player_activity:
                query = "DELETE FROM player_activities WHERE player_id = ? AND activity_id != ?"

                params_activities = [player_id, player_activity.id]

                await db.execute(query, params_activities)
            else:
                await db.execute("DELETE FROM player_activities WHERE player_id = ?", (player_id,))

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

            # Add or update changed activities
            if player_activity:
                await db.execute('''
                    INSERT OR REPLACE INTO player_activities (player_id, activity_id)
                    VALUES (?, ?)
                ''', (player_id, player_activity.id))

            # Check if the player exists in the database
            async with db.execute('SELECT 1 FROM players WHERE player_id = ?', (player_id,)) as cursor:
                found_player = await cursor.fetchone()

            if found_player:
                await db.execute('''
                UPDATE players
                SET player_display_name = ?, last_update_time = ?
                WHERE player_id == ?
                ''', (player.display_name, player.last_update_time, player_id))
            else:
                await db.execute('''
                INSERT INTO players (player_id, player_display_name, last_update_time)
                VALUES (?, ?, ?)
                ''', (player_id, player.display_name, player.last_update_time))

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
        if player.current_activity:
            embed.add_field(name="🏃 Current activity", value=player.current_activity.status_description, inline=False)
        else:
            embed.add_field(name="🏃 Current activity", value='Currently doing nothing. Go get an activity!', inline=False)

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
            missing_upgrades_text = []
            for upgrade, upgrades_left in missing_upgrades:
                missing_upgrades_text.append(
                    f"**{upgrade.name}**\n"
                    f"• Cost: `{upgrade.cost} {upgrade.cost_material}`\n"
                    f"• Remaining: `{upgrades_left}`\n"
                    f"• Effect: {self.format_upgrade_text(upgrade)}"
                )
            embed.add_field(
                name="🛠️ Buyable Upgrades",
                value='\n\n'.join(missing_upgrades_text),
                inline=False
            )
        else:
            embed.add_field(
                name="🛠️ Buyable Upgrades",
                value='No more available upgrades to buy.',
                inline=False)

        return embed

    def player_activities_embed_message(self, player):
        """Create the activities embed message for the player."""
        embed = discord.Embed(
            title="🏃 Available Activities",
            description="You can select an activity here and you will continously do it.",
            color=discord.Color.green()
        )

        activities = self.get_available_activities(player)
        for activity in activities:

            stat_key = f"{activity.output_item}.gain"

            modifiers = player.stat_modifiers.get(stat_key, {'increase': 0, 'multiplier': 1.0})

            modified_output = (activity.output_amount + modifiers['increase']) * modifiers['multiplier']

            modified_output_text = f" `+ {(modified_output - activity.output_amount):.2f}` " if modified_output - activity.output_amount > 0 else ''

            activity_details = (
                f"• Description: {activity.description}\n"
                f"• Benefit: {activity.output_amount:.2f} {modified_output_text}{activity.output_item} per {activity.duration_seconds} second(s)\n"
                f"• Requirements: {', '.join(activity.unlock_conditions) if activity.unlock_conditions else 'None'}\n"
            )

            embed.add_field(name=f'__{activity.name}__', value=activity_details, inline=False)

        return embed

    def format_upgrade_text(self, upgrade:  Upgrade):
        material_type, material_modifier = upgrade.stat.split('.')
        amount = upgrade.modifier_value
        modifier_type = upgrade.modifier_type

        modifier_text = material_modifier
        modifier_type_text = modifier_type

        if material_modifier == "capacity":
            modifier_text = 'max capacity'

        modifier_symbol = ''
        if modifier_type == 'increase':
            modifier_symbol = '+'

        if modifier_type == 'multiplier':
            modifier_symbol = 'x'

        formatted_text = f'{modifier_type_text} __{material_type.capitalize()}__ **{modifier_text}** by `{modifier_symbol}{format_number(amount)}`'

        if upgrade.unlocks:
            formatted_text += '\n• Unlocks: `'
            formatted_text += '`, `'.join(upgrade.unlocks)
            formatted_text += '`'

        return formatted_text

    def get_missing_upgrades(self, player) -> list[tuple[Upgrade, int]]:
        missing_upgrades = []
        upgrades_list = copy.deepcopy(self.upgrades)
        for id, upgrade in upgrades_list.items():
            if id in player.upgrades:
                upgrades_left = upgrade.max_purchases - player.upgrades[id].count
            else:
                upgrades_left = upgrade.max_purchases

            if upgrades_left > 0:
                missing_upgrades.append((upgrade, upgrades_left))

        return missing_upgrades

    def get_available_activities(self, player) -> list[Activity]:
        activities_list = []
        for activity in self.activities.values():
            if all(condition in player.unlock_conditions for condition in activity.unlock_conditions):
                activities_list.append(activity)

        return activities_list


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


async def create_player_activities_table(database_name):
    async with aiosqlite.connect(database_name) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS player_activities (
            player_id INTEGER NOT NULL,
            activity_id INTEGER NOT NULL,
            PRIMARY KEY (player_id, activity_id),
            FOREIGN KEY (activity_id) REFERENCES activities(activity_id)
        )
        ''')
        await db.commit()


async def create_activities_table(database_name):
    async with aiosqlite.connect(database_name) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            activity_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            output_item TEXT NOT NULL,
            output_amount INTEGER NOT NULL,
            duration_seconds INTEGER NOT NULL,
            unlock_conditions TEXT,
            description TEXT,
            status_description TEXT
        )
        ''')
        await db.commit()


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
            description TEXT
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS upgrade_unlock_conditions (
            id INTEGER PRIMARY KEY,
            upgrade_id INTEGER,
            condition TEXT,
            FOREIGN KEY (upgrade_id) REFERENCES upgrades (upgrade_id) ON DELETE CASCADE
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
                last_update_time TEXT
            )
        ''')
        await db.commit()


async def update_activities_from_json_to_db(database_name):
    with open(os.path.join(game_data_folder, 'activities.json'), encoding='utf-8') as file:
        activities = json.load(file)

    async with aiosqlite.connect(database_name) as db:
        for activity in activities:
            await db.execute('''
                INSERT OR IGNORE INTO activities (activity_id, name, type, output_item, output_amount, duration_seconds, unlock_conditions, description, status_description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (activity['id'], activity['name'], activity['type'],
                  activity['output_item'], activity['output_amount'],
                  activity['duration_seconds'], ','.join(activity['unlock_conditions']),
                  activity['description'],
                  activity['status_description']))
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
                description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (upgrade['id'], upgrade['name'], upgrade['stat'],
                  upgrade['modifier_type'], upgrade['modifier_value'],
                  upgrade['cost_material'], upgrade['cost'],
                  upgrade['max_purchases'], upgrade['description']))

            if upgrade['unlocks']:
                for condition in upgrade['unlocks']:
                    async with db.execute('''
                        SELECT 1 FROM upgrade_unlock_conditions WHERE upgrade_id = ? AND condition = ?
                    ''', (upgrade['id'], condition)) as cursor:
                        exists = await cursor.fetchone()

                    if not exists:
                        await db.execute('''
                            INSERT INTO upgrade_unlock_conditions (upgrade_id, condition)
                            VALUES (?, ?)
                        ''', (upgrade['id'], condition))

            await db.commit()


async def setup(bot):
    global tree
    tree = bot.tree
    bot.add_command(tree_sync)

    # create table if not exist
    await create_players_table(GAME_DB_LOCATION)

    await create_items_table(GAME_DB_LOCATION)
    # await update_items_from_json_to_db(DB_NAME)
    # await create_player_items_table(DB_NAME)

    await create_activities_table(GAME_DB_LOCATION)
    await update_activities_from_json_to_db(GAME_DB_LOCATION)
    await create_player_activities_table(GAME_DB_LOCATION)

    await create_currencies_table(GAME_DB_LOCATION)
    await update_currencies_from_json_to_db(GAME_DB_LOCATION)
    await create_player_currencies_table(GAME_DB_LOCATION)

    await create_upgrades_table(GAME_DB_LOCATION)
    await update_upgrades_from_json_to_db(GAME_DB_LOCATION)
    await create_player_upgrades_table(GAME_DB_LOCATION)

    game_cog = IncrementalGameCog(bot)
    await bot.add_cog(game_cog)
    await game_cog.get_currencies_from_db()
    await game_cog.get_upgrades_from_db()
    await game_cog.get_activities_from_db()
