from __future__ import annotations
from discord.ext import commands
from datetime import datetime
import discord
import aiosqlite
import math
import json
import os
from views import ShopMenuView, MainMenuView, ActivitiesMenuView
from typing import Optional, Any
from copy import deepcopy

tree = None

game_data_folder = 'game_data'

GAME_DB_LOCATION = os.path.join(game_data_folder, 'game.db')

SERVER_DB_LOCATION = os.path.join(game_data_folder, 'server.db')

MAX_MESSAGE_LENGTH = 2000

GAME_NAME = "Beggar's Ascension"

ACTIVITIES_PER_PAGE = 5

UPGRADES_PER_PAGE = 4


class Energy:
    def __init__(self, id, name, max_energy, recovery_rate=0.2):
        self.id = id
        self.name = name
        self.max_energy = max_energy
        self.base_max_energy = max_energy
        self.current_energy = max_energy
        self.recovery_rate = recovery_rate
        self.base_recovery_rate = recovery_rate
        self.energy_passive_recovery = 0
        self.recovering = False

    def copy(self):
        new_energy = Energy(
            id=self.id,
            name=self.name,
            max_energy=self.max_energy,
            recovery_rate=self.recovery_rate
        )

        return new_energy

    def is_not_full(self):
        return self.max_energy > self.current_energy

    def passive_recovery(self, seconds):
        if self.energy_passive_recovery > 0:
            self.current_energy = min((self.energy_passive_recovery * seconds), self.max_energy)

    def recover(self, seconds):
        self.passive_recovery(seconds)
        recover_amount = seconds * self.recovery_rate
        start_energy = self.current_energy

        self.current_energy = min(self.current_energy + recover_amount, self.max_energy)

        if self.current_energy == self.max_energy:
            self.recovering = False

        recovered_amount = self.current_energy - start_energy

        seconds_used = recovered_amount / self.recovery_rate

        return seconds_used

    def deplete(self, amount):
        start_energy = self.current_energy
        self.current_energy = max(self.current_energy - amount, 0)
        if self.current_energy == 0:
            self.recovering = True

        # return amount of used from amount
        return start_energy - self.current_energy

    def __str__(self):
        return f"Energy: {format_number(self.current_energy)}/{format_number(self.max_energy)} - Recovery Rate: {format_number(self.base_recovery_rate)}" \
            f"{f' `+{format_number(self.recovery_rate - self.base_recovery_rate)}`' if self.recovery_rate > self.base_recovery_rate else ''}"


class Skill:
    def __init__(self, id, name, base_exp_requirement,
                 scaling_factor, description, exp_formula, max_level=50,
                 start_level=1, current_exp=0):
        self.id = id
        self.name = name
        self.base_exp_requirement = base_exp_requirement
        self.scaling_factor = scaling_factor
        self.description = description
        self.exp_formula = exp_formula
        self.max_level = max_level
        self.start_level = start_level
        self.current_level = start_level
        self.current_exp = current_exp
        self.exp_passive_gain = 0
        self.last_gained = 0
        self.effects: dict[str, dict[str, Any]] = {}

    def copy(self):
        new_skill = Skill(
            id=self.id,
            name=self.name,
            base_exp_requirement=self.base_exp_requirement,
            scaling_factor=self.scaling_factor,
            description=self.description,
            exp_formula=self.exp_formula,
            max_level=self.max_level,
            start_level=self.start_level,
            current_exp=self.current_exp
        )

        new_skill.effects = self.effects.copy()

        return new_skill

    def exp_required_for_next_level(self):
        if self.current_level >= self.max_level:
            return 0

        return self.base_exp_requirement * (self.scaling_factor ** (self.current_level - self.start_level))

    def add_experience(self, experience_amount):
        levelled_up = False

        if self.current_level >= self.max_level:
            return False

        self.current_exp += experience_amount

        while self.current_level < self.max_level and self.current_exp >= self.exp_required_for_next_level():
            self.current_level += 1
            levelled_up = True

        return levelled_up

    def passive_gain(self, seconds):
        if self.exp_passive_gain > 0:
            self.add_experience(self.exp_passive_gain * seconds)

    def __str__(self):
        last_gained_text = f' (+{format_number(self.last_gained)})' if self.last_gained > 0 else ''
        return f'{self.name}: Level {self.current_level}/{self.max_level} - Exp: {format_number(self.current_exp)}/{format_number(self.exp_required_for_next_level())}' \
            f'{last_gained_text}'


class Activity:
    def __init__(self, id: int, name: str, icon: str,
                 output_item: str, output_amount: float,
                 energy_type: str,
                 energy_drain_rate: float,
                 skill: Optional[Skill],
                 skill_exp_rate: float,
                 unlock_conditions: list[str], description: str,
                 status_description: str):
        self.id = id
        self.name = name
        self.icon = icon
        self.output_item = output_item
        self.output_amount = output_amount
        self.energy_type = energy_type
        self.energy_drain_rate = energy_drain_rate
        self.skill = skill
        self.skill_exp_rate = skill_exp_rate
        self.unlock_conditions = unlock_conditions
        self.description = description
        self.status_description = status_description

    def copy(self):
        new_activity = Activity(
            id=self.id,
            name=self.name,
            icon=self.icon,
            output_item=self.output_item,
            output_amount=self.output_amount,
            energy_type=self.energy_type,
            energy_drain_rate=self.energy_drain_rate,
            skill=self.skill,
            skill_exp_rate=self.skill_exp_rate,
            unlock_conditions=self.unlock_conditions[:],
            description=self.description,
            status_description=self.status_description
        )

        return new_activity

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
        self.currency_passive_gain = 0

    def copy(self):
        new_currency = Currency(
            self.id,
            self.name,
            self.capacity
        )

        new_currency.amount = self.amount
        new_currency.base_capacity = self.base_capacity
        new_currency.last_gained = self.last_gained

        return new_currency

    def set_amount(self, amount: float):
        self.amount = amount

    def add_amount(self, amount: float):
        current_amount = self.amount
        self.amount += amount
        self.amount = min(self.amount, self.capacity)
        self.last_gained = self.amount - current_amount

    def passive_gain(self, seconds):
        if self.currency_passive_gain > 0:
            self.add_amount(seconds * self.currency_passive_gain)

    def __str__(self):
        return f"{self.name}: {format_number(self.amount)}/{format_number(self.capacity)} " \
            f"{f'(+{format_number(self.last_gained)})' if self.last_gained > 0 else ''}"


