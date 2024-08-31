from discord.ext import commands
import asyncio
import discord

tree = None

@commands.command(name='sync')
async def synchronizeSlashCommands(ctx):
  await tree.sync()
  print("Tree synced")


@commands.hybrid_command(name='slash', with_app_command=True)
async def slashCommand(ctx: commands.Context):
    await ctx.send("SLAAAAAASH!")

#Test
@commands.command(name='repeat')
async def repeatWord(ctx: commands.Context, str):
    await ctx.send(str)

@commands.command(name='repeatS')
async def repeatSentence(ctx: commands.Context, *args):
    arguments = " ".join(args) #Chars between the quotes get printed inbetween the joined args.
    await ctx.send(arguments)
@commands.command(name='removereaction')
async def removeReaction(ctx: commands.Context):
    """
    Creates a message that removes reactions.

    Parameters:
    None

    Output:
    Message: Message that will have reactions removed
    """

    channel = ctx
    client = ctx.bot

    msg_remove_reactions = (await channel.send('If you react to this message, I will remove it!'))

    @client.event
    async def on_reaction_add(reaction, user):
        #new event to bot, deprecated manner of creating event. Don't use this.
        if(reaction.message.id == msg_remove_reactions.id):
            await msg_remove_reactions.remove_reaction(reaction, user)



async def setup(bot):
    global tree
    tree = bot.tree
    bot.add_command(synchronizeSlashCommands)
    bot.add_command(slashCommand)
    bot.add_command(removeReaction)
    bot.add_command(repeatWord)
    bot.add_command(repeatSentence)
