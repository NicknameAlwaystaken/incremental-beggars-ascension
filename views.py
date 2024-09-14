import discord
from functools import partial


class BaseView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.user_id = user_id

    def is_owner(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    def add_back_button(self, callback, row=2):
        back_button = discord.ui.Button(label='Back', style=discord.ButtonStyle.primary, row=row)
        back_button.callback = callback
        self.add_item(back_button)

    def add_update_button(self, callback, row=3):
        update_button = discord.ui.Button(label='Update', style=discord.ButtonStyle.secondary, row=row)
        update_button.callback = callback
        self.add_item(update_button)

    def add_previous_button(self, callback, row=2):
        previous_button = discord.ui.Button(label='⬅️', style=discord.ButtonStyle.primary, row=row)
        previous_button.callback = callback
        self.add_item(previous_button)

    def add_next_button(self, callback, row=2):
        next_button = discord.ui.Button(label='➡️', style=discord.ButtonStyle.primary, row=row)
        next_button.callback = callback
        self.add_item(next_button)


class MainMenuView(BaseView):
    def __init__(self, cog, user_id):
        super().__init__(cog, user_id)
        self.create_main_menu()

    def create_main_menu(self):
        self.clear_items()

        # Activities button
        activities_button = discord.ui.Button(label='Activities', style=discord.ButtonStyle.primary)
        activities_button.callback = self.cog.activities_menu_callback
        self.add_item(activities_button)

        # Tasks button
        tasks_button = discord.ui.Button(label='Tasks', style=discord.ButtonStyle.primary)
        tasks_button.callback = self.cog.tasks_menu_callback
        self.add_item(tasks_button)

        # Shop button
        shop_button = discord.ui.Button(label='Shop', style=discord.ButtonStyle.primary)
        shop_button.callback = self.cog.shop_menu_callback
        self.add_item(shop_button)

        # Update button
        self.add_update_button(self.cog.main_menu_callback)

    def create_register_menu(self):
        self.clear_items()

        register_button = discord.ui.Button(label='Register', style=discord.ButtonStyle.success)
        register_button.callback = self.cog.register_callback
        self.add_item(register_button)


class ShopMenuView(BaseView):
    def __init__(self, cog, user_id, player, upgrades_per_page, page=1):
        super().__init__(cog, user_id)
        if page < 1:
            page = 1
        self.create_shop_menu(player, upgrades_per_page, page)

    def create_shop_menu(self, player, upgrades_per_page, page=1):
        self.clear_items()
        missing_upgrades = self.cog.get_missing_upgrades(player)
        upgrades_count = 0
        for upgrade, _ in missing_upgrades:
            if not self.cog.check_conditions(player, upgrade.unlock_conditions):
                continue
            upgrades_count += 1
            start_index = (page - 1) * upgrades_per_page
            end_index = page * upgrades_per_page

            if start_index < upgrades_count <= end_index:
                item = next((item for item in player.items.values() if item.name == upgrade.cost_material), None)
                button_style = discord.ButtonStyle.success if item and item.amount >= upgrade.cost else discord.ButtonStyle.secondary
                buy_button = discord.ui.Button(label=f'Buy {upgrade.name}', style=button_style)
                buy_button.callback = partial(self.cog.buy_upgrade_callback, upgrade=upgrade)
                self.add_item(buy_button)

        # Back and Update buttons
        self.add_update_button(self.cog.shop_menu_callback)
        self.add_back_button(self.cog.main_menu_callback)

        if upgrades_count > upgrades_per_page:
            previous_button_callback = partial(self.cog.shop_menu_callback, page=page-1)
            next_button_callback = partial(self.cog.shop_menu_callback, page=page+1)
            if page > 1:
                self.add_previous_button(previous_button_callback)
            if page * upgrades_per_page < upgrades_count:
                self.add_next_button(next_button_callback)


class ActivitiesMenuView(BaseView):
    def __init__(self, cog, user_id, player, activities_per_page, page=1):
        super().__init__(cog, user_id)
        self.create_activities_menu(player, activities_per_page, page)

    def create_activities_menu(self, player, activities_per_page, page=1):
        self.clear_items()

        activities = self.cog.get_available_activities(player)

        activities_count = 0

        for items in activities:
            button_type, activity = items
            activities_count += 1

            start_index = (page - 1) * activities_per_page
            end_index = page * activities_per_page

            if start_index < activities_count <= end_index:
                button_style = discord.ButtonStyle.success if player.current_activity and player.current_activity.id == activity.id else discord.ButtonStyle.primary
                if button_type == "disabled":
                    continue

                activity_button = discord.ui.Button(label=f'{activity.name}', style=button_style)
                activity_button.callback = partial(self.cog.start_activity_callback, activity=activity)
                self.add_item(activity_button)

        if player.current_activity:
            stop_button_style = discord.ButtonStyle.danger
        else:
            stop_button_style = discord.ButtonStyle.secondary

        stop_activity_button = discord.ui.Button(label=f'Stop', style=stop_button_style, row=1)
        stop_activity_button.callback = partial(self.cog.start_activity_callback, activity="None")
        self.add_item(stop_activity_button)

        # Back and Update buttons
        # self.add_update_button(self.cog.activities_menu_callback)
        self.add_back_button(self.cog.main_menu_callback)

        if activities_count > activities_per_page:
            previous_button_callback = partial(self.cog.activities_menu_callback, page=page-1)
            next_button_callback = partial(self.cog.activities_menu_callback, page=page+1)
            if page > 1:
                self.add_previous_button(previous_button_callback)
            if page * activities_per_page < activities_count:
                self.add_next_button(next_button_callback)


class TasksMenuView(BaseView):
    def __init__(self, cog, user_id, player, tasks_per_page, page=1):
        super().__init__(cog, user_id)
        self.create_tasks_menu(player, tasks_per_page, page)

    def create_tasks_menu(self, player, tasks_per_page, page=1):
        self.clear_items()

        tasks = self.cog.get_available_tasks(player)

        tasks_count = 0

        for task in tasks:
            tasks_count += 1

            start_index = (page - 1) * tasks_per_page
            end_index = page * tasks_per_page

            if start_index < tasks_count <= end_index:
                can_afford = True
                for cost in task.energy_costs:
                    get_item = next((item for item in player.energies.values() if item.name.lower() == cost["energy"].lower()), None)
                    if not get_item or get_item.current_energy < cost["amount"]:
                        can_afford = False

                for cost in task.costs:
                    get_item = next((item for item in player.items.values() if item.name.lower() == cost["item"].lower()), None)
                    if not get_item or get_item.amount < cost["amount"]:
                        can_afford = False

                button_style = discord.ButtonStyle.primary if can_afford else discord.ButtonStyle.secondary
                task_button = discord.ui.Button(label=f'{task.name}', style=button_style)
                task_button.callback = partial(self.cog.start_task_callback, task=task)
                self.add_item(task_button)

        # Back and Update buttons
        self.add_update_button(self.cog.tasks_menu_callback)
        self.add_back_button(self.cog.main_menu_callback)

        if tasks_count > tasks_per_page:
            previous_button_callback = partial(self.cog.tasks_menu_callback, page=page-1)
            next_button_callback = partial(self.cog.tasks_menu_callback, page=page+1)
            if page > 1:
                self.add_previous_button(previous_button_callback)
            if page * tasks_per_page < tasks_count:
                self.add_next_button(next_button_callback)