class Upgrade:
    def __init__(self, id, name, cost_material, cost,
                 max_purchases, description):
        self.id = id
        self.name = name
        self.cost_material = cost_material
        self.cost = cost
        self.count = 1
        self.max_purchases = max_purchases
        self.unlock_conditions = []
        self.unlocks = []
        self.description = description
        self.effects: dict[str, dict[str, Any]] = {}

    def copy(self):
        new_upgrade = Upgrade(
            self.id,
            self.name,
            self.cost_material,
            self.cost,
            self.max_purchases,
            self.description
        )

        new_upgrade.unlock_conditions = self.unlock_conditions[:]
        new_upgrade.unlocks = self.unlocks[:]
        new_upgrade.effects = self.effects.copy()

        return new_upgrade

    def __str__(self):
        return f'{self.name if self.count == 1 else self.name + " __x" + str(self.count) + "__"}'


class Player:
    def __init__(self, player_id: int, display_name: str):
        self.id = player_id
        self.title = 'Beggar'
        self.display_name = display_name
        self.currencies: dict[int, Currency] = {}
        self.upgrades: dict[int, Upgrade] = {}
        self.skills: dict[int, Skill] = {}
        self.energies: dict[int, Energy] = {}
        self.stat_modifiers: dict[str, dict[str, float]] = {}
        self.unlock_conditions = []
        self.last_update_time = datetime.now()
        self.current_activity: Optional[Activity] = None
        self.time_since_last_update = 0
        self.start_date = datetime.now()

    def add_skill(self, skill: Skill):
        self.skills[skill.id] = skill

    def buy_upgrade(self, upgrade:  Upgrade, count=1):
        new_upgrade = upgrade.copy()
        material_type = new_upgrade.cost_material
        cost = new_upgrade.cost

        currency = next((currency for currency in self.currencies.values() if currency.name == material_type), None)

        if currency and currency.amount >= cost * count:
            if upgrade.id in self.upgrades:
                owned_upgrade = self.upgrades[upgrade.id]
                if owned_upgrade.count + count <= owned_upgrade.max_purchases:
                    self.add_upgrade(new_upgrade, count)
                    currency.amount -= cost
            else:
                if count <= upgrade.max_purchases:
                    self.add_upgrade(upgrade, count)
                    currency.amount -= cost

    def add_energy(self, energy: Energy):
        energy_id = energy.id
        if energy_id not in self.energies:
            self.energies[energy_id] = energy

    def add_currency(self, currency: Currency):
        currency_id = currency.id
        if currency_id not in self.currencies:
            self.currencies[currency_id] = currency

    def add_upgrade(self, upgrade:  Upgrade, count=1):
        if count < 1:
            return

        new_upgrade = upgrade.copy()
        upgrade_id = new_upgrade.id
        if upgrade_id in self.upgrades:
            self.upgrades[upgrade_id].count += count
        else:
            new_upgrade.count = count
            self.upgrades[upgrade_id] = new_upgrade

        self.update_unlock_conditions()

    def update_unlock_conditions(self):
        self.unlock_conditions = []

        for upgrade in self.upgrades.values():
            if upgrade.unlocks:
                self.unlock_conditions.extend(upgrade.unlocks)

    def recalculate_modifiers(self):
        self.stat_modifiers = {}

        priority_upgrades = [
            upgrade for upgrade in self.upgrades.values()
            if any(effect_key.split('.')[1] == "effects" for effect_key in upgrade.effects.keys())
        ]

        for upgrade in priority_upgrades:
            for stat, effect in upgrade.effects.items():
                modifier_type = effect['modifier_type']
                modifier_value = effect['modifier_value']

                for _ in range(upgrade.count):
                    if stat not in self.stat_modifiers:
                        self.stat_modifiers[stat] = {'increase': 0, 'multiplier': 1.0}

                    if modifier_type == 'multiplier':
                        self.stat_modifiers[stat]['multiplier'] *= modifier_value

                    if modifier_type == 'increase':
                        self.stat_modifiers[stat]['increase'] += modifier_value

        self.apply_upgrade_modifiers()

        # Skills improving upgrades
        for skill in self.skills.values():
            for stat, effect in skill.effects.items():
                modifier_type = effect['modifier_type']
                modifier_value = effect['modifier_value']

                effect_count = skill.current_level - skill.start_level

                for _ in range(effect_count):
                    if stat not in self.stat_modifiers:
                        self.stat_modifiers[stat] = {'increase': 0, 'multiplier': 1.0}

                    if modifier_type == 'multiplier':
                        self.stat_modifiers[stat]['multiplier'] *= modifier_value

                    if modifier_type == 'increase':
                        self.stat_modifiers[stat]['increase'] += modifier_value

        for upgrade in self.upgrades.values():
            if upgrade not in priority_upgrades:
                for stat, effect in upgrade.effects.items():
                    modifier_type = effect['modifier_type']
                    modifier_value = effect['modifier_value']

                    for _ in range(upgrade.count):
                        if stat not in self.stat_modifiers:
                            self.stat_modifiers[stat] = {'increase': 0, 'multiplier': 1.0}

                        if modifier_type == 'multiplier':
                            self.stat_modifiers[stat]['multiplier'] *= modifier_value

                        if modifier_type == 'increase':
                            self.stat_modifiers[stat]['increase'] += modifier_value

    def apply_upgrade_modifiers(self):
        for upgrade in self.upgrades.values():
            for key, stat_modifier in self.stat_modifiers.items():
                if key.startswith(upgrade.name.lower()):
                    upgrade_name, attribute = key.split('.')

                    if attribute == 'effects':
                        upgrade_to_change = next((upgrade for upgrade in self.upgrades.values() if upgrade.name.lower() == upgrade_name.lower()), None)
                        effects_dict = getattr(upgrade_to_change, attribute)

                        for effect in effects_dict.values():
                            if 'modifier_value' in effect:
                                modifier_value = effect['modifier_value']

                                new_value = (modifier_value + stat_modifier['increase']) * stat_modifier['multiplier']

                                effect['modifier_value'] = new_value

                                setattr(upgrade_to_change, attribute, effects_dict)

                    elif hasattr(upgrade, attribute):
                        upgrade_attribute = getattr(upgrade, attribute)

                        new_value = (upgrade_attribute + stat_modifier['increase']) * stat_modifier['multiplier']

                        setattr(upgrade, attribute, new_value)

    def apply_energy_modifiers(self):
        for energy in self.energies.values():
            for key, stat_modifier in self.stat_modifiers.items():
                if key.startswith(energy.name.lower()):
                    _, attribute = key.split('.')

                    if hasattr(energy, attribute):
                        energy_attribute = getattr(energy, attribute)

                        new_value = (energy_attribute + stat_modifier['increase']) * stat_modifier['multiplier']

                        setattr(energy, attribute, new_value)

    def apply_currency_modifiers(self):
        for currency in self.currencies.values():
            for key, stat_modifier in self.stat_modifiers.items():
                if key.startswith(currency.name):
                    _, attribute = key.split('.')

                    if hasattr(currency, attribute):
                        currency_attribute = getattr(currency, attribute)

                        new_value = (currency_attribute + stat_modifier['increase']) * stat_modifier['multiplier']

                        setattr(currency, attribute, new_value)

    def change_activity(self, activity: Activity):
        self.update(datetime.now())

        self.current_activity = activity

    def recover_energy(self, energy: Energy, activity_steps):
        recover_amount = energy.recover(activity_steps)
        return recover_amount

    def deplete_energy(self, energy: Energy, activity_steps):
        deplete_amount = energy.deplete(activity_steps)

        if energy.name.lower() == 'energy':
            self.skills[0].add_experience(deplete_amount)

        return deplete_amount

    def update(self, current_time):
        if not self.energies:
            return

        activity_steps = (current_time - self.last_update_time).total_seconds()

        if activity_steps < 1:
            return

        min_activity_step = 1e-5

        base_energy = self.energies[0]
        stamina_level = self.skills[0].current_level

        current_skills_exp = {skill.id: skill.current_exp for skill in self.skills.values()}

        current_currencies_amount = {currency.id: currency.amount for currency in self.currencies.values()}

        for currency in self.currencies.values():
            currency.passive_gain(activity_steps)

        for skill in self.skills.values():
            skill.passive_gain(activity_steps)

        if self.current_activity:
            current_activity = self.current_activity
            output_amount = current_activity.output_amount

            player_currency = next((currency for currency in self.currencies.values() if currency.name == current_activity.output_item), None)

            player_energy = next((energy for energy in self.energies.values() if current_activity.energy_type.lower() == energy.name.lower()), None)

            activity_skill = next((skill for skill in self.skills.values() if current_activity.skill and current_activity.skill.name.lower() == skill.name.lower()), current_activity.skill)

            if not player_energy:
                return

            while activity_steps > 0:
                if activity_steps < min_activity_step:
                    break

                if player_energy.recovering:
                    activity_steps -= self.recover_energy(player_energy, activity_steps)
                else:
                    for energy in self.energies.values():
                        energy.passive_recovery(activity_steps)
                    energy_to_use = min(player_energy.current_energy, activity_steps * current_activity.energy_drain_rate)

                    activity_count = energy_to_use / current_activity.energy_drain_rate
                    activity_steps -= activity_count

                    amount_to_add = activity_count * output_amount

                    self.deplete_energy(player_energy, energy_to_use)

                    if activity_skill:
                        if activity_skill.id not in self.skills:
                            self.skills[activity_skill.id] = activity_skill.copy()
                            activity_skill = self.skills[activity_skill.id]

                        activity_skill.add_experience(current_activity.skill_exp_rate * activity_count)

                    if player_currency:
                        if player_currency.name in self.stat_modifiers:
                            currency_modifier = self.stat_modifiers[player_currency.name]
                            amount_to_add *= currency_modifier['multiplier']

                        player_currency.add_amount(amount_to_add)

        # Recover energy if it's not idle and not full
        elif not self.current_activity and base_energy.is_not_full():
            self.recover_energy(base_energy, activity_steps)

        # Check how much currency gained
        for currency_id, currency in self.currencies.items():
            if currency_id in current_currencies_amount.keys():
                if currency.amount != current_currencies_amount[currency_id]:
                    currency.last_gained = currency.amount - current_currencies_amount[currency_id]
            else:
                currency.last_gained = currency.amount

        # Check how much skill exp gained
        for skill_id, skill in self.skills.items():
            if skill_id in current_skills_exp.keys():
                skill.last_gained = skill.current_exp - current_skills_exp[skill_id]
            else:
                skill.last_gained = skill.current_exp

        new_stamina_level = self.skills[0].current_level
        if stamina_level < new_stamina_level:
            self.energies[0].max_energy = new_stamina_level

        self.time_since_last_update = (current_time - self.last_update_time).total_seconds()
        self.last_update_time = current_time

    def __str__(self):

        upgrades = 'Upgrades: ' + ' ,'.join([str(upgrade) for upgrade in self.upgrades.values()]) + '\n'

        return f'{self.title}: {self.display_name}\n' + \
            f'{upgrades if self.upgrades else ''}'


