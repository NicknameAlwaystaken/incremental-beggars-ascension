import discord
from functools import partial


class DropdownBaseView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id

    def is_owner(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id


class PlayersDropdown(discord.ui.Select):
    def __init__(self, players_list, selected_game, trigger_function):
        options = []
        options.append(discord.SelectOption(label="AI", description="Discord Bot", emoji="🤖"))

        for player in players_list:
            options.append(discord.SelectOption(label=player.name, description=player.display_name, emoji="🦯"))

        super().__init__(placeholder="Choose opponent", min_values=1, max_values=1, options=options)
        self.selected_game = selected_game
        self.trigger_function = trigger_function

    async def callback(self, interaction: discord.Interaction):
        await self.trigger_function(interaction, self.values[0], self.selected_game)


class GamesDropdown(discord.ui.Select):
    def __init__(self, trigger_function):
        options = [
            discord.SelectOption(label="Rock Paper Scissors", description="Rock Paper Scissors", emoji="✊")
        ]

        super().__init__(placeholder="Choose a game", min_values=1, max_values=1, options=options)
        self.trigger_function = trigger_function

    async def callback(self, interaction: discord.Interaction):
        await self.trigger_function(interaction, self.values[0])


class RPSDropdown(discord.ui.Select):
    def __init__(self, trigger_function):
        options = [
            discord.SelectOption(label="Rock", description="Pick Rock", emoji="✊"),
            discord.SelectOption(label="Paper", description="Pick Paper", emoji="✋"),
            discord.SelectOption(label="Scissors", description="Pick Scissors", emoji="✌️")
        ]

        super().__init__(placeholder="Choose your move", min_values=1, max_values=1, options=options)
        self.trigger_function = trigger_function

    async def callback(self, interaction: discord.Interaction):
        await self.trigger_function(interaction, self.values[0])


class GamesDropdownView(DropdownBaseView):
    def __init__(self, user_id, player, game_select_cb, *, add_cb, redeem_cb):
        super().__init__(user_id)

        self.add_item(GamesDropdown(game_select_cb))

        chips_list = [5, 10, 20, 50]

        player_coins = next((item for item in player.items.values() if item.name == "coins"), None)

        if player_coins:
            for chip_amount in chips_list:
                add_button_style = discord.ButtonStyle.primary if player_coins.amount >= chip_amount else discord.ButtonStyle.secondary
                add_chips_button = discord.ui.Button(label=f'Buy {chip_amount} chips', style=add_button_style, row=2)
                add_chips_button.callback = partial(add_cb, amount=chip_amount)
                self.add_item(add_chips_button)

                redeem_button_style = discord.ButtonStyle.primary if player.chips >= chip_amount and player_coins.capacity >= chip_amount + player_coins.amount else discord.ButtonStyle.secondary
                redeem_chips_button = discord.ui.Button(label=f'Sell {chip_amount} chips', style=redeem_button_style, row=4)
                redeem_chips_button.callback = partial(redeem_cb, amount=chip_amount)
                self.add_item(redeem_chips_button)


class PlayersDropdownView(DropdownBaseView):
    def __init__(self, user_id, players_list, selected_game, trigger_function):
        super().__init__(user_id)
        self.add_item(PlayersDropdown(players_list, selected_game, trigger_function))


class RPSDropdownView(DropdownBaseView):
    def __init__(self, user_id, trigger_function):
        super().__init__(user_id)
        self.add_item(RPSDropdown(trigger_function))


class GameBaseView(discord.ui.View):
    def __init__(self, user_ids):
        super().__init__()
        self.user_ids = user_ids

    def is_owner(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id in self.user_ids

    def add_accept_button(self, callback, row=1):
        accept_button = discord.ui.Button(label='Accept challenge', style=discord.ButtonStyle.success, row=row)
        accept_button.callback = callback
        self.add_item(accept_button)

    def add_decline_button(self, callback, row=1):
        decline_button = discord.ui.Button(label='Decline challenge', style=discord.ButtonStyle.danger, row=row)
        decline_button.callback = callback
        self.add_item(decline_button)


class RPSView(GameBaseView):
    def __init__(self, user_ids, *, accept_cb, decline_cb):
        super().__init__(user_ids)
        self.create_rps_view(accept_cb, decline_cb)

    def create_rps_view(self, accept_cb, decline_cb):
        self.add_accept_button(accept_cb)
        self.add_decline_button(decline_cb)


class StartChallengeView(GameBaseView):
    def __init__(self, user_ids, *, make_choice_cb):
        super().__init__(user_ids)
        self.create_challenge_view(make_choice_cb)

    def create_challenge_view(self, make_choice_cb):
        make_choice_button = discord.ui.Button(label='Make choice', style=discord.ButtonStyle.success, row=1)
        make_choice_button.callback = make_choice_cb
        self.add_item(make_choice_button)


class RematchChallengeView(GameBaseView):
    def __init__(self, user_ids, *, rematch_cb):
        super().__init__(user_ids)
        self.create_rematch_challenge_view(rematch_cb)

    def create_rematch_challenge_view(self, rematch_cb):
        rematch_button = discord.ui.Button(label='Rematch?', style=discord.ButtonStyle.success, row=1)
        rematch_button.callback = rematch_cb
        self.add_item(rematch_button)
