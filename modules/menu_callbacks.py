from __future__ import annotations
from functools import partial
from modules.game_features import RPSGameSession, Task
from modules.utils import ACTIVITIES_PER_PAGE, LOCATIONS_PER_PAGE, UPGRADES_PER_PAGE, format_number
from views.dropdownviews import DropdownBaseView, PlayersDropdownView, RPSDropdownView, RPSView, StartChallengeView
from views.views import ActivitiesMenuView, BaseView, LocationsMenuView, MainMenuView, ShopMenuView, TasksMenuView
from typing import TYPE_CHECKING
import discord
import random

if TYPE_CHECKING:
    from bot_commands import IncrementalGameCog  # Only imported during type checking
    from player_classes import Activity, Upgrade, Location


async def shop_menu_callback(cog: IncrementalGameCog, interaction: discord.Interaction, page=1):
    if not await is_valid_interaction(cog, interaction):
        return

    user = interaction.user
    player = await cog.get_player(user)
    if player:
        await cog.update_player(user)
        if page < 1:
            page = 1
        view = ShopMenuView(
            cog, user.id, player, UPGRADES_PER_PAGE, page,
            shop_cb=shop_menu_callback,
            back_cb=main_menu_callback,
            buy_upgrade_cb=buy_upgrade_callback,
        )
        await interaction.response.edit_message(content='', embed=cog.player_shop_embed_message(player, page), view=view)


async def update_callback(cog: IncrementalGameCog, interaction: discord.Interaction):
    user = interaction.user
    if not await is_valid_interaction(cog, interaction):
        return

    await cog.update_player(user)


async def main_menu_callback(cog: IncrementalGameCog, interaction: discord.Interaction):
    user = interaction.user
    if not await is_valid_interaction(cog, interaction):
        return

    await cog.update_player(user)

    view = MainMenuView(
        cog, user.id,
        activities_cb=activities_menu_callback,
        tasks_cb=tasks_menu_callback,
        shop_cb=shop_menu_callback,
        locations_cb=locations_menu_callback,
        update_cb=main_menu_callback,
    )
    await interaction.response.edit_message(content='', embed=cog.player_stats_embed_message(player), view=view)


async def locations_menu_callback(cog: IncrementalGameCog, interaction: discord.Interaction, page=1):
    user = interaction.user
    if not await is_valid_interaction(cog, interaction):
        return

    player = await cog.get_player(user)
    if player:
        await cog.update_player(user)
        if page < 1:
            page = 1
        view = LocationsMenuView(
            cog, user.id, player, LOCATIONS_PER_PAGE, page,
            locations_cb=locations_menu_callback,
            back_cb=main_menu_callback,
            go_location_cb=go_location_callback
        )
        await interaction.response.edit_message(content='', embed=cog.player_locations_embed_message(player, page), view=view)


async def activities_menu_callback(cog: IncrementalGameCog, interaction: discord.Interaction, page=1):
    user = interaction.user
    if not await is_valid_interaction(cog, interaction):
        return

    player = await cog.get_player(user)
    if player:
        await cog.update_player(user)
        if page < 1:
            page = 1
        view = ActivitiesMenuView(
            cog, user.id, player, ACTIVITIES_PER_PAGE, page,
            activities_cb=activities_menu_callback,
            back_cb=main_menu_callback,
            start_cb=start_activity_callback
        )
        await interaction.response.edit_message(content='', embed=cog.player_activities_embed_message(player, page), view=view)


async def tasks_menu_callback(cog: IncrementalGameCog, interaction: discord.Interaction, page=1):
    user = interaction.user
    if not await is_valid_interaction(cog, interaction):
        return

    player = await cog.get_player(user)
    if player:
        await cog.update_player(user)
        if page < 1:
            page = 1

        view = TasksMenuView(
            cog, user.id, player, ACTIVITIES_PER_PAGE, page,
            tasks_cb=tasks_menu_callback,
            back_cb=main_menu_callback,
            start_cb=start_task_callback
        )
        await interaction.response.edit_message(content='', embed=cog.player_tasks_embed_message(player, page), view=view)