class WrongChannelError(commands.CheckFailure):
    pass


class IncrementalGameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players: dict[int, Player] = {}
        self.upgrades: dict[int,  Upgrade] = {}
        self.activities: dict[int, Activity] = {}
        self.skills: dict[int, Skill] = {}
        self.energies: dict[int, Energy] = {}
        self.currencies: dict[int, Currency] = {}
        self.views: dict[int, discord.ui.View] = {}
        self.allowed_channels = {}

        self.initialized = False

        self.play = commands.check(self.is_allowed_channel)(self.play)

    def initialize(self):
        self.initialized = True

    def get_energies(self):
        return {id: energy.copy() for id, energy in self.energies.items()}

    def get_upgrades(self):
        return {id: upgrade.copy() for id, upgrade in self.upgrades.items()}

    def get_activities(self):
        return {id: activity.copy() for id, activity in self.activities.items()}

    def get_skills(self):
        return {id: skill.copy() for id, skill in self.skills.items()}

    def get_currencies(self):
        return {id: currency.copy() for id, currency in self.currencies.items()}

    async def is_allowed_channel(self, ctx):
        server_id = ctx.guild.id
        channel_id = ctx.channel.id

        is_allowed = server_id in self.allowed_channels and any(channel["id"] == channel_id for channel in self.allowed_channels[server_id]["channels"])

        if not is_allowed:
            # Raise a specific error if the check fails due to channel restrictions
            raise WrongChannelError("You cannot use this command in this channel. Please use it in an allowed channel.")

        return True

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, WrongChannelError):
            await ctx.send("You cannot use this command in this channel. Please use it in an allowed channel.", ephemeral=True)

        elif isinstance(error, commands.CheckFailure):
            await ctx.send("You don't have permissions to use this command.", ephemeral=True)
        else:
            raise error

    # Command to send a message with the button
    @commands.hybrid_command(name='add_channel', with_app_command=True)
    async def add_channel(self, ctx):
        """Add this channel for this bot"""
        if not self.initialized:
            print("Not done initializing!")
            return

        channel_id = ctx.channel.id
        server_id = ctx.guild.id

        if server_id not in self.allowed_channels:
            self.allowed_channels[server_id] = {"name": ctx.guild.name, "channels": []}

        self.allowed_channels[server_id]["channels"].append({"id": channel_id, "name": ctx.channel.name})

        print(self.allowed_channels)

        await self.save_channels_to_db()

    @commands.command(name='levelup')
    async def levelup(self, ctx, *args):
        if not self.initialized:
            print("Not done initializing!")
            return

        if len(args) != 1:
            return

        skill_name = args[0]

        user_id = ctx.author.id
        player = await self.get_player(user_id)

        skill = next((skill for skill in self.get_skills().values() if skill.name.lower() == skill_name.lower()), None)

        if player and skill:
            if skill.id not in player.skills:
                player.skills[skill.id] = skill
            else:
                skill = player.skills[skill.id]

            skill.add_experience(skill.exp_required_for_next_level() - skill.current_exp)
            await self.update_player(player)

    @commands.command(name='addexp')
    async def addexp(self, ctx, *args):
        if not self.initialized:
            print("Not done initializing!")
            return

        if len(args) != 2:
            return

        skill_name, experience_amount = args

        user_id = ctx.author.id
        player = await self.get_player(user_id)

        skill = next((skill for skill in self.get_skills().values() if skill.name.lower() == skill_name.lower()), None)

        if player and skill:
            if skill.id not in player.skills:
                player.skills[skill.id] = skill
            else:
                skill = player.skills[skill.id]

            skill.add_experience(int(experience_amount))
            await self.update_player(player)

    # Command to send a message with the button
    @commands.hybrid_command(name='play', with_app_command=True)
    async def play(self, ctx):
        """Interactive play command"""
        if not self.initialized:
            print("Not done initializing!")
            return

        user_id = ctx.author.id
        player = await self.get_player(user_id)
        view = MainMenuView(self, user_id)

        if not player:
            view.create_register_menu()
            register_message = "You have not registered yet!" \
                "\nGame offers content up to **level 10** of skills."\
                "\n**WARNING** Game is still in development so your progress"\
                " will be reset until full version release!"
            message = await ctx.send(content=register_message, view=view)
            self.views[message.id] = view
        else:
            await self.update_player(player)
            message = await ctx.send(content='', embed=self.player_stats_embed_message(player), view=view)
            self.views[message.id] = view

    async def shop_menu_callback(self, interaction: discord.Interaction, page=1):
        user = interaction.user
        if not await self._is_valid_interaction(interaction):
            return

        player = await self.get_player(user.id)
        if player:
            await self.update_player(player)
            if page < 1:
                page = 1
            view = ShopMenuView(self, user.id, player, UPGRADES_PER_PAGE, page)
            await interaction.response.edit_message(content='', embed=self.player_shop_embed_message(player, page), view=view)

    async def update_callback(self, interaction: discord.Interaction):
        user = interaction.user
        if not await self._is_valid_interaction(interaction):
            return

        player = await self.get_player(user.id)
        if player:
            await self.update_player(player)

    async def main_menu_callback(self, interaction: discord.Interaction):
        user = interaction.user
        if not await self._is_valid_interaction(interaction):
            return

        player = await self.get_player(user.id)
        if player:
            await self.update_player(player)
            view = MainMenuView(self, user.id)
            await interaction.response.edit_message(content='', embed=self.player_stats_embed_message(player), view=view)

    async def activities_menu_callback(self, interaction: discord.Interaction, page=1):
        user = interaction.user
        if not await self._is_valid_interaction(interaction):
            return

        player = await self.get_player(user.id)
        if player:
            await self.update_player(player)
            if page < 1:
                page = 1
            view = ActivitiesMenuView(self, user.id, player, ACTIVITIES_PER_PAGE, page)
            await interaction.response.edit_message(content='', embed=self.player_activities_embed_message(player, page), view=view)

    async def buy_upgrade_callback(self, interaction: discord.Interaction, upgrade: Upgrade, page=1):
        user = interaction.user
        if not await self._is_valid_interaction(interaction):
            return

        player = await self.get_player(user.id)

        if player:
            player.buy_upgrade(upgrade)
            self.recalculate_player_modifiers(player)
            await self.update_player(player)
            view = ShopMenuView(self, user.id, player, UPGRADES_PER_PAGE, page)
            await interaction.response.edit_message(content='', embed=self.player_shop_embed_message(player, page), view=view)

    async def start_activity_callback(self, interaction: discord.Interaction, activity: Activity, page=1):
        user = interaction.user
        if not await self._is_valid_interaction(interaction):
            return

        player = await self.get_player(user.id)

        if player:
            player.change_activity(activity)
            await self.update_player(player)
            view = ActivitiesMenuView(self, user.id, player, ACTIVITIES_PER_PAGE, page)
            await interaction.response.edit_message(content='', embed=self.player_activities_embed_message(player, page), view=view)

    async def register_callback(self, interaction: discord.Interaction):
        user = interaction.user
        if not await self._is_valid_interaction(interaction):
            return

        player = await self.get_player(int(user.id))

        if not player:
            # Register the player and update the message
            await self.register_player(int(user.id), user.display_name)
            player = await self.get_player(int(user.id))
            await self.update_player(player)
            view = MainMenuView(self, user.id)
            await interaction.response.edit_message(content='', embed=self.player_stats_embed_message(player), view=view)

    async def _is_valid_interaction(self, interaction: discord.Interaction):
        view = self.views.get(interaction.message.id)

        if view and not view.is_owner(interaction):
            return False
        return True

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
                    unlock_conditions = activity[9]
                    if unlock_conditions is None or unlock_conditions == "":
                        unlock_conditions = []
                    else:
                        unlock_conditions = unlock_conditions.split(',')

                    self.activities[activity[0]] = Activity(
                            id=activity[0],
                            name=activity[1],
                            icon=activity[2],
                            output_item=activity[3],
                            output_amount=activity[4],
                            energy_type=activity[5],
                            energy_drain_rate=activity[6],
                            skill=skill,
                            skill_exp_rate=activity[8],
                            unlock_conditions=unlock_conditions,
                            description=activity[10],
                            status_description=activity[11]
                        )

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
                    player = self.players[int(player_id)]
                    currency = self.currencies[currency_id].copy()
                    player.add_currency(currency)
                    currency.set_amount(amount)

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

    async def get_player_from_db(self, player_id):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            async with db.execute('''
            SELECT player_id, player_display_name, start_date, last_update_time
            FROM players
            WHERE player_id = ?''', (player_id,)) as cursor:

                found_player = await cursor.fetchone()

                if found_player:
                    player_id, display_name, start_date, last_update_time = found_player
                    player = Player(player_id, display_name)
                    player.last_update_time = datetime.fromisoformat(last_update_time)
                    player.start_date = datetime.fromisoformat(start_date)
                    self.players[int(player_id)] = player
                    await self.get_player_upgrades_from_db(player_id)
                    await self.get_player_currencies_from_db(player_id)
                    await self.get_player_skills_from_db(player_id)
                    await self.get_player_activities_from_db(player_id)
                    await self.get_player_energies_from_db(player_id)
                    self.recalculate_player_modifiers(player)

                    await self.update_player(player)
                    return player
                else:
                    return None

    async def get_player(self, player_id: int):
        if player_id not in self.players:
            player = await self.get_player_from_db(player_id)
            if player:
                self.players[int(player_id)] = player
                return player
            else:
                return None
        else:
            await self.player_to_database_update(player_id)
            return self.players[int(player_id)]

    def recalculate_player_modifiers(self, player: Player):

        # reset currency capacity
        for currency_id, player_currency in player.currencies.items():
            baseline_currency = next((currency for currency in self.get_currencies().values() if currency_id == currency.id), None)

            if baseline_currency:
                player_currency.capacity = baseline_currency.capacity

        # reset upgrade max_purchases
        for upgrade_id, player_upgrade in player.upgrades.items():
            baseline_upgrade = next((upgrade for upgrade in self.get_upgrades().values() if upgrade_id == upgrade.id), None)

            if baseline_upgrade:
                player_upgrade.max_purchases = baseline_upgrade.max_purchases
                player_upgrade.effects = deepcopy(baseline_upgrade.effects)

        player.recalculate_modifiers()
        player.apply_upgrade_modifiers()
        player.apply_currency_modifiers()
        player.apply_energy_modifiers()

    async def update_player(self, player):
        current_time = datetime.now()
        player.update(current_time)

        self.recalculate_player_modifiers(player)

        await self.player_to_database_update(player.id)

    async def player_to_database_update(self, player_id):
        async with aiosqlite.connect(GAME_DB_LOCATION) as db:
            player = self.players[int(player_id)]
            player_upgrades = [(id, upgrade.count) for id, upgrade in player.upgrades.items()]
            player_currencies = [(id, currency.amount) for id, currency in player.currencies.items()]
            player_activity = player.current_activity
            player_skills = [(id, skill.current_level, skill.current_exp) for id, skill in player.skills.items()]
            player_energies = [(id, energy.current_energy) for id, energy in player.energies.items()]

            await db.execute('BEGIN')

            await self.update_player_upgrades(db, player_id, player_upgrades)
            await self.update_player_currencies(db, player_id, player_currencies)
            await self.update_player_skills(db, player_id, player_skills)
            await self.update_player_activities(db, player_id, player_activity)
            await self.update_player_energies(db, player_id, player_energies)
            await self.update_player_data(db, player_id, player)

            await db.commit()

    async def update_player_upgrades(self, db, player_id, player_upgrades):
        placeholders_upgrades = ', '.join('?' for _ in player_upgrades)

        # Clear all upgrades that player doesn't have anymore
        if player_upgrades:
            query = f"DELETE FROM player_upgrades WHERE player_id = ? AND upgrade_id NOT IN ({placeholders_upgrades})"
            params_upgrades = [player_id] + [upgrade[0] for upgrade in player_upgrades]
            await db.execute(query, params_upgrades)
        else:
            await db.execute("DELETE FROM player_upgrades WHERE player_id = ?", (player_id,))

        # Add or update changed upgrades
        for player_upgrade in player_upgrades:
            await db.execute('''
                INSERT OR REPLACE INTO player_upgrades (player_id, upgrade_id, count)
                VALUES (?, ?, ?)
            ''', (player_id, player_upgrade[0], player_upgrade[1]))

    async def update_player_currencies(self, db, player_id, player_currencies):
        placeholders_currencies = ', '.join('?' for _ in player_currencies)

        # Clear all currencies that player doesn't have anymore
        if player_currencies:
            query = f"DELETE FROM player_currencies WHERE player_id = ? AND currency_id NOT IN ({placeholders_currencies})"
            params_currencies = [player_id] + [currency[0] for currency in player_currencies]
            await db.execute(query, params_currencies)
        else:
            await db.execute("DELETE FROM player_currencies WHERE player_id = ?", (player_id,))

        # Add or update changed currencies
        for player_currency in player_currencies:
            await db.execute('''
                INSERT OR REPLACE INTO player_currencies (player_id, currency_id, amount)
                VALUES (?, ?, ?)
            ''', (player_id, player_currency[0], player_currency[1]))

    async def update_player_energies(self, db, player_id, player_energies):
        placeholders_energies = ', '.join('?' for _ in player_energies)

        # Clear all energies that the player doesn't have anymore
        if player_energies:
            query = f"DELETE FROM player_energies WHERE player_id = ? AND energy_id NOT IN ({placeholders_energies})"
            params_energies = [player_id] + [energy[0] for energy in player_energies]
            await db.execute(query, params_energies)
        else:
            await db.execute("DELETE FROM player_energies WHERE player_id = ?", (player_id,))

        # Add or update the player's energies
        for energy_id, current_energy in player_energies:
            await db.execute('''
                INSERT OR REPLACE INTO player_energies (player_id, energy_id, current_energy)
                VALUES (?, ?, ?)
            ''', (player_id, energy_id, current_energy))

    async def update_player_skills(self, db, player_id, player_skills):
        placeholders_skills = ', '.join('?' for _ in player_skills)

        # Clear all skills that the player doesn't have anymore
        if player_skills:
            query = f"DELETE FROM player_skills WHERE player_id = ? AND skill_id NOT IN ({placeholders_skills})"
            params_skills = [player_id] + [skill[0] for skill in player_skills]
            await db.execute(query, params_skills)
        else:
            await db.execute("DELETE FROM player_skills WHERE player_id = ?", (player_id,))

        # Add or update the player's skills
        for skill_id, current_level, current_exp in player_skills:
            await db.execute('''
                INSERT OR REPLACE INTO player_skills (player_id, skill_id, current_level, current_exp)
                VALUES (?, ?, ?, ?)
            ''', (player_id, skill_id, current_level, current_exp))

    async def update_player_activities(self, db, player_id, player_activity):
        # Clear all activities that player doesn't have anymore
        if player_activity:
            query = "DELETE FROM player_activities WHERE player_id = ? AND activity_id != ?"
            params_activities = [player_id, player_activity.id]
            await db.execute(query, params_activities)
        else:
            await db.execute("DELETE FROM player_activities WHERE player_id = ?", (player_id,))

        # Add or update changed activities
        if player_activity:
            await db.execute('''
                INSERT OR REPLACE INTO player_activities (player_id, activity_id)
                VALUES (?, ?)
            ''', (player_id, player_activity.id))

    async def update_player_data(self, db, player_id, player):
        # Check if the player exists in the database
        async with db.execute('SELECT 1 FROM players WHERE player_id = ?', (player_id,)) as cursor:
            found_player = await cursor.fetchone()

        if found_player:
            await db.execute('''
            UPDATE players
            SET player_display_name = ?, start_date = ?, last_update_time = ?
            WHERE player_id == ?
            ''', (player.display_name, player.start_date, player.last_update_time, player_id))
        else:
            await db.execute('''
            INSERT INTO players (player_id, player_display_name, start_date, last_update_time)
            VALUES (?, ?, ?, ?)
            ''', (player_id, player.display_name, player.start_date, player.last_update_time))

    async def register_player(self, player_id: int, display_name: str):
        new_player = Player(player_id, display_name)
        new_player.add_currency(self.currencies[0].copy())
        new_player.add_skill(self.skills[0].copy())
        new_player.add_energy(self.energies[0].copy())
        new_player.add_upgrade(self.upgrades[0].copy())

        self.players[int(player_id)] = new_player

        self.recalculate_player_modifiers(new_player)
        await self.player_to_database_update(player_id)

    def player_stats_embed_message(self, player):
        embed_color = discord.Color.green() if player.current_activity else discord.Color.red()
        embed = discord.Embed(
            title="🎩 Player Status",
            description=f"**{player.title}**: __{player.display_name}__\nPlaytime: {format_time((datetime.now() - player.start_date).total_seconds())}\nTime passed: {format_time(player.time_since_last_update)}",
            color=embed_color
        )

        formatted_currencies = []
        for currency in player.currencies.values():
            bars_to_fill = int(((currency.amount / currency.capacity) * 100) // 10)
            currency_bar = f'  {"█" * bars_to_fill}' + f'{"░" * (10 - bars_to_fill)}'
            last_gained = f"  (+{format_number(currency.last_gained)})" if currency.last_gained > 0 else ''
            formatted_currencies.append(f"{currency.name.capitalize()}: {format_number(currency.amount)}/{format_number(currency.capacity)}{currency_bar}{last_gained}")

        embed.add_field(name="💰 Currencies", value='\n'.join(formatted_currencies), inline=False)

        if player.energies:
            energies_list = [str(energy) for energy in player.energies.values()]
            embed.add_field(name='⚡ Energies', value='\n'.join(energies_list), inline=False)

        if player.skills:
            skills_list = [str(skill) for skill in player.skills.values()]
            embed.add_field(name='🎓 Skills', value='\n'.join(skills_list), inline=False)

        player_base_energy = player.energies[0]
        recover_text = ' (Recovering energy)' if player_base_energy.recovering else ''
        if player.current_activity:
            embed.add_field(name="🏃 Current activity", value=player.current_activity.status_description + recover_text, inline=False)
        else:
            embed.add_field(name="🏃 Current activity", value='C__urrently doing nothing. Go get an activity!__' + recover_text, inline=False)

        if player.upgrades:
            embed.add_field(name="🛠️ Upgrades", value=', '.join([str(upgrade) for upgrade in player.upgrades.values()]), inline=False)

        return embed

    def player_shop_embed_message(self, player, page=1):
        embed_color = discord.Color.green() if player.current_activity else discord.Color.red()
        formatted_currencies = []
        for currency in player.currencies.values():
            formatted_currencies.append(f"{currency.name.capitalize()}: {format_number(currency.amount)}/{format_number(currency.capacity)} (+{format_number(currency.last_gained)})")

        missing_upgrades = self.get_missing_upgrades(player)

        missing_upgrades_text = []

        if page < 1:
            page = 1

        upgrades_count = 0
        if missing_upgrades:
            for upgrade, upgrades_left in missing_upgrades:
                if not self.check_conditions(player, upgrade.unlock_conditions):
                    continue
                upgrades_count += 1

                start_index = (page - 1) * UPGRADES_PER_PAGE
                end_index = page * UPGRADES_PER_PAGE

                if start_index < upgrades_count <= end_index:
                    missing_upgrades_text.append(
                        f"**{upgrade.name}**\n"
                        f"• Cost: `{upgrade.cost} {upgrade.cost_material}`\n"
                        f"• Remaining: `{upgrades_left}`"
                        f"{self.format_upgrade_text(upgrade)}"
                    )

        pages = max(1, math.ceil(upgrades_count / UPGRADES_PER_PAGE))

        embed = discord.Embed(
            title=f"🛒 Upgrade shop - Page {page}/{pages}",
            description=f"**{player.title}**: __{player.display_name}__",
            color=embed_color
        )

        embed.add_field(name="💰 Currencies", value='\n'.join(formatted_currencies), inline=False)

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

        for activity in activities:

            activities_count += 1

            start_index = (page - 1) * ACTIVITIES_PER_PAGE
            end_index = page * ACTIVITIES_PER_PAGE

            if start_index < activities_count <= end_index:
                stat_key = f"{activity.output_item}.gain"

                modifiers = player.stat_modifiers.get(stat_key, {'increase': 0, 'multiplier': 1.0})

                modified_output = (activity.output_amount + modifiers['increase']) * modifiers['multiplier']

                modified_output_text = f" `+{(modified_output - activity.output_amount):.2f}` " if modified_output - activity.output_amount > 0 else ''

                requirements_text = f"\n• Requirements: `{'`, `'.join(activity.unlock_conditions)}`" if activity.unlock_conditions else ''

                benefits_text = f"\n• Benefit: __{activity.output_amount:.2f}__ {modified_output_text}{activity.output_item.capitalize()} per second" if activity.output_item else ''

                activity_energy = next((energy for energy in self.get_energies().values() if energy and activity.energy_type and activity.energy_type.lower() == energy.name.lower()), None)

                if activity_energy:
                    drain_text = f"\n• Drain: __{format_number(activity.energy_drain_rate)}__ {activity_energy.name.capitalize()} per second"
                else:
                    drain_text = ''

                activity_exp = f'\nGains `{format_number(activity.skill_exp_rate)}` {activity.skill.name} experience per second' if activity.skill else ''

                activity_details.append(
                    f"**{activity.name}**"
                    f"\n*{activity.description}*"
                    f"{benefits_text}"
                    f"{drain_text}"
                    f"{requirements_text}"
                    f"{activity_exp}"
                )

        pages = max(1, math.ceil(activities_count / ACTIVITIES_PER_PAGE))

        embed = discord.Embed(
            title=f"🏃 Available Activities - Page {page}/{pages}",
            description="You can select an activity here and you will continously do it.",
            color=embed_color
        )

        embed.add_field(name='', value='\n\n'.join(activity_details), inline=False)
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

    def get_available_activities(self, player) -> list[Activity]:
        activities_list = []
        for activity in self.activities.values():
            if activity.unlock_conditions:
                if not all(condition in player.unlock_conditions for condition in activity.unlock_conditions):
                    continue

            activities_list.append(activity)

        return activities_list

    def check_conditions(self, player: Player, conditions: list) -> bool:

        for condition in conditions:
            if condition.startswith('level.'):
                _, skill_name, required_level = condition.split('.')

                skill = next((s for s in player.skills.values() if s.name.lower() == skill_name.lower()), None)

                if not skill or skill.current_level < int(required_level):
                    return False

            elif condition.startswith('energy.'):
                pass
            elif condition.startswith('gold.'):
                pass

        return True

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


@commands.command(name='sync')
async def tree_sync(ctx):
    global tree
    await tree.sync()  # type: ignore
    print("Tree is synchronized")


def format_time(time_in_seconds):
    seconds = int(time_in_seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    time_string = []

    if hours:
        time_string.append(f'{hours:.0f}h')

    if minutes:
        time_string.append(f'{minutes}m')

    if seconds > 0 or len(time_string) == 0:
        time_string.append(f'{seconds}s')

    return " ".join(time_string)


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


async def create_energies_table(db_location):
    async with aiosqlite.connect(db_location) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS energies (
                energy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                max_energy REAL,
                recovery_rate REAL
        )
        ''')
        await db.commit()


async def create_player_energy_table(db_location):
    async with aiosqlite.connect(db_location) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS player_energies (
                player_id INTEGER,
                energy_id INTEGER,
                current_energy REAL,
                PRIMARY KEY (player_id, energy_id),
                FOREIGN KEY (energy_id) REFERENCES energies(energy_id)
        )
        ''')
        await db.commit()


async def create_skills_table(db_location):
    async with aiosqlite.connect(db_location) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS skills (
                skill_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                start_level INTEGER NOT NULL,
                max_level INTEGER NOT NULL,
                base_exp_requirement REAL NOT NULL,
                scaling_factor REAL NOT NULL,
                exp_formula TEXT
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS skill_effects (
            id INTEGER PRIMARY KEY,
            skill_id INTEGER NOT NULL,
            stat TEXT NOT NULL,
            modifier_type TEXT NOT NULL,
            modifier_value REAL NOT NULL,
            UNIQUE (skill_id, stat, modifier_type),
            FOREIGN KEY (skill_id) REFERENCES skills (skill_id) ON DELETE CASCADE
        )
        ''')
        await db.commit()


async def create_player_skills_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS player_skills (
            player_id INTEGER NOT NULL,
            skill_id INTEGER NOT NULL,
            current_level INTEGER NOT NULL,
            current_exp REAL NOT NULL,
            PRIMARY KEY (player_id, skill_id),
            FOREIGN KEY (skill_id) REFERENCES skills(skill_id)
        )
        ''')
        await db.commit()


async def create_player_activities_table(database_location):
    async with aiosqlite.connect(database_location) as db:
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


async def create_activities_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            activity_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            icon TEXT,
            output_item TEXT NOT NULL,
            output_amount REAL NOT NULL,
            energy_type TEXT,
            energy_drain_rate REAL,
            skill TEXT,
            skill_exp_rate REAL,
            unlock_conditions TEXT,
            description TEXT,
            status_description TEXT
        )
        ''')
        await db.commit()


async def create_player_upgrades_table(database_location):
    async with aiosqlite.connect(database_location) as db:
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


async def create_upgrades_table(database_location):
    async with aiosqlite.connect(database_location) as db:
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
        CREATE TABLE IF NOT EXISTS upgrade_unlocks (
            id INTEGER PRIMARY KEY,
            upgrade_id INTEGER NOT NULL,
            condition TEXT NOT NULL,
            UNIQUE (upgrade_id, condition),
            FOREIGN KEY (upgrade_id) REFERENCES upgrades (upgrade_id) ON DELETE CASCADE
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS upgrade_effects (
            id INTEGER PRIMARY KEY,
            upgrade_id INTEGER NOT NULL,
            stat TEXT NOT NULL,
            modifier_type TEXT NOT NULL,
            modifier_value REAL NOT NULL,
            UNIQUE (upgrade_id, stat, modifier_type),
            FOREIGN KEY (upgrade_id) REFERENCES upgrades (upgrade_id) ON DELETE CASCADE
        )
        ''')

        await db.execute('''
        CREATE TABLE IF NOT EXISTS upgrade_unlock_conditions (
            upgrade_id INTEGER,
            condition TEXT,
            PRIMARY KEY (upgrade_id, condition),
            FOREIGN KEY (upgrade_id) REFERENCES upgrades (upgrade_id) ON DELETE CASCADE
        )
        ''')

        await db.commit()


