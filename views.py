import discord
from functools import partial


class BaseView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.user_id = user_id

    def is_owner(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    def add_back_button(self, callback):
        back_button = discord.ui.Button(label='Back', style=discord.ButtonStyle.secondary)
        back_button.callback = callback
        self.add_item(back_button)

    def add_update_button(self, callback, row=1):
        update_button = discord.ui.Button(label='Update', style=discord.ButtonStyle.secondary, row=row)
        update_button.callback = callback
        self.add_item(update_button)


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
    def __init__(self, cog, user_id, player):
        super().__init__(cog, user_id)
        self.create_shop_menu(player)

    def create_shop_menu(self, player):
        self.clear_items()
        missing_upgrades = self.cog.get_missing_upgrades(player)
        for upgrade, _ in missing_upgrades:
            currency = next((c for c in player.currencies.values() if c.name == upgrade.cost_material), None)
            button_style = discord.ButtonStyle.success if currency and currency.amount >= upgrade.cost else discord.ButtonStyle.secondary
            buy_button = discord.ui.Button(label=f'Buy {upgrade.name}', style=button_style)
            buy_button.callback = partial(self.cog.buy_upgrade_callback, upgrade=upgrade)
            self.add_item(buy_button)

        # Back and Update buttons
        self.add_back_button(self.cog.main_menu_callback)
        self.add_update_button(self.cog.shop_menu_callback)


class ActivitiesMenuView(BaseView):
    def __init__(self, cog, user_id, player):
        super().__init__(cog, user_id)
        self.create_activities_menu(player)

    def create_activities_menu(self, player):
        self.clear_items()

        if player.current_activity:
            stop_activity_button = discord.ui.Button(label=f'Stop', style=discord.ButtonStyle.danger)
            stop_activity_button.callback = partial(self.cog.start_activity_callback, activity=None)
            self.add_item(stop_activity_button)

        activities = self.cog.get_available_activities(player)

        for activity in activities:
            button_style = discord.ButtonStyle.success if player.current_activity and player.current_activity.id == activity.id else discord.ButtonStyle.primary
            activity_button = discord.ui.Button(label=f'{activity.name}', style=button_style)
            activity_button.callback = partial(self.cog.start_activity_callback, activity=activity)
            self.add_item(activity_button)

        # Back and Update buttons
        self.add_back_button(self.cog.main_menu_callback)
        self.add_update_button(self.cog.activities_menu_callback)

