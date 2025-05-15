from __future__ import annotations
import os
from discord.ext import commands
from modules.game_database import create_activities_table, create_energies_table, create_games_table, create_items_table, create_locations_table, create_player_activities_table, create_player_chips_table, create_player_energies_table, create_player_games_table, create_player_items_table, create_player_locations_table, create_player_reputations_table, create_player_skills_table, create_player_tasks_table, create_player_upgrades_table, create_players_table, create_reputations_table, create_server_channel_table, create_skills_table, create_tasks_table, create_upgrades_table, update_activities_from_json_to_db, update_energies_from_json_to_db, update_games_from_json_to_db, update_items_from_json_to_db, update_locations_from_json_to_db, update_reputations_from_json_to_db, update_reputations_titles_from_json_to_db, update_reputations_unlocks_from_json_to_db, update_skills_from_json_to_db, update_tasks_from_json_to_db, update_upgrades_from_json_to_db
from modules.bot_commands import IncrementalGameCog, make_tree_sync_command

game_data_folder = 'game_data'

GAME_DB_LOCATION = os.path.join(game_data_folder, 'game.db')

SERVER_DB_LOCATION = os.path.join(game_data_folder, 'server.db')


async def create_tables():
    # create table if doesn't exist

    await create_server_channel_table(SERVER_DB_LOCATION)

    await create_players_table(GAME_DB_LOCATION)

    await create_activities_table(GAME_DB_LOCATION)
    await update_activities_from_json_to_db(GAME_DB_LOCATION)
    await create_player_activities_table(GAME_DB_LOCATION)

    await create_items_table(GAME_DB_LOCATION)
    await update_items_from_json_to_db(GAME_DB_LOCATION)
    await create_player_items_table(GAME_DB_LOCATION)

    await create_upgrades_table(GAME_DB_LOCATION)
    await update_upgrades_from_json_to_db(GAME_DB_LOCATION)
    await create_player_upgrades_table(GAME_DB_LOCATION)

    await create_skills_table(GAME_DB_LOCATION)
    await update_skills_from_json_to_db(GAME_DB_LOCATION)
    await create_player_skills_table(GAME_DB_LOCATION)

    await create_energies_table(GAME_DB_LOCATION)
    await update_energies_from_json_to_db(GAME_DB_LOCATION)
    await create_player_energies_table(GAME_DB_LOCATION)

    await create_tasks_table(GAME_DB_LOCATION)
    await update_tasks_from_json_to_db(GAME_DB_LOCATION)
    await create_player_tasks_table(GAME_DB_LOCATION)

    await create_reputations_table(GAME_DB_LOCATION)
    await update_reputations_from_json_to_db(GAME_DB_LOCATION)
    await update_reputations_unlocks_from_json_to_db(GAME_DB_LOCATION)
    await update_reputations_titles_from_json_to_db(GAME_DB_LOCATION)
    await create_player_reputations_table(GAME_DB_LOCATION)

    await create_locations_table(GAME_DB_LOCATION)
    await update_locations_from_json_to_db(GAME_DB_LOCATION)
    await create_player_locations_table(GAME_DB_LOCATION)

    await create_games_table(GAME_DB_LOCATION)
    await update_games_from_json_to_db(GAME_DB_LOCATION)
    await create_player_games_table(GAME_DB_LOCATION)

    await create_player_chips_table(GAME_DB_LOCATION)


async def prepare_game_cog(game_cog: IncrementalGameCog):
    await game_cog.get_server_channels_from_db()

    await game_cog.get_items_from_db()
    await game_cog.get_reputations_from_db()
    await game_cog.get_upgrades_from_db()
    await game_cog.get_tasks_from_db()
    await game_cog.get_skills_from_db()
    await game_cog.get_energies_from_db()
    await game_cog.get_activities_from_db()
    await game_cog.get_games_from_db()

    # locations has to be after activities, tasks and upgrades
    # it refers to the lists in game_cog
    await game_cog.get_locations_from_db()

    game_cog.initialize()


async def setup(bot: commands.Bot):
    bot.add_command(make_tree_sync_command(bot.tree))

    await create_tables()

    game_cog = IncrementalGameCog(bot)
    await bot.add_cog(game_cog)

    await prepare_game_cog(game_cog)
