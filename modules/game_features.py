from __future__ import annotations
from typing import Optional, Any
from abc import abstractmethod
from views.dropdownviews import RematchChallengeView
from discord.ext import commands
import discord

class Game:
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.played = 0
        self.wins = 0
        self.losses = 0
        self.amount_bet = 0
        self.earnings = 0

    def copy(self):
        new_game = Game(
            id=self.id,
            name=self.name
        )

        new_game.played = self.played
        new_game.wins = self.wins
        new_game.losses = self.losses
        new_game.amount_bet = self.amount_bet
        new_game.earnings = self.earnings

        return new_game


class Task:
    def __init__(self, id: int, name: str, icon: str, task_amount: int, description: str):
        self.id = id
        self.name = name
        self.icon = icon
        self.task_amount = task_amount
        self.description = description
        self.outputs: list[dict[str, Any]] = []
        self.costs: list[dict[str, Any]] = []
        self.energy_costs: list[dict[str, Any]] = []
        self.unlock_conditions: list[str] = []
        self.unlocks: list[str] = []
        self.effects: dict[str, dict[str, Any]] = {}

    def copy(self):
        new_task = Task(
            self.id,
            self.name,
            self.icon,
            self.task_amount,
            self.description
        )

        new_task.outputs = self.outputs[:]
        new_task.costs = self.costs[:]
        new_task.energy_costs = self.energy_costs[:]
        new_task.unlock_conditions = self.unlock_conditions[:]
        new_task.unlocks = self.unlocks[:]
        new_task.effects = self.effects.copy()

        return new_task


class GameSession:
    _session_id = 0

    def __init__(self, game_id: int, challenger: Player, challenged: Player, game_name, bet_amount, game_channel, rematch_cb):
        self.game_id = game_id
        self.challenger = challenger
        self.challenged = challenged
        self.game_name = game_name
        self.bet_amount = bet_amount
        self.game_channel = game_channel
        self.rematch_cb = rematch_cb
        self.accepted = False
        self.declined = False
        self.started = False
        self.finished = False
        self.message: Optional[discord.Message] = None

        self.winner: Any = None
        self.loser: Any = None

        self.challenger_score = 0
        self.challenged_score = 0

        self.challenger_option: str | None = None
        self.challenged_option: str | None = None

        self.session_id = GameSession._session_id
        GameSession._session_id += 1

    def reset_game(self):
        self.finished = False
        self.accepted = False
        self.declined = False
        self.started = False

    def get_player_ids(self):
        return [self.challenger.id, self.challenged.id]

    def get_players(self, user_id):
        if user_id == self.challenger.id:
            return self.challenger, self.challenged
        return self.challenged, self.challenger

    @abstractmethod
    def check_winner(self):
        pass

    async def update_message(self):
        if self.message:
            await self.message.edit(content='', embed=self.embed_message())

    async def restart_match(self, cog):
        if self.message:
            view = RematchChallengeView(
                self.get_player_ids(),
                rematch_cb=self.rematch_cb
            )
            await self.message.edit(embed=self.embed_message(), view=view)

    async def accept(self):
        self.accepted = True
        self.started = True

    async def decline(self):
        self.declined = True
        self.started = False

    @abstractmethod
    def embed_message(self) -> discord.Embed:
        pass


class RPSGameSession(GameSession):
    def __init__(self, game_id, challenger, challenged, game_name, bet_amount, channel, rematch_cb):
        super().__init__(game_id, challenger, challenged, game_name, bet_amount, channel, rematch_cb)

    def check_winner(self):
        if self.challenger_option is not None and self.challenged_option is not None:
            if (
                (self.challenger_option == "Rock" and self.challenged_option == "Scissors") or
                (self.challenger_option == "Scissors" and self.challenged_option == "Paper") or
                (self.challenger_option == "Paper" and self.challenged_option == "Rock")
               ):
                self.challenger_score += 1

                self.winner = self.challenger
                self.loser = self.challenged

                self.winner.games[self.game_id].wins += 1
                self.winner.games[self.game_id].earnings += self.bet_amount
                self.winner.games[self.game_id].amount_bet += self.bet_amount

                self.loser.games[self.game_id].losses += 1
                self.loser.games[self.game_id].amount_bet += self.bet_amount

            elif self.challenger_option == self.challenged_option:
                self.winner = "tie"
            else:
                self.challenged_score += 1

                self.winner = self.challenged
                self.loser = self.challenger

                self.winner.games[self.game_id].wins += 1
                self.winner.games[self.game_id].earnings += self.bet_amount
                self.winner.games[self.game_id].amount_bet += self.bet_amount

                self.loser.games[self.game_id].losses += 1
                self.loser.games[self.game_id].amount_bet += self.bet_amount

            self.challenger.games[self.game_id].played += 1
            self.challenged.games[self.game_id].played += 1

            self.finished = True

    def get_player_ids(self):
        return [self.challenger.id, self.challenged.id]

    def get_players(self, user_id):
        if user_id == self.challenger.id:
            return self.challenger, self.challenged
        return self.challenged, self.challenger

    def reset_game(self):
        super().reset_game()
        self.challenger_option: str | None = None
        self.challenged_option: str | None  = None
        self.winner = None
        self.loser = None

    def embed_message(self):
        embed_color = discord.Color.green() if self.started and not self.finished else discord.Color.red()

        embed = discord.Embed(
            title="🎰 Current Game",
            description=f'{self.game_name}',
            color=embed_color
        )

        players_text = f"**{self.challenger.display_name}** Score: `{self.challenger_score}`" \
            f"\n**{self.challenged.display_name}** Score: `{self.challenged_score}`"

        embed.add_field(name="🎮 Players", value=players_text, inline=False)

        if self.declined:
            embed.add_field(name="Game declined!", value='', inline=False)
        else:
            if self.started:
                choice_dict = {
                    "Rock": '✊',
                    "Paper": '🖐',
                    "Scissors": '✌'
                }

                check_emoji = '✅'
                questionmark_emoji = '❓'

                challenger_choice = check_emoji if self.challenger_option else questionmark_emoji
                challenged_choice = check_emoji if self.challenged_option else questionmark_emoji

                if self.challenger_option and self.challenged_option:
                    challenger_choice = f'{choice_dict.get(self.challenger_option, "Fail")}'
                    challenged_choice = f'{choice_dict.get(self.challenged_option, "Fail")}'

                choices_text = f'**{self.challenger.display_name}**: ' + challenger_choice + f'\n**{self.challenged.display_name}**: ' + challenged_choice

                embed.add_field(name="✊🖐✌ Choices", value=choices_text, inline=False)

            if self.winner:
                if self.winner == 'tie':
                    winner_text = 'The game is a **TIE**!'
                else:
                    winner_text = f'**{self.winner.display_name}** is the winner! 🎉🎉🎉'

                embed.add_field(name="🎉 Game finished!", value=winner_text, inline=False)

        return embed


class WrongChannelError(commands.CheckFailure):
    pass