async def buy_upgrade_callback(cog: IncrementalGameCog, interaction: discord.Interaction, upgrade: Upgrade, page=1):
    user = interaction.user
    if not await is_valid_interaction(cog, interaction):
        return

    player = await cog.get_player(user)

    if player:
        player.buy_upgrade(upgrade)
        cog.recalculate_player_modifiers(player)
        await cog.update_player(user)
        view = ShopMenuView(
            cog, user.id, player, UPGRADES_PER_PAGE, page,
            shop_cb=shop_menu_callback,
            back_cb=main_menu_callback,
            buy_upgrade_cb=buy_upgrade_callback,
        )
        await interaction.response.edit_message(content='', embed=cog.player_shop_embed_message(player, page), view=view)


async def go_location_callback(cog: IncrementalGameCog, interaction: discord.Interaction, location: Location, page=1):
    user = interaction.user
    if not await is_valid_interaction(cog, interaction):
        return

    player = await cog.get_player(user)

    if player:
        player.set_location(location)
        await cog.update_player(user)
        view = LocationsMenuView(
            cog, user.id, player, ACTIVITIES_PER_PAGE, page,
            locations_cb=locations_menu_callback,
            back_cb=main_menu_callback,
            go_location_cb=go_location_callback
        )
        await interaction.response.edit_message(content='', embed=cog.player_locations_embed_message(player, page), view=view)


async def start_activity_callback(cog: IncrementalGameCog, interaction: discord.Interaction, activity: Activity, page=1):
    user = interaction.user
    if not await is_valid_interaction(cog, interaction):
        return

    player = await cog.get_player(user)

    if player:
        player.change_activity(activity)
        await cog.update_player(user)
        view = ActivitiesMenuView(
            cog, user.id, player, ACTIVITIES_PER_PAGE, page,
            activities_cb=activities_menu_callback,
            back_cb=main_menu_callback,
            start_cb=start_activity_callback
        )
        await interaction.response.edit_message(content='', embed=cog.player_activities_embed_message(player, page), view=view)


async def start_task_callback(cog: IncrementalGameCog, interaction: discord.Interaction, task: Task, page=1):
    user = interaction.user
    if not await is_valid_interaction(cog, interaction):
        return

    player = await cog.get_player(user)

    if player:
        cog.complete_task(task, player)
        await cog.update_player(user)
        view = TasksMenuView(
            cog, user.id, player, ACTIVITIES_PER_PAGE, page,
            tasks_cb=tasks_menu_callback,
            back_cb=main_menu_callback,
            start_cb=start_task_callback
        )
        await interaction.response.edit_message(content='', embed=cog.player_tasks_embed_message(player, page), view=view)


async def register_callback(cog: IncrementalGameCog, interaction: discord.Interaction):
    user = interaction.user
    if not await is_valid_interaction(cog, interaction):
        return

    player = await cog.get_player(user)

    if not player:
        # Register the player and update the message
        await cog.register_player(user)
        player = await cog.get_player(user)
        if player:
            await cog.update_player(user)
            view = MainMenuView(
                cog, user.id,
                activities_cb=activities_menu_callback,
                tasks_cb=tasks_menu_callback,
                shop_cb=shop_menu_callback,
                locations_cb=locations_menu_callback,
                update_cb=main_menu_callback,
            )
            await interaction.response.edit_message(content='', embed=cog.player_stats_embed_message(player), view=view)


async def buy_chips_callback(cog: IncrementalGameCog, interaction: discord.Interaction, amount: int):
    user = interaction.user
    player = await cog.get_player(user)

    #  Check player coins count
    if player and 0 in player.items and player.items[0].amount >= amount:
        player.chips += amount
        player.items[0].amount -= amount

    await cog.update_player(user)
    await cog.start_game(user, interaction, edit=True)


