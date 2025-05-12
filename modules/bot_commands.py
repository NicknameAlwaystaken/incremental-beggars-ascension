from __future__ import annotations
from typing import Optional
from discord.app_commands import CommandTree
from discord.ext import commands
from datetime import datetime
from modules.game_database import update_player_activities, update_player_chips, update_player_data, update_player_energies, update_player_games, update_player_items, update_player_locations, update_player_reputation, update_player_skills, update_player_upgrades
from modules.game_features import Game, GameSession, RPSGameSession, Task
from modules.menu_callbacks import activities_menu_callback, buy_chips_callback, main_menu_callback, redeem_chips_callback, register_callback, select_players_callback, shop_menu_callback, tasks_menu_callback
from modules.player_classes import Activity, Energy, Item, Location, Player, Reputation, Skill, Upgrade
from modules.utils import format_number, format_time
from views.views import MainMenuView
from views.dropdownviews import GamesDropdownView
from copy import deepcopy
from functools import partial, reduce
import os
import discord
import aiosqlite
import math

game_data_folder = 'game_data'

GAME_DB_LOCATION = os.path.join(game_data_folder, 'game.db')

SERVER_DB_LOCATION = os.path.join(game_data_folder, 'server.db')


MAX_MESSAGE_LENGTH = 2000

GAME_NAME = "Beggar's Ascension"

ACTIVITIES_PER_PAGE = 4

TASKS_PER_PAGE = 5

UPGRADES_PER_PAGE = 4

PRESHOW_BASIC_UNLOCKS = ["manual labour"]


class IncrementalGameCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.players: dict[int, Player] = {}
        self.reputations: dict[int, Reputation] = {}
        self.upgrades: dict[int, Upgrade] = {}
        self.activities: dict[int, Activity] = {}
        self.skills: dict[int, Skill] = {}
        self.locations: dict[int, Location] = {}
        self.energies: dict[int, Energy] = {}
        self.items: dict[int, Item] = {}
        self.tasks: dict[int, Task] = {}
        self.views: dict[int, discord.ui.View] = {}
        self.games: dict[int, Game] = {}
        self.active_games: dict[int, GameSession | RPSGameSession] = {}
        self.allowed_channels = {}

        self.initialized = False

        # I can't think of any better ways to do..
        # check without using global variable
        self.play = commands.check(self.is_allowed_channel)(self.play_command)
        self.game = commands.check(self.is_allowed_channel)(self.start_game_command)

    def initialize(self):
        self.initialized = True

    def get_energies(self):
        return {id: energy.copy() for id, energy in self.energies.items()}

    def get_upgrades(self):
        return {id: upgrade.copy() for id, upgrade in self.upgrades.items()}

    def get_activities(self):
        return {id: activity.copy() for id, activity in self.activities.items()}

    def get_locations(self):
        return {id: location.copy() for id, location in self.locations.items()}

    def get_tasks(self):
        return {id: task.copy() for id, task in self.tasks.items()}

    def get_skills(self):
        return {id: skill.copy() for id, skill in self.skills.items()}

    def get_games(self):
        return {id: game.copy() for id, game in self.games.items()}

    def get_items(self):
        return {id: item.copy() for id, item in self.items.items()}

    def get_location_tasks(self, location: Location):
        return {id: task.copy() for id, task in self.tasks.items() if id in location.tasks}

    def get_location_activities(self, location: Location):
        return {id: activity.copy() for id, activity in self.activities.items() if id in location.activities}

    def get_location_upgrades(self, location: Location):
        return {id: upgrade.copy() for id, upgrade in self.upgrades.items() if id in location.upgrades}

    async def is_allowed_channel(self, ctx):
        if ctx.guild is None:
            # Assuming that guild is None that user is using DMs to do commands
            return True

        server_id = ctx.guild.id
        channel_id = ctx.channel.id

        is_allowed = server_id in self.allowed_channels and any(channel["id"] == channel_id for channel in self.allowed_channels[server_id]["channels"])

        if not is_allowed:
            # Raise a specific error if the check fails due to channel restrictions
            raise WrongChannelError("You cannot use this command in this channel. Please use it in an allowed channel.")

        return True

    async def start_game(self, user, interaction, edit=False):
        player = await self.get_player(user)

        if player:
            spacing_character = " "
            padding_amount = 25
            full_bar = "🟦"
            empty_bar = "⬜"

            coins = player.items[0]
            bars_to_fill = int(((coins.amount / coins.capacity) * 100) // 10)
            coins_bar = f'  {full_bar * bars_to_fill}' + f'{empty_bar * (10 - bars_to_fill)}'
            coins_text = f"{coins.name.capitalize()}: {format_number(coins.amount)}/{format_number(coins.capacity)}"

            formatted_coins = f"`🪙 {coins_text + (spacing_character * (padding_amount - len(coins_text)))} {coins_bar}`"

            played, wins, losses, amount_bet, earnings = reduce(lambda acc, game: (
                acc[0] + game.played,
                acc[1] + game.wins,
                acc[2] + game.losses,
                acc[3] + game.amount_bet,
                acc[4] + game.earnings
            ), player.games.values(), (0, 0, 0, 0, 0))

            player_stats_text = f'\n\n**Totals**\nPlayed: `{format_number(played)}` Wins: `{format_number(wins)}` Losses: `{format_number(losses)}` Betted: `{format_number(amount_bet)}` Earnings: `{format_number(earnings)}`'

            view = GamesDropdownView(
                user.id, player,
                game_select_cb=partial(select_players_callback, self),
                add_cb=partial(buy_chips_callback, self),
                redeem_cb=partial(redeem_chips_callback, self)
            )
            content = f"{formatted_coins}" \
                f"\n\nYou have `{format_number(player.chips)}` Chips. You can trade Chips for Coins in 1:1 ratio." \
                f"{player_stats_text}" \
                "\n\nChoose a game:"
            if not edit:
                message = await interaction.send(content=content, view=view, ephemeral=True)
            else:
                await interaction.response.edit_message(content=content, view=view)
                message = interaction.message

            self.views[message.id] = message.id

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, WrongChannelError):
            await ctx.send("You cannot use this command in this channel. Please use it in an allowed channel.", ephemeral=True)

        elif isinstance(error, commands.CheckFailure):
            await ctx.send("You don't have permissions to use this command.", ephemeral=True)
        else:
            raise error

    @commands.hybrid_command(name="game", with_app_command=True)
    async def start_game_command(self, ctx):
        """Game menu, you can play games for fun or to gamble!"""
        if not self.initialized:
            print("Not done initializing!")
            return

        user = ctx.author

        await self.update_player(user)
        await self.start_game(user, ctx)

    @commands.has_permissions(manage_channels=True)
    @commands.hybrid_command(name='add_channel', with_app_command=True)
    async def add_channel_command(self, ctx):
        """Add this channel for using this bot"""
        if not self.initialized:
            print("Not done initializing!")
            return

        channel_id = ctx.channel.id
        server_id = ctx.guild.id

        if server_id not in self.allowed_channels:
            self.allowed_channels[server_id] = {"name": ctx.guild.name, "channels": []}

        all_channels = self.allowed_channels[server_id]["channels"]

        if not any(channel["id"] == channel_id for channel in all_channels):
            self.allowed_channels[server_id]["channels"].append({"id": channel_id, "name": ctx.channel.name})

            await self.save_channels_to_db()

            await ctx.send("This channel is now accepted as channel for bot commands!", ephemeral=True)
        else:
            await ctx.send("This channel already is accepted!.", ephemeral=True)

    # Command to send a message with the button
    @commands.has_permissions(manage_channels=True)
    @commands.hybrid_command(name='remove_channel', with_app_command=True)
    async def remove_channel_command(self, ctx):
        """Remove this channel for using this bot"""
        if not self.initialized:
            print("Not done initializing!")
            return

        channel_id = ctx.channel.id
        server_id = ctx.guild.id

        if server_id not in self.allowed_channels:
            self.allowed_channels[server_id] = {"name": ctx.guild.name, "channels": []}

        all_channels = self.allowed_channels[server_id]["channels"]

        for channel in all_channels:
            if channel["id"] == channel_id:
                self.allowed_channels[server_id]["channels"].remove(channel)

                await self.save_channels_to_db()

                await ctx.send("This channel has been now removed from channel list!", ephemeral=True)
                return

        await ctx.send("This channel was not in the channel list.", ephemeral=True)

    @commands.command(name='levelup')
    async def levelup_command(self, ctx, *args):
        if not self.initialized:
            print("Not done initializing!")
            return

        if len(args) != 1:
            return

        skill_name = args[0]

        user = ctx.author
        player = await self.get_player(user)

        skill = next((skill for skill in self.get_skills().values() if skill.name.lower() == skill_name.lower()), None)

        if player and skill:
            if skill.id not in player.skills:
                player.skills[skill.id] = skill
            else:
                skill = player.skills[skill.id]

            skill.add_experience(skill.exp_required_for_next_level() - skill.current_exp)
            await self.update_player(user)

    @commands.command(name='addexp')
    async def addexp_command(self, ctx, *args):
        if not self.initialized:
            print("Not done initializing!")
            return

        if len(args) != 2:
            return

        skill_name, experience_amount = args

        user = ctx.author
        player = await self.get_player(user)

        skill = next((skill for skill in self.get_skills().values() if skill.name.lower() == skill_name.lower()), None)

        if player and skill:
            if skill.id not in player.skills:
                player.skills[skill.id] = skill
            else:
                skill = player.skills[skill.id]

            skill.add_experience(int(experience_amount))
            await self.update_player(user)

    # Command to send a message with the button
    @commands.hybrid_command(name="play", with_app_command=True)
    async def play_command(self, ctx):
        """Interactive play command"""
        if not self.initialized:
            print("Not done initializing!")
            return

        user = ctx.author
        player = await self.get_player(user)
        view = MainMenuView(
            self, user.id,
            activities_cb=activities_menu_callback,
            tasks_cb=tasks_menu_callback,
            shop_cb=shop_menu_callback,
            update_cb=main_menu_callback,
        )

        if not player:
            view.create_register_menu(register_cb=register_callback)
            register_message = "You have not registered yet!" \
                "\nGame offers content up to **level 10** of skills."\
                "\n**WARNING** Game is still in development so your progress"\
                " may be reset multiple times until full version release!"
            message = await ctx.send(content=register_message, view=view)
        else:
            await self.update_player(user)
            message = await ctx.send(content='', embed=self.player_stats_embed_message(player), view=view)

        self.views[message.id] = view

    def get_players_from_server(self, server_id):
        server = next((server for server in self.bot.guilds if server.id == server_id), None)
        if server:
            members_id_list = [member.id for member in server.members]
            return [player for player_id, player in self.players.items() if player_id in members_id_list]
        return []

    async def get_server_channels_from_db(self):
        async with aiosqlite.connect(SERVER_DB_LOCATION) as db:
            async with db.execute('''
            SELECT server_id, server_name
            FROM servers''') as cursor:

                servers = await cursor.fetchall()

                self.allowed_channels = {}
                for (server_id, server_name) in servers:
                    self.allowed_channels[server_id] = {"name": server_name, "channels": []}

            async with db.execute('''
            SELECT channel_id, server_id, channel_name
            FROM channels''') as cursor:

                channels = await cursor.fetchall()

                for (channel_id, server_id, channel_name) in channels:
                    if server_id in self.allowed_channels:
                        self.allowed_channels[server_id]["channels"].append({
                            "id": channel_id,
                            "name": channel_name
                        })

    async def get_energies_from_db(self):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT energy_id, name, max_energy, recovery_rate
            FROM energies''') as cursor:

                energies = await cursor.fetchall()

                self.energies = {}
                for energy in energies:
                    self.energies[energy[0]] = Energy(
                        energy[0], energy[1],
                        energy[2], energy[3])

    async def get_reputation_unlocks_from_db(self):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT unlock_id, name, description
            FROM reputation_unlocks''') as cursor:

                reputation_unlocks = await cursor.fetchall()

                self.reputation_unlocks = {}
                for unlock in reputation_unlocks:
                    self.reputation_unlocks[unlock[0]] = ReputationUnlock(
                        unlock[0], unlock[1], unlock[2])

    async def get_items_from_db(self):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT item_id, name, default_capacity
            FROM items''') as cursor:

                items = await cursor.fetchall()

                self.items = {}
                for item in items:
                    self.items[item[0]] = Item(
                        item[0], item[1],
                        item[2])

    async def get_games_from_db(self):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT game_id, name
            FROM games''') as cursor:

                games = await cursor.fetchall()

                self.games = {}
                for game in games:
                    self.games[game[0]] = Game(
                        game[0], game[1]
                    )

    async def get_reputation_from_db(self):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
                SELECT reputation_id, name, description, start_level, max_level, base_exp_requirement, scaling_factor, exp_formula
                FROM reputation
                LIMIT 1
            ''') as cursor:
                row = await cursor.fetchone()
                if row:
                    reputation_id = row[0]
                    self.reputations[reputation_id] = Reputation(
                        id=row[0],
                        name=row[1],
                        description=row[2],
                        start_level=row[3],
                        max_level=row[4],
                        base_exp_requirement=row[5],
                        scaling_factor=row[6],
                        exp_formula=row[7]
                    )

            # Fill unlocks for each reputation
            for rep_id, reputation in self.reputations.items():
                # reputation titles
                async with db.execute('''
                    SELECT id, name, level
                    FROM reputation_titles
                    WHERE reputation_id = ?
                    ORDER BY level ASC
                ''', (rep_id,)) as cursor:
                    titles = await cursor.fetchall()

                reputation.titles = [{"id": t[0], "name": t[1], "level": t[2]} for t in titles]

                # reputation unlocks
                async with db.execute('''
                    SELECT id, level
                    FROM reputation_unlocks
                    WHERE reputation_id = ?
                ''', (rep_id,)) as cursor:
                    unlocks = await cursor.fetchall()

                for unlock_id, level in unlocks:
                    reputation.unlocks[unlock_id] = {
                        "level": level,
                        "conditions": []
                    }

                async with db.execute('''
                    SELECT unlock_id, effect
                    FROM reputation_unlock_effects
                ''') as cursor:
                    effects = await cursor.fetchall()

                for unlock_id, effect in effects:
                    if unlock_id in reputation.unlocks:
                        reputation.unlocks[unlock_id]["conditions"].append(effect)

    async def get_locations_from_db(self):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            # 1. Load all locations
            async with db.execute('SELECT location_id, name, icon_png FROM locations') as cursor:
                locations = await cursor.fetchall()

                self.locations = {}
                for loc in locations:
                    location_id, name, icon_png = loc
                    self.locations[location_id] = Location(id=location_id, name=name, icon_png=icon_png)

            # Helper: name → id maps
            async def make_lookup(table: str):
                async with db.execute(f"SELECT id, name FROM {table}") as cursor:
                    return {name: id for id, name in await cursor.fetchall()}

            activity_dict = self.get_activities()
            task_dict = self.get_tasks()
            upgrade_dict = self.get_upgrades()

            # 2. Link activities
            async with db.execute('SELECT location_id, activity FROM location_activities') as cursor:
                for loc_id, activity_name in await cursor.fetchall():
                    activity_id = next((activity.id for activity in activity_dict.values() if activity_name == activity.name), None)
                    if activity_id is not None:
                        self.locations[loc_id].activities.append(activity_id)

            # 3. Link tasks
            async with db.execute('SELECT location_id, task FROM location_tasks') as cursor:
                for loc_id, task_name in await cursor.fetchall():
                    task_id = next((task.id for task in task_dict.values() if task_name == task.name), None)
                    if task_id is not None:
                        self.locations[loc_id].tasks.append(task_id)

            # 4. Link upgrades
            async with db.execute('SELECT location_id, upgrade FROM location_upgrades') as cursor:
                for loc_id, upgrade_name in await cursor.fetchall():
                    upgrade_id = next((upgrade.id for upgrade in upgrade_dict.values() if upgrade_name == upgrade.name), None)
                    if upgrade_id is not None:
                        self.locations[loc_id].upgrades.append(upgrade_id)

    async def get_skills_from_db(self):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT skill_id, name, description, start_level, max_level, base_exp_requirement, scaling_factor, exp_formula
            FROM skills''') as cursor:

                skills = await cursor.fetchall()

                self.skills = {}
                for skill in skills:
                    self.skills[skill[0]] = Skill(
                        id=skill[0],
                        name=skill[1],
                        description=skill[2],
                        start_level=skill[3],
                        max_level=skill[4],
                        base_exp_requirement=skill[5],
                        scaling_factor=skill[6],
                        exp_formula=skill[7]
                    )

            # Fetch the effects from the skill_effects table
            async with db.execute('''
            SELECT skill_id, stat, modifier_type, modifier_value
            FROM skill_effects''') as cursor:

                effects = await cursor.fetchall()

                for effect in effects:
                    skill_id = effect[0]
                    stat = effect[1]
                    modifier_type = effect[2]
                    modifier_value = effect[3]

                    if skill_id in self.skills:
                        self.skills[skill_id].effects[stat] = {
                            'modifier_type': modifier_type,
                            'modifier_value': modifier_value
                        }

    async def get_activities_from_db(self):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT activity_id, name, icon, output_item, output_amount, energy_type, energy_drain_rate, skill, skill_exp_rate, unlock_conditions, description, status_description
            FROM activities''') as cursor:

                activities = await cursor.fetchall()

                self.activities = {}
                for activity in activities:
                    skill = next((skill.copy() for skill in self.get_skills().values() if activity[7].lower() == skill.name.lower()), None)
                    item = next((item.copy() for item in self.get_items().values() if activity[3].lower() == item.name.lower()), None)
                    unlock_conditions = activity[9]
                    if unlock_conditions is None or unlock_conditions == "":
                        unlock_conditions = []
                    else:
                        unlock_conditions = unlock_conditions.split(',')

                    self.activities[activity[0]] = Activity(
                        id=activity[0],
                        name=activity[1],
                        icon=activity[2],
                        output_item=item,
                        output_amount=activity[4],
                        energy_type=activity[5],
                        energy_drain_rate=activity[6],
                        skill=skill,
                        skill_exp_rate=activity[8],
                        unlock_conditions=unlock_conditions,
                        description=activity[10],
                        status_description=activity[11]
                    )

    async def get_tasks_from_db(self):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT task_id, name, icon, task_amount, description
            FROM tasks''') as cursor:

                tasks = await cursor.fetchall()

                self.tasks = {}
                for task in tasks:
                    self.tasks[task[0]] = Task(
                        id=task[0],
                        name=task[1],
                        icon=task[2],
                        task_amount=task[3],
                        description=task[4]
                    )

            async with db.execute('''
            SELECT task_id, output_item, output_amount
            FROM task_outputs
            ''') as cursor:
                outputs = await cursor.fetchall()

            for output in outputs:
                task_id, item, amount = output
                if task_id in self.tasks:
                    self.tasks[task_id].outputs.append({"item": item, "amount": amount})

            async with db.execute('''
            SELECT task_id, cost_item, cost_amount
            FROM task_costs
            ''') as cursor:
                costs = await cursor.fetchall()

            for cost in costs:
                task_id, item, amount = cost
                if task_id in self.tasks:
                    self.tasks[task_id].costs.append({"item": item, "amount": amount})

            async with db.execute('''
            SELECT task_id, energy_type, energy_amount
            FROM task_energy_costs
            ''') as cursor:
                energy_costs = await cursor.fetchall()

            for energy_cost in energy_costs:
                task_id, energy, amount = energy_cost
                if task_id in self.tasks:
                    self.tasks[task_id].energy_costs.append({"energy": energy, "amount": amount})

            async with db.execute('''
            SELECT task_id, stat, modifier_type, modifier_value
            FROM task_effects''') as cursor:

                effects = await cursor.fetchall()

                for effect in effects:
                    task_id = effect[0]
                    stat = effect[1]
                    modifier_type = effect[2]
                    modifier_value = effect[3]

                    if task_id in self.tasks:
                        self.tasks[task_id].effects[stat] = {
                            'modifier_type': modifier_type,
                            'modifier_value': modifier_value
                        }

            async with db.execute('''
            SELECT task_id, condition
            FROM task_unlock_conditions''') as cursor:

                unlock_conditions = await cursor.fetchall()

                for condition in unlock_conditions:
                    task_id = condition[0]
                    condition_text = condition[1]

                    if task_id in self.tasks:
                        self.tasks[task_id].unlock_conditions.append(condition_text)

            async with db.execute('''
            SELECT task_id, condition
            FROM task_unlocks''') as cursor:

                unlocks = await cursor.fetchall()

                for unlock in unlocks:
                    task_id = unlock[0]
                    condition_text = unlock[1]

                    if task_id in self.tasks:
                        self.tasks[task_id].unlocks.append(condition_text)

    async def get_upgrades_from_db(self):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT upgrade_id, name, cost_material, cost, max_purchases, description
            FROM upgrades''') as cursor:

                upgrades = await cursor.fetchall()

                self.upgrades = {}
                unordered_upgrades = {}
                for upgrade in sorted(upgrades, key=lambda x: x[3]):
                    unordered_upgrades[upgrade[0]] = Upgrade(
                        id=upgrade[0],
                        name=upgrade[1],
                        cost_material=upgrade[2],
                        cost=upgrade[3],
                        max_purchases=upgrade[4],
                        description=upgrade[5]
                    )

                self.upgrades = deepcopy(unordered_upgrades)

            # Fetch the effects from the upgrade_effects table
            async with db.execute('''
            SELECT upgrade_id, stat, modifier_type, modifier_value
            FROM upgrade_effects''') as cursor:

                effects = await cursor.fetchall()

                for effect in effects:
                    upgrade_id = effect[0]
                    stat = effect[1]
                    modifier_type = effect[2]
                    modifier_value = effect[3]

                    if upgrade_id in self.upgrades:
                        self.upgrades[upgrade_id].effects[stat] = {
                            'modifier_type': modifier_type,
                            'modifier_value': modifier_value
                        }

            async with db.execute('''
            SELECT upgrade_id, condition
            FROM upgrade_unlock_conditions''') as cursor:

                unlock_conditions = await cursor.fetchall()

                for condition in unlock_conditions:
                    upgrade_id = condition[0]
                    condition_text = condition[1]

                    if upgrade_id in self.upgrades:
                        self.upgrades[upgrade_id].unlock_conditions.append(condition_text)

            async with db.execute('''
            SELECT upgrade_id, condition
            FROM upgrade_unlocks''') as cursor:

                unlocks = await cursor.fetchall()

                for unlock in unlocks:
                    upgrade_id = unlock[0]
                    condition_text = unlock[1]

                    if upgrade_id in self.upgrades:
                        self.upgrades[upgrade_id].unlocks.append(condition_text)

    async def get_player_locations_from_db(self, player_id):
        await self.get_locations_from_db()
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT player_id, location_id
            FROM player_locations
            WHERE player_id = ?''', (player_id,)) as cursor:

                player_locations = await cursor.fetchall()

                for player_location in player_locations:
                    player_id, location_id = player_location
                    player = self.players[int(player_id)]
                    player.current_location = self.locations[location_id].copy()

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
                    player = self.players[int(player_id)]
                    player.current_activity = self.activities[activity_id].copy()

    async def get_player_energies_from_db(self, player_id):
        await self.get_energies_from_db()
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT player_id, energy_id, current_energy
            FROM player_energies
            WHERE player_id = ?''', (player_id,)) as cursor:

                player_energies = await cursor.fetchall()

                for player_energy in player_energies:
                    player_id, energy_id, current_amount = player_energy
                    player = self.players[int(player_id)]
                    energy = self.energies[energy_id].copy()
                    player.add_energy(energy)
                    energy.current_energy = current_amount

    async def get_player_items_from_db(self, player_id):
        await self.get_items_from_db()
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT player_id, item_id, amount
            FROM player_items
            WHERE player_id = ?''', (player_id,)) as cursor:

                player_items = await cursor.fetchall()

                for player_item in player_items:
                    player_id, item_id, amount = player_item
                    player = self.players[int(player_id)]
                    item = self.items[item_id].copy()
                    player.add_item(item)
                    item.set_amount(amount)

    async def get_player_chips_from_db(self, player_id):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT player_id, amount
            FROM player_chips
            WHERE player_id = ?''', (player_id,)) as cursor:

                player_chips = await cursor.fetchall()

                for player_chip in player_chips:
                    player_id, amount = player_chip
                    player = self.players[int(player_id)]
                    player.chips = amount

    async def get_player_games_from_db(self, player_id):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT player_id, game_id, played, wins, losses, amount_bet, earnings
            FROM player_games
            WHERE player_id = ?''', (player_id,)) as cursor:

                player_games = await cursor.fetchall()

                for player_game in player_games:
                    player_id, game_id, played, wins, losses, amount_bet, earnings = player_game
                    player = self.players[int(player_id)]
                    new_game = self.games[game_id].copy()
                    new_game.played = played
                    new_game.wins = wins
                    new_game.losses = losses
                    new_game.amount_bet = amount_bet
                    new_game.earnings = earnings
                    player.games[game_id] = new_game

    async def get_player_reputations_from_db(self, player_id):
        await self.get_reputation_from_db()
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT player_id, reputation_id, current_level, current_exp
            FROM player_reputations
            WHERE player_id = ?''', (player_id,)) as cursor:

                player_reputations = await cursor.fetchall()

                for player_reputation in player_reputations:
                    player_id, reputation_id, _, current_exp = player_reputation
                    player = self.players[int(player_id)]
                    if self.reputations:
                        reputation = self.reputations[reputation_id].copy()
                        player.add_reputation(reputation)
                        reputation.add_experience(current_exp)

    async def get_player_skills_from_db(self, player_id):
        await self.get_skills_from_db()
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT player_id, skill_id, current_level, current_exp
            FROM player_skills
            WHERE player_id = ?''', (player_id,)) as cursor:

                player_skills = await cursor.fetchall()

                for player_skill in player_skills:
                    player_id, skill_id, _, current_exp = player_skill
                    player = self.players[int(player_id)]
                    skill = self.skills[skill_id].copy()
                    player.add_skill(skill)
                    skill.add_experience(current_exp)

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
                    player = self.players[int(player_id)]
                    upgrade = self.upgrades[upgrade_id].copy()
                    player.add_upgrade(upgrade, count)

    async def get_player_from_db(self, user: discord.User | discord.Member):
        player_id = user.id
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT player_id, player_name, player_display_name, start_date, last_update_time
            FROM players
            WHERE player_id = ?''', (player_id,)) as cursor:

                found_player = await cursor.fetchone()

                if found_player:
                    player_id, name, display_name, start_date, last_update_time = found_player
                    player = Player(player_id, name, display_name)
                    # initialize with default location
                    player.set_location(self.locations[0])
                    player.last_update_time = datetime.fromisoformat(last_update_time)
                    player.start_date = datetime.fromisoformat(start_date)
                    self.players[int(player_id)] = player

                    await self.get_player_reputations_from_db(player_id)
                    await self.get_player_upgrades_from_db(player_id)
                    await self.get_player_items_from_db(player_id)
                    await self.get_player_skills_from_db(player_id)
                    await self.get_player_energies_from_db(player_id)
                    await self.get_player_activities_from_db(player_id)
                    await self.get_player_locations_from_db(player_id)
                    await self.get_player_chips_from_db(player_id)
                    await self.get_player_games_from_db(player_id)

                    self.recalculate_player_modifiers(player)

                    await self.update_player(user)
                    return player
                else:
                    return None

    async def get_player(self, user: discord.User | discord.Member):
        player_id = user.id
        # check if we are trying to get the bot instead of another user
        if self.bot.user:
            if player_id == self.bot.user.id:
                if player_id not in self.players:
                    await self.register_player(user)
                return self.players[int(player_id)]

        if player_id not in self.players:
            player = await self.get_player_from_db(user)
            if player:
                self.players[int(player_id)] = player
                return player
            else:
                return None
        else:
            await self.player_to_database_update(user)
            return self.players[int(player_id)]

    def recalculate_player_modifiers(self, player: Player):
        # reset item capacity
        for item_id, player_item in player.items.items():
            baseline_item = next((item for item in self.get_items().values() if item_id == item.id), None)

            if baseline_item:
                player_item.capacity = baseline_item.capacity

        # reset upgrade max_purchases
        for upgrade_id, player_upgrade in player.upgrades.items():
            baseline_upgrade = next((upgrade for upgrade in self.get_upgrades().values() if upgrade_id == upgrade.id), None)

            if baseline_upgrade:
                player_upgrade.max_purchases = baseline_upgrade.max_purchases
                player_upgrade.effects = deepcopy(baseline_upgrade.effects)

        player.recalculate_modifiers()
        player.apply_upgrade_modifiers()
        player.apply_item_modifiers()
        player.apply_energy_modifiers()

    async def update_player(self, user: discord.User | discord.Member):
        player = await self.get_player(user)
        if player:
            current_time = datetime.now()
            player.update(current_time)

            self.recalculate_player_modifiers(player)

            await self.player_to_database_update(user)

    def complete_task(self, task: Task, player: Player):
        can_afford = True
        cost_list = []
        for cost in task.energy_costs:
            get_item = next((item for item in player.energies.values() if item.name.lower() == cost["energy"].lower()), None)
            if not get_item or get_item.current_energy < cost["amount"]:
                can_afford = False
            else:
                cost_list.append(("energy", get_item, cost["amount"]))

        for cost in task.costs:
            get_item = next((item for item in player.items.values() if item.name.lower() == cost["item"].lower()), None)
            if not get_item or get_item.amount < cost["amount"]:
                can_afford = False
            else:
                cost_list.append(("item", get_item, cost["amount"]))

        if not can_afford:
            return

        for output in task.outputs:
            get_item = next((item for item in player.items.values() if item.name.lower() == output["item"].lower()), None)
            if get_item:
                if get_item.amount < get_item.capacity:
                    get_item.increase_amount(output["amount"])
            else:
                get_item = next((item for item in player.reputations.values() if item.name.lower() == output["item"].lower()), None)
                if get_item:
                    get_item.add_experience(output["amount"])

        for key, item, cost in cost_list:
            if key == "energy":
                item.deplete(cost)
            if key == "item":
                item.amount -= cost

    async def player_to_database_update(self, user: discord.User | discord.Member):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            player_id = user.id
            player = self.players[int(player_id)]
            player.name = user.name
            player.display_name = user.display_name
            player_upgrades = [(id, upgrade.count) for id, upgrade in player.upgrades.items()]
            player_items = [(id, item.amount) for id, item in player.items.items()]
            player_chips = player.chips
            player_activity = player.current_activity
            player_location = player.current_location
            player_skills = [(id, skill.current_level, skill.current_exp) for id, skill in player.skills.items()]
            player_energies = [(id, energy.current_energy) for id, energy in player.energies.items()]
            player_games = [(id, game.played, game.wins, game.losses, game.amount_bet, game.earnings) for id, game in player.games.items()]
            player_reputations = [(id, reputation.current_level, reputation.current_exp) for id, reputation in player.reputations.items()]

            await db.execute('BEGIN')

            await update_player_upgrades(db, player_id, player_upgrades)
            await update_player_items(db, player_id, player_items)
            await update_player_skills(db, player_id, player_skills)
            await update_player_locations(db, player_id, player_location)
            await update_player_reputation(db, player_id, player_reputations)
            await update_player_activities(db, player_id, player_activity)
            await update_player_energies(db, player_id, player_energies)
            await update_player_chips(db, player_id, player_chips)
            await update_player_games(db, player_id, player_games)
            await update_player_data(db, player_id, player)

            await db.commit()

    async def register_player(self, user: discord.User | discord.Member):
        new_player = Player(user.id, user.name, user.display_name)
        new_player.add_item(self.items[0].copy())
        new_player.add_skill(self.skills[0].copy())
        new_player.add_reputation(self.reputations[0].copy())
        new_player.add_energy(self.energies[0].copy())
        new_player.add_upgrade(self.upgrades[0].copy())
        new_player.games = self.get_games()

        new_player.update_title()
        new_player.set_location(self.locations[0])

        self.players[user.id] = new_player

        self.recalculate_player_modifiers(new_player)
        await self.player_to_database_update(user)

    def player_stats_embed_message(self, player):
        embed_color = discord.Color.green() if player.current_activity else discord.Color.red()
        reputation_text = str(next((item for item in player.reputations.values() if item.name.lower() == "reputation"), ""))
        embed = discord.Embed(
            title="🎩 Player Status",
            description=f"**{player.title}**: __{player.display_name}__\n{reputation_text}\nPlaytime: {format_time((datetime.now() - player.start_date).total_seconds())}\nTime passed: {format_time(player.time_since_last_update)}",
            color=embed_color
        )

        if player.current_activity:
            activity_name = player.current_activity.name.lower()
            embed.set_thumbnail(url=f"https://raw.githubusercontent.com/NicknameAlwaystaken/incremental-beggars-ascension/refs/heads/main/images/activity/{activity_name}.png")

        if player.current_location:
            location_png = player.current_location.icon_png
            location_name = player.current_location.name

            embed.set_footer(text=location_name,icon_url=f"https://raw.githubusercontent.com/NicknameAlwaystaken/incremental-beggars-ascension/refs/heads/main/images/location/{location_png}.png")

        spacing_character = " "
        padding_amount = 25
        full_bar = "🟦"
        empty_bar = "⬜"

        player_base_energy = player.energies[0]
        recover_text = ' (Recovering energy)' if player_base_energy.recovering else ''
        if player.current_activity:
            embed.add_field(name="🏃 Current activity", value=player.current_activity.status_description + recover_text, inline=False)
        else:
            embed.add_field(name="🏃 Current activity", value='__Currently doing nothing. Go get an activity!__' + recover_text, inline=False)

        formatted_items = []
        for item in player.items.values():
            bars_to_fill = int(((item.amount / item.capacity) * 100) // 10)
            item_bar = f'  {full_bar * bars_to_fill}' + f'{empty_bar * (10 - bars_to_fill)}'
            last_gained = f"  (+{format_number(item.last_gained)})" if item.last_gained > 0 else ''
            item_text = f"{item.name.capitalize()}: {format_number(item.amount)}/{format_number(item.capacity)}{last_gained}"

            formatted_items.append(f"`{item_text + (spacing_character * (padding_amount - len(item_text)))} {item_bar}`")

        embed.add_field(name="🎒 Items", value='\n'.join(formatted_items), inline=False)

        if player.energies:
            formatted_energies = []
            for energy in player.energies.values():
                bars_to_fill = int(((energy.current_energy / energy.max_energy) * 100) // 10)
                energy_bar = f'  {full_bar * bars_to_fill}' + f'{empty_bar * (10 - bars_to_fill)}'
                is_recovering_text = ' (Recovering)' if energy.recovering else ''
                energy_text = f"{energy.name.capitalize()}: {format_number(energy.current_energy)}/{format_number(energy.max_energy)}{is_recovering_text}"

                formatted_energies.append(f"`{energy_text + (spacing_character * (padding_amount - len(energy_text)))} {energy_bar}`")

            embed.add_field(name='⚡ Energies', value='\n'.join(formatted_energies), inline=False)

        if player.skills:
            skills_list = [str(skill) for skill in player.skills.values()]
            embed.add_field(name='🎓 Skills', value='\n'.join(skills_list), inline=False)

        if player.upgrades:
            embed.add_field(name="🛠️ Upgrades", value=', '.join([str(upgrade) for upgrade in player.upgrades.values()]), inline=False)

        return embed

    def player_shop_embed_message(self, player, page=1):
        embed_color = discord.Color.green() if player.current_activity else discord.Color.red()
        formatted_items = []
        for item in player.items.values():
            formatted_items.append(f"{item.name.capitalize()}: {format_number(item.amount)}/{format_number(item.capacity)} (+{format_number(item.last_gained)})")

        missing_upgrades = self.get_missing_upgrades_filtered_by_location(player)

        missing_upgrades_text = []

        if page < 1:
            page = 1

        upgrades_count = 0
        if missing_upgrades:
            for upgrade, upgrades_left in missing_upgrades:
                if not self.satisfies_unlock_conditions(player, upgrade.unlock_conditions):
                    continue

                upgrades_count += 1

                start_index = (page - 1) * UPGRADES_PER_PAGE
                end_index = page * UPGRADES_PER_PAGE

                if start_index < upgrades_count <= end_index:
                    player_item = next((item for item in player.items.values() if item.name.lower() == upgrade.cost_material.lower()), None)
                    can_afford_emoji = "❌"
                    if player_item and player_item.amount >= upgrade.cost:
                        can_afford_emoji = "✅"

                    missing_upgrades_text.append(
                        f"**{upgrade.name}** {can_afford_emoji}"
                        f"\n{upgrade.description}"
                        f"\n• Cost: `{upgrade.cost} {upgrade.cost_material}`"
                        f"\n• Remaining: `{upgrades_left}`"
                        f"{self.format_upgrade_text(upgrade)}"
                    )

        pages = max(1, math.ceil(upgrades_count / UPGRADES_PER_PAGE))

        embed = discord.Embed(
            title=f"🛒 Upgrade shop - Page {page}/{pages}",
            description=f"**{player.title}**: __{player.display_name}__",
            color=embed_color
        )

        if player.current_activity:
            activity_name = player.current_activity.name.lower()
            embed.set_thumbnail(url=f"https://raw.githubusercontent.com/NicknameAlwaystaken/incremental-beggars-ascension/refs/heads/main/images/activity/{activity_name}.png")

        if player.current_location:
            location_png = player.current_location.icon_png
            location_name = player.current_location.name

            embed.set_footer(text=location_name,icon_url=f"https://raw.githubusercontent.com/NicknameAlwaystaken/incremental-beggars-ascension/refs/heads/main/images/location/{location_png}.png")

        spacing_character = " "
        padding_amount = 25
        full_bar = "🟦"
        empty_bar = "⬜"

        formatted_items = []
        for item in player.items.values():
            bars_to_fill = int(((item.amount / item.capacity) * 100) // 10)
            item_bar = f'  {full_bar * bars_to_fill}' + f'{empty_bar * (10 - bars_to_fill)}'
            last_gained = f"  (+{format_number(item.last_gained)})" if item.last_gained > 0 else ''
            item_text = f"{item.name.capitalize()}: {format_number(item.amount)}/{format_number(item.capacity)}{last_gained}"

            formatted_items.append(f"`{item_text + (spacing_character * (padding_amount - len(item_text)))} {item_bar}`")

        embed.add_field(name="🎒 Items", value='\n'.join(formatted_items), inline=False)

        embed.add_field(
            name="🛠️ Buyable Upgrades",
            value='\n\n'.join(missing_upgrades_text) if missing_upgrades_text else 'No more available upgrades to buy.',
            inline=False
        )

        return embed

    def player_activities_embed_message(self, player, page=1):
        embed_color = discord.Color.green() if player.current_activity else discord.Color.red()

        activities = self.get_available_activities(player)

        activities_count = 0

        activity_details = []

        for items in activities:
            button_type, activity = items

            activities_count += 1

            start_index = (page - 1) * ACTIVITIES_PER_PAGE
            end_index = page * ACTIVITIES_PER_PAGE

            if start_index < activities_count <= end_index:
                if not activity.output_item:
                    return

                stat_key = f"{activity.output_item.name}.gain"

                modifiers = player.stat_modifiers.get(stat_key, {'increase': 0, 'multiplier': 1.0})

                modified_output = (activity.output_amount + modifiers['increase']) * modifiers['multiplier']

                modified_output_text = f" `+{(modified_output - activity.output_amount):.2f}` " if modified_output - activity.output_amount > 0 else ''

                requirements_text = f"\n• Requirements: `{'`, `'.join(activity.unlock_conditions)}`" if activity.unlock_conditions else ''

                benefits_text = f"\n• Benefit: __{activity.output_amount:.2f}__ {modified_output_text}{activity.output_item.name.capitalize()} per second" if activity.output_item else ''

                activity_energy = next((energy for energy in self.get_energies().values() if energy and activity.energy_type and activity.energy_type.lower() == energy.name.lower()), None)

                if activity_energy:
                    drain_text = f"\n• Drain: __{format_number(activity.energy_drain_rate)}__ {activity_energy.name.capitalize()} per second"
                else:
                    drain_text = ''

                activity_exp = f'\nGains `{format_number(activity.skill_exp_rate)}` {activity.skill.name} experience per second' if activity.skill else ''

                enabled_text = ' - *Missing requirements!*' if button_type == "disabled" else ''

                activity_details.append(
                    f"**{activity.name}**{enabled_text}"
                    f"\n*{activity.description}*"
                    f"{benefits_text}"
                    f"{drain_text}"
                    f"{requirements_text}"
                    f"{activity_exp}"
                )

        pages = max(1, math.ceil(activities_count / ACTIVITIES_PER_PAGE))

        embed = discord.Embed(
            title=f"🏃 Available Activities - Page {page}/{pages}",
            description="Activities are **passive** actions.\nSelected activity runs all the time.",
            color=embed_color
        )

        if player.current_activity:
            activity_name = player.current_activity.name.lower()
            embed.set_thumbnail(url=f"https://raw.githubusercontent.com/NicknameAlwaystaken/incremental-beggars-ascension/refs/heads/main/images/activity/{activity_name}.png")

        if player.current_location:
            location_png = player.current_location.icon_png
            location_name = player.current_location.name

            embed.set_footer(text=location_name,icon_url=f"https://raw.githubusercontent.com/NicknameAlwaystaken/incremental-beggars-ascension/refs/heads/main/images/location/{location_png}.png")

        embed.add_field(name='', value='\n\n'.join(activity_details), inline=False)
        return embed

    def player_tasks_embed_message(self, player, page=1):
        embed_color = discord.Color.green() if player.current_activity else discord.Color.red()

        tasks = self.get_available_tasks(player)

        tasks_count = 0

        task_details = []

        for task in tasks:

            tasks_count += 1

            start_index = (page - 1) * ACTIVITIES_PER_PAGE
            end_index = page * ACTIVITIES_PER_PAGE

            if start_index < tasks_count <= end_index:

                cost_list = []
                costs_intro_text = '\n• Use: '
                for cost in task.costs:
                    cost_list.append(f'__{format_number(cost['amount'])}__ {cost['item'].capitalize()}')

                for energy_cost in task.energy_costs:
                    cost_list.append(f'__{format_number(energy_cost['amount'])}__ {energy_cost['energy'].capitalize()}')

                cost_text = costs_intro_text + ('\n' if len(cost_list) > 1 else '') + '\n'.join(cost_list)

                output_list = []
                outputs_intro_text = '\n• Gain: '
                for output in task.outputs:
                    output_list.append(f'__{format_number(output['amount'])}__ {output['item'].capitalize()}')

                output_text = outputs_intro_text + ('\n' if len(output_list) > 1 else '') + '\n'.join(output_list)

                task_details.append(
                    f"**{task.name}**"
                    f"\n*{task.description}*"
                    f"{cost_text}"
                    f"{output_text}"
                )

        pages = max(1, math.ceil(tasks_count / TASKS_PER_PAGE))

        embed = discord.Embed(
            title=f"📋 Available Tasks - Page {page}/{pages}",
            description="Complete a task, unlike activities this is instant.",
            color=embed_color
        )

        if player.current_activity:
            activity_name = player.current_activity.name.lower()
            embed.set_thumbnail(url=f"https://raw.githubusercontent.com/NicknameAlwaystaken/incremental-beggars-ascension/refs/heads/main/images/activity/{activity_name}.png")

        if player.current_location:
            location_png = player.current_location.icon_png
            location_name = player.current_location.name

            embed.set_footer(text=location_name,icon_url=f"https://raw.githubusercontent.com/NicknameAlwaystaken/incremental-beggars-ascension/refs/heads/main/images/location/{location_png}.png")

        spacing_character = " "
        padding_amount = 25
        full_bar = "🟦"
        empty_bar = "⬜"

        formatted_items = []
        for item in player.items.values():
            bars_to_fill = int(((item.amount / item.capacity) * 100) // 10)
            item_bar = f'  {full_bar * bars_to_fill}' + f'{empty_bar * (10 - bars_to_fill)}'
            last_gained = f"  (+{format_number(item.last_gained)})" if item.last_gained > 0 else ''
            item_text = f"{item.name.capitalize()}: {format_number(item.amount)}/{format_number(item.capacity)}{last_gained}"

            formatted_items.append(f"`{item_text + (spacing_character * (padding_amount - len(item_text)))} {item_bar}`")

        embed.add_field(name="🎒 Items", value='\n'.join(formatted_items), inline=False)

        embed.add_field(name='', value='\n\n'.join(task_details), inline=False)
        return embed

    def format_upgrade_text(self, upgrade:  Upgrade):
        formatted_text = ''
        effects_text = []
        for effect_key, effect in upgrade.effects.items():
            amount = effect['modifier_value']  # example 1.5
            modifier_type = effect['modifier_type']  # example multiplier

            material_type, material_modifier = effect_key.split('.')  # example coin.gain
            modifier_type_text = modifier_type

            material_modifier_text = material_modifier

            if material_modifier == "capacity":
                material_modifier_text = 'max capacity'

            elif material_modifier == "max_purchases":
                material_modifier_text = 'max purchases'

            if modifier_type_text == "multiplier":
                modifier_type_text = "multiply"

            modifier_symbol = ''
            if modifier_type == 'increase':
                modifier_symbol = '+'

            if modifier_type == 'multiplier':
                modifier_symbol = 'x'

            effects_text.append(f'{modifier_type_text} __{material_type.capitalize()}__ **{material_modifier_text}** by `{modifier_symbol}{format_number(amount)}`')

        if effects_text:
            effects_intro = '• Effects: ' + ('\n' if len(effects_text) > 1 else '')
            formatted_text = f'\n{effects_intro}' + '\n'.join(effects_text)

        if upgrade.unlocks:
            formatted_text += '\n• Unlocks: `'
            formatted_text += '`, `'.join(upgrade.unlocks)
            formatted_text += '`'

        if upgrade.unlock_conditions:
            for condition in upgrade.unlock_conditions:
                formatted_text += '\n' + self.format_unlock_condition_text(condition)

        return formatted_text

    def format_unlock_condition_text(self, condition):
        if condition.startswith("level."):
            skill, level = condition.split(".")[1:]
            return f"• Requires {skill.capitalize()} Level {level}"
        return f"• Requires {condition}"

    def get_missing_upgrades_filtered_by_location(self, player: Player) -> list[tuple[Upgrade, int]]:
        missing_upgrades: list[tuple[Upgrade, int]] = self.get_missing_upgrades(player)
        if player.current_location:
            return [upgrade for upgrade in missing_upgrades if upgrade[0].id in player.current_location.upgrades]
        return missing_upgrades

    def get_missing_upgrades(self, player) -> list[tuple[Upgrade, int]]:
        missing_upgrades = []
        upgrades_list = self.get_upgrades()
        for id, upgrade in upgrades_list.items():
            if id in player.upgrades:
                upgrades_left = player.upgrades[id].max_purchases - player.upgrades[id].count
            else:
                upgrades_left = upgrade.max_purchases

            if upgrades_left > 0:
                missing_upgrades.append((upgrade, int(upgrades_left)))

        return missing_upgrades

    def get_available_activities(self, player: Player) -> list[tuple[str, Activity]]:
        activities_list = []
        for activity in self.activities.values():
            if player.current_location:
                if activity.id not in player.current_location.activities:
                    continue;
            button_type = "enabled"
            if activity.unlock_conditions:
                list_of_preshown_conditions = PRESHOW_BASIC_UNLOCKS
                if not all(condition in list_of_preshown_conditions for condition in activity.unlock_conditions):
                    if not all(condition in player.unlock_conditions for condition in activity.unlock_conditions):
                        continue
                else:
                    if not all(condition in player.unlock_conditions for condition in activity.unlock_conditions):
                        button_type = "disabled"

            activities_list.append((button_type, activity))

        return activities_list

    def get_available_tasks(self, player) -> list[Task]:
        tasks_list = []
        for task in self.tasks.values():
            if player.current_location:
                if task.id not in player.current_location.tasks:
                    continue;

            if task.unlock_conditions:
                list_of_preshown_conditions = PRESHOW_BASIC_UNLOCKS
                if not all(condition in list_of_preshown_conditions for condition in task.unlock_conditions):
                    if not all(condition in player.unlock_conditions for condition in task.unlock_conditions):
                        continue

            tasks_list.append(task)

        return tasks_list

    def satisfies_unlock_conditions(self, player: Player, conditions: list) -> bool:
        for condition in conditions:
            if condition.startswith('level.'):
                _, skill_name, required_level = condition.split('.')

                skill = next((s for s in player.skills.values() if s.name.lower() == skill_name.lower()), None)

                if not skill or skill.current_level < int(required_level):
                    return False
                return True

            elif condition.startswith('energy.'):
                pass
            elif condition.startswith('gold.'):
                pass

        if all(condition in player.unlock_conditions for condition in conditions):
            return True
        return False

    async def save_channels_to_db(self):
        async with aiosqlite.connect(SERVER_DB_LOCATION) as db:
            for server_id, values in self.allowed_channels.items():
                server_name = values["name"]
                channels = values["channels"]
                async with db.execute('''
                SELECT server_id
                FROM servers
                WHERE server_id = ?''', (server_id,)) as cursor:
                    result = await cursor.fetchone()

                if result is None:
                    await db.execute('''
                        INSERT INTO servers (server_id, server_name)
                        VALUES (?, ?)
                    ''', (server_id, server_name))

                for channel in channels:
                    channel_id = channel["id"]
                    channel_name = channel["name"]

                    async with db.execute('''
                        SELECT channel_id
                        FROM channels
                        WHERE channel_id = ? AND server_id = ?
                    ''', (channel_id, server_id)) as cursor:
                        channel_result = await cursor.fetchone()

                        if channel_result is None:
                            await db.execute('''
                                INSERT INTO channels (channel_id, server_id, channel_name)
                                VALUES (?, ?, ?)
                            ''', (channel_id, server_id, channel_name))

            await db.commit()


def make_tree_sync_command(tree: CommandTree[commands.Bot]):
    @commands.command(name='sync')
    async def tree_sync(ctx):
        await tree.sync()
        await ctx.send("Tree is synchronized")
    return tree_sync


class WrongChannelError(commands.CheckFailure):
    pass
