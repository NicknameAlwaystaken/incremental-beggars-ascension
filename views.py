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
                currency = next((c for c in player.currencies.values() if c.name == upgrade.cost_material), None)
                button_style = discord.ButtonStyle.success if currency and currency.amount >= upgrade.cost else discord.ButtonStyle.secondary
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

        for activity in activities:
            activities_count += 1

            start_index = (page - 1) * activities_per_page
            end_index = page * activities_per_page

            if start_index < activities_count <= end_index:
                button_style = discord.ButtonStyle.success if player.current_activity and player.current_activity.id == activity.id else discord.ButtonStyle.primary
                activity_button = discord.ui.Button(label=f'{activity.name}', style=button_style)
                activity_button.callback = partial(self.cog.start_activity_callback, activity=activity)
                self.add_item(activity_button)

        if player.current_activity:
            stop_button_style = discord.ButtonStyle.danger
        else:
            stop_button_style = discord.ButtonStyle.secondary

        stop_activity_button = discord.ui.Button(label=f'Stop', style=stop_button_style, row=1)
        stop_activity_button.callback = partial(self.cog.start_activity_callback, activity=None)
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