async def redeem_chips_callback(cog: IncrementalGameCog, interaction: discord.Interaction, amount: int):
    user = interaction.user
    player = await cog.get_player(user)

    #  Check player Chips and Coins count, don't allow redeem if not enough coins capacity
    if player and player.chips >= amount:
        if 0 in player.items:
            coins = player.items[0]
            if coins.capacity >= amount + coins.amount:
                player.chips -= amount
                coins.amount += amount

    await cog.update_player(user)
    await cog.start_game(user, interaction, edit=True)


async def select_players_callback(cog: IncrementalGameCog, interaction: discord.Interaction, option):
    if not await is_valid_interaction(cog, interaction):
        return

    user = interaction.user
    player = await cog.get_player(user)
    if player and interaction.guild:
        player_list = [player for player in cog.get_players_from_server(interaction.guild.id) if user.id != player.id]
        view = PlayersDropdownView(
            user.id, player_list, option,
            partial(set_challenge_callback, cog)
        )
        content = f"You have `{format_number(player.chips)}` chips." \
            f"\n\nYou chose game **{option}**.\n\nNow choose player: "
        await interaction.response.edit_message(content=content, view=view)


async def set_challenge_callback(cog: IncrementalGameCog, interaction: discord.Interaction, chosen_opponent, game_name):
    user = interaction.user
    player = await cog.get_player(user)
    if player and interaction.guild:
        if chosen_opponent == "AI":
            # AI/Bot chosen
            bot_user: discord.User = cog.bot.user  # type: ignore
            chosen_member = await cog.get_player(bot_user)
            if chosen_member:
                game = next((game for game in cog.get_games().values() if game.name == game_name), None)
                if game:
                    bet_amount = 0
                    new_game_session = RPSGameSession(game.id, player, cog.players[chosen_member.id], game_name, bet_amount, interaction.channel, partial(game_rematch_callback, cog))
                    new_game_session.challenged_option = random.choice(["Rock", "Paper", "Scissors"])
                    new_game_session.accepted = True
                    new_game_session.started = True
                    view = StartChallengeView(
                        new_game_session.get_player_ids(),
                        make_choice_cb=partial(rps_choice_callback, cog)
                    )
                    message = await interaction.channel.send(embed=new_game_session.embed_message(), view=view)
                    new_game_session.message = message
                    cog.views[message.id] = view

                    cog.active_games[player.id] = new_game_session
                    cog.active_games[chosen_member.id] = new_game_session
                    await interaction.response.edit_message(delete_after=0)
        else:
            chosen_member = next((member for member in interaction.guild.members if member.name == chosen_opponent), None)
            if chosen_member:
                game = next((game for game in cog.get_games().values() if game.name == game_name), None)
                if game:
                    bet_amount = 0
                    new_game_session = RPSGameSession(
                        game.id,
                        player,
                        cog.players[chosen_member.id],
                        game_name,
                        bet_amount,
                        interaction.channel,
                        rematch_cb=game_rematch_callback
                    )
                    view = RPSView(
                        [user.id],
                        accept_cb=accept_challenge_callback,
                        decline_cb=decline_challenge_callback
                    )
                    message = await interaction.channel.send(content=f"\n\n{chosen_member.mention} just got challenged by {user.mention} in a game of **{game_name}**", embed=new_game_session.embed_message(), view=view)
                    new_game_session.message = message
                    cog.views[message.id] = view

                    cog.active_games[player.id] = new_game_session
                    cog.active_games[chosen_member.id] = new_game_session
                    await interaction.response.edit_message(delete_after=0)


async def decline_challenge_callback(cog: IncrementalGameCog, interaction: discord.Interaction):
    if not await is_valid_interaction(cog, interaction):
        return
    user = interaction.user

    if user.id not in cog.active_games:
        await interaction.response.send_message(content="This challenge is not for you!", ephemeral=True)
        return

    game = cog.active_games[user.id]
    if game.challenged and game.challenged.id != user.id:
        await interaction.response.send_message(content="Request is not for you.", ephemeral=True)
        return

    if game.declined or game.accepted:
        await interaction.response.send_message(content="You already responded to this challenge!", ephemeral=True)
        return

    await game.decline()

    await interaction.response.edit_message(content='', embed=game.embed_message(), view=None)