async def create_player_currencies_table(database_location):
    async with aiosqlite.connect(database_location) as db:
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


async def create_currencies_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
        CREATE TABLE IF NOT EXISTS currencies (
            currency_id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            default_capacity INTEGER
        )
        ''')
        await db.commit()


async def create_items_table(database_location):
    async with aiosqlite.connect(database_location) as db:
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


async def create_player_items_table(database_location):
    async with aiosqlite.connect(database_location) as db:
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


async def create_players_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
            CREATE TABLE IF NOT EXISTS players (
                player_id INTEGER PRIMARY KEY,
                player_display_name TEXT NOT NULL,
                start_date TEXT,
                last_update_time TEXT
            )
        ''')
        await db.commit()


async def create_server_channel_table(database_location):
    async with aiosqlite.connect(database_location) as db:
        # Create a table if it doesn't exist
        await db.execute('''
            CREATE TABLE IF NOT EXISTS servers (
                server_id BIGINT PRIMARY KEY,
                server_name TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id BIGINT PRIMARY KEY,
                server_id BIGINT,
                channel_name TEXT,
                FOREIGN KEY (server_id) REFERENCES servers(server_id)
            )
        ''')
        await db.commit()


async def update_energies_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'energies.json'), encoding='utf-8') as file:
        energies_data = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for energy in energies_data:
            await db.execute('''
                INSERT OR REPLACE INTO energies (energy_id, name, max_energy, recovery_rate)
                VALUES (?, ?, ?, ?)
            ''', (energy['id'], energy['name'], energy['max_energy'], energy['recovery_rate']))
        await db.commit()


