from __future__ import annotations
from modules.game_features import Game
from modules.utils import format_number
from typing import Optional, Any
from datetime import datetime

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
                 output_item: Optional[Item], output_amount: float,
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


class Item:
    def __init__(self, id, name, capacity):
        self.id = id
        self.name = name
        self.amount = 0
        self.capacity = capacity
        self.base_capacity = capacity
        self.last_gained = 0
        self.item_passive_gain = 0

    def copy(self):
        new_item = Item(
            self.id,
            self.name,
            self.capacity
        )

        new_item.amount = self.amount
        new_item.base_capacity = self.base_capacity
        new_item.last_gained = self.last_gained

        return new_item

    def set_amount(self, amount: float):
        self.amount = amount

    def add_amount(self, amount: float):
        self.amount += amount

    def increase_amount(self, amount: float):
        current_amount = self.amount
        if current_amount <= self.capacity:
            self.amount += amount
            self.amount = min(self.amount, self.capacity)

        self.last_gained = self.amount - current_amount

    def passive_gain(self, seconds):
        if self.item_passive_gain > 0:
            self.increase_amount(seconds * self.item_passive_gain)

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
    def __init__(self, player_id: int, name: str, display_name: str):
        self.id = player_id
        self.title = 'Beggar'
        self.name = name
        self.display_name = display_name
        self.items: dict[int, Item] = {}
        self.upgrades: dict[int, Upgrade] = {}
        self.skills: dict[int, Skill] = {}
        self.energies: dict[int, Energy] = {}
        self.games: dict[int, Game] = {}
        self.chips = 0
        self.stat_modifiers: dict[str, dict[str, float]] = {}
        self.unlock_conditions = []
        self.last_update_time = datetime.now()
        self.current_activity: Optional[Activity] = None
        self.time_since_last_update = 0
        self.start_date = datetime.now()

    def add_skill(self, skill: Skill):
        self.skills[skill.id] = skill

    def add_game(self, game: Game):
        self.games[game.id] = game

    def buy_upgrade(self, upgrade:  Upgrade, count=1):
        new_upgrade = upgrade.copy()
        material_type = new_upgrade.cost_material
        cost = new_upgrade.cost

        item = next((item for item in self.items.values() if item.name == material_type), None)

        if item and item.amount >= cost * count:
            if upgrade.id in self.upgrades:
                owned_upgrade = self.upgrades[upgrade.id]
                if owned_upgrade.count + count <= owned_upgrade.max_purchases:
                    self.add_upgrade(new_upgrade, count)
                    item.amount -= cost
            else:
                if count <= upgrade.max_purchases:
                    self.add_upgrade(upgrade, count)
                    item.amount -= cost

    def add_energy(self, energy: Energy):
        energy_id = energy.id
        if energy_id not in self.energies:
            self.energies[energy_id] = energy

    def add_item(self, item: Item):
        item_id = item.id
        if item_id not in self.items:
            self.items[item_id] = item

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

    def apply_item_modifiers(self):
        for item in self.items.values():
            for key, stat_modifier in self.stat_modifiers.items():
                if key.startswith(item.name):
                    _, attribute = key.split('.')

                    if hasattr(item, attribute):
                        item_attribute = getattr(item, attribute)

                        new_value = (item_attribute + stat_modifier['increase']) * stat_modifier['multiplier']

                        setattr(item, attribute, new_value)

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

    def update(self, current_time: datetime):
        activity_steps = (current_time - self.last_update_time).total_seconds()

        if activity_steps < 1:
            return

        min_activity_step = 1e-5

        base_energy = self.energies[0]
        stamina_level = self.skills[0].current_level

        current_skills_exp = {skill.id: skill.current_exp for skill in self.skills.values()}

        current_items_amount = {item.id: item.amount for item in self.items.values()}

        for item in self.items.values():
            item.passive_gain(activity_steps)

        for skill in self.skills.values():
            skill.passive_gain(activity_steps)

        if self.current_activity:
            current_activity = self.current_activity
            output_amount = current_activity.output_amount

            player_item = next((item for item in self.items.values() if item.name == current_activity.output_item), None)

            player_energy = next((energy for energy in self.energies.values() if current_activity.energy_type.lower() == energy.name.lower()), None)

            activity_skill = next((skill for skill in self.skills.values() if current_activity.skill and current_activity.skill.name.lower() == skill.name.lower()), current_activity.skill)

            activity_item = next((item for item in self.items.values() if current_activity.output_item and current_activity.output_item.name.lower() == item.name.lower()), current_activity.output_item)

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

                    if activity_item:
                        if activity_item.id not in self.items:
                            self.items[activity_item.id] = activity_item.copy()
                            activity_item = self.items[activity_item.id]

                        activity_item.increase_amount(current_activity.output_amount * activity_count)

                    if player_item:
                        if player_item.name in self.stat_modifiers:
                            item_modifier = self.stat_modifiers[player_item.name]
                            amount_to_add *= item_modifier['multiplier']

                        player_item.increase_amount(amount_to_add)

        # Recover energy if it's not idle and not full
        elif not self.current_activity and base_energy.is_not_full():
            self.recover_energy(base_energy, activity_steps)

        # Check how much of item gained
        for item_id, item in self.items.items():
            if item_id in current_items_amount.keys():
                if item.amount != current_items_amount[item_id]:
                    item.last_gained = item.amount - current_items_amount[item_id]
            else:
                item.last_gained = item.amount

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