async def accept_challenge_callback(cog: IncrementalGameCog, interaction: discord.Interaction):
    if not await is_valid_interaction(cog, interaction):
        return

    user = interaction.user

    if user.id not in cog.active_games:
        await interaction.response.send_message(content="This challenge is not for you!", ephemeral=True)
        return

    game = cog.active_games[user.id]
    if game.challenged and game.challenged.id != user.id:
        await interaction.response.send_message(content="Request is not for you.", ephemeral=True)
        return

    if game.declined or game.accepted:
        await interaction.response.send_message(content="You already responded to this challenge!", ephemeral=True)
        return

    await game.accept()

    view = StartChallengeView(
        [user.id],
        make_choice_cb=partial(rps_choice_callback, cog)
    )
    await interaction.response.edit_message(embed=game.embed_message(), view=view)


async def game_rematch_callback(cog: IncrementalGameCog, interaction: discord.Interaction):
    if not await is_valid_interaction(cog, interaction):
        return

    user = interaction.user
    player = await cog.get_player(user)
    if player and interaction.guild:
        new_game_session = cog.active_games[user.id]
        player, opponent_player = new_game_session.get_players(user.id)
        if player != new_game_session.challenger:
            # Incase if rematch is initiated by challenger
            new_game_session.challenger = player
            new_game_session.challenged = opponent_player
            challenger_score = new_game_session.challenger_score
            challenged_score = new_game_session.challenged_score
            new_game_session.challenger_score = challenged_score
            new_game_session.challenged_score = challenger_score

        chosen_member = next((member for member in interaction.guild.members if member.name == opponent_player.name), None)
        if new_game_session and chosen_member:
            new_game_session.reset_game()
            if cog.bot.user and chosen_member.id == cog.bot.user.id:
                new_game_session.challenged_option = random.choice(["Rock", "Paper", "Scissors"])
                new_game_session.accepted = True
                new_game_session.started = True
                view = StartChallengeView(
                    new_game_session.get_player_ids(),
                    make_choice_cb=partial(rps_choice_callback, cog)
                )
            else:
                view = RPSView(
                    [chosen_member.id],
                    accept_cb=partial(accept_challenge_callback, cog),
                    decline_cb=partial(decline_challenge_callback, cog)
                )

            await interaction.response.edit_message(content=f"\n\n**Rematch!**", embed=new_game_session.embed_message(), view=view)


async def rps_choice_callback(cog: IncrementalGameCog, interaction: discord.Interaction):
    if not await is_valid_interaction(cog, interaction):
        return

    user = interaction.user

    view = RPSDropdownView(user.id, partial(rps_game_callback, cog))
    await interaction.response.send_message("Choose an option:", view=view, ephemeral=True)


async def rps_game_callback(cog: IncrementalGameCog, interaction: discord.Interaction, option):
    user = interaction.user

    if user.id in cog.active_games:
        game = cog.active_games[user.id]
        player, _ = game.get_players(user.id)
        if player == game.challenger:
            game.challenger_option = option
        else:
            game.challenged_option = option

        player = await cog.get_player(interaction.user)

        game.check_winner()
        await interaction.response.edit_message(delete_after=0)

        if game.finished:
            if player and interaction.guild:
                await game.restart_match(cog)
                return

        await game.update_message()


async def is_valid_interaction(cog: IncrementalGameCog, interaction: discord.Interaction):
    if interaction.message:
        view = cog.views.get(interaction.message.id)

        if (isinstance(view, BaseView) or isinstance(view, DropdownBaseView)) and not view.is_owner(interaction):
            return False

    return True