async def update_skills_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'skills.json'), encoding='utf-8') as file:
        skills_data = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for skill in skills_data:
            await db.execute('''
                INSERT OR REPLACE INTO skills (skill_id, name, description, start_level, max_level, base_exp_requirement, scaling_factor, exp_formula)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (skill['id'], skill['name'], skill['description'], skill['start_level'], skill['max_level'], skill['base_exp_requirement'], skill['scaling_factor'], skill['exp_formula']))

            if 'effects' in skill and skill['effects']:
                for stat, effect in skill['effects'].items():
                    await db.execute('''
                        INSERT OR REPLACE INTO skill_effects (
                            skill_id, stat, modifier_type, modifier_value
                        )
                        VALUES (?, ?, ?, ?)
                    ''', (
                        skill['id'], stat, effect['modifier_type'], effect['modifier_value']
                    ))

        await db.commit()


async def update_activities_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'activities.json'), encoding='utf-8') as file:
        activities = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for activity in activities:
            await db.execute('''
                INSERT OR REPLACE INTO activities (activity_id, name, icon, output_item, output_amount, energy_type, energy_drain_rate, skill, skill_exp_rate, unlock_conditions, description, status_description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (activity['id'], activity['name'], activity['icon'],
                  activity['output_item'], activity['output_amount'],
                  activity['energy_type'],
                  activity['energy_drain_rate'],
                  activity['skill'],
                  activity['skill_exp_rate'],
                  ','.join(activity['unlock_conditions']),
                  activity['description'],
                  activity['status_description']))
        await db.commit()


async def update_currencies_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'currencies.json')) as file:
        currencies = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for currency in currencies:
            await db.execute('''
                INSERT OR IGNORE INTO currencies (currency_id, name, default_capacity)
                VALUES (?, ?, ?)
            ''', (currency['id'], currency['name'], currency['capacity']))

        await db.commit()


# async def update_items_from_json_to_db(database_location):
#     with open(os.path.join(game_data_folder, 'items.json')) as file:
#         items = json.load(file)
#
#     async with aiosqlite.connect(database_location) as db:
#         for item in items:
#             item_name = item['name']
#             await db.execute('''
#                 INSERT OR IGNORE INTO items (name, default_amount, default_capacity, default_gain)
#                 VALUES (?, ?, ?, ?)
#             ''', (item_name))
#
#         await db.commit()


async def update_upgrades_from_json_to_db(database_location):
    with open(os.path.join(game_data_folder, 'upgrades.json')) as file:
        upgrades = json.load(file)

    async with aiosqlite.connect(database_location) as db:
        for upgrade in upgrades:
            await db.execute('''
                INSERT OR REPLACE INTO upgrades (upgrade_id, name,
                cost_material, cost, max_purchases,
                description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (upgrade['id'], upgrade['name'],
                  upgrade['cost_material'], upgrade['cost'],
                  upgrade['max_purchases'], upgrade['description']))

            if 'effects' in upgrade and upgrade['effects']:
                for stat, effect in upgrade['effects'].items():
                    await db.execute('''
                        INSERT OR REPLACE INTO upgrade_effects (
                            upgrade_id, stat, modifier_type, modifier_value
                        )
                        VALUES (?, ?, ?, ?)
                    ''', (
                        upgrade['id'], stat, effect['modifier_type'], effect['modifier_value']
                    ))

            if upgrade['unlocks']:
                for condition in upgrade['unlocks']:
                    async with db.execute('''
                        SELECT 1 FROM upgrade_unlocks WHERE upgrade_id = ? AND condition = ?
                    ''', (upgrade['id'], condition)) as cursor:
                        exists = await cursor.fetchone()

                    if not exists:
                        await db.execute('''
                            INSERT OR REPLACE INTO upgrade_unlocks (upgrade_id, condition)
                            VALUES (?, ?)
                        ''', (upgrade['id'], condition))

            if upgrade['unlock_conditions']:
                for condition in upgrade['unlock_conditions']:
                    async with db.execute('''
                        SELECT 1 FROM upgrade_unlock_conditions WHERE upgrade_id = ? AND condition = ?
                    ''', (upgrade['id'], condition)) as cursor:
                        exists = await cursor.fetchone()

                    if not exists:
                        await db.execute('''
                            INSERT OR REPLACE INTO upgrade_unlock_conditions (upgrade_id, condition)
                            VALUES (?, ?)
                        ''', (upgrade['id'], condition))

            await db.commit()


async def setup(bot):
    global tree
    tree = bot.tree
    bot.add_command(tree_sync)

    # create table if not exist

    await create_server_channel_table(SERVER_DB_LOCATION)

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

    await create_skills_table(GAME_DB_LOCATION)
    await update_skills_from_json_to_db(GAME_DB_LOCATION)
    await create_player_skills_table(GAME_DB_LOCATION)

    await create_energies_table(GAME_DB_LOCATION)
    await update_energies_from_json_to_db(GAME_DB_LOCATION)
    await create_player_energy_table(GAME_DB_LOCATION)

    game_cog = IncrementalGameCog(bot)
    await bot.add_cog(game_cog)

    await game_cog.get_server_channels_from_db()

    await game_cog.get_currencies_from_db()
    await game_cog.get_upgrades_from_db()
    await game_cog.get_skills_from_db()
    await game_cog.get_activities_from_db()
    await game_cog.get_energies_from_db()

    game_cog.initialize()
