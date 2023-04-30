import discord
from discord.ext import commands
import openai
import tiktoken as tiktoken
import datetime
import random
import logging
import io
import requests
import config

# Config
openai.api_key = config.openapi_token
discord_token = config.discord_token
guilds = config.guilds
owner_id = config.owner_id
unlocked = False
#handler = logging.FileHandler(filename='icarus_discord.log', encoding='utf-8', mode='w')

# This code from OpenAI counts the number of tokens in a message list
def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301"):
  """Returns the number of tokens used by a list of messages."""
  try:
      encoding = tiktoken.encoding_for_model(model)
  except KeyError:
      encoding = tiktoken.get_encoding("cl100k_base")
  if model == "gpt-3.5-turbo-0301":  # note: future models may deviate from this
      num_tokens = 0
      for message in messages:
          num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
          for key, value in message.items():
              num_tokens += len(encoding.encode(value))
              if key == "name":  # if there's a name, the role is omitted
                  num_tokens += -1  # role is always required and always 1 token
      num_tokens += 2  # every reply is primed with <im_start>assistant
      return num_tokens
  else:
      raise NotImplementedError(f"""num_tokens_from_messages() is not presently implemented for model {model}.
  See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")

def update_online_users(guild_id):
    users = []
    guild = bot.get_guild(guild_id)
    for member in guild.members:
        if member.status != discord.Status.offline and isinstance(member.display_name, str):
            users.append(member.display_name)
    return users

def update_channels(guild_id):
    channels = []
    guild = bot.get_guild(guild_id)
    for channel in guild.text_channels:
        if isinstance(channel.name, str):
            channels.append(channel.name)
    return channels

def update_systems():
    global guilds
    for guild in guilds:
        update_system(guild)

def update_system(guild_id):
    users = update_online_users(guild_id)
    channels = update_channels(guild_id)

    user_list = ", ".join(users)
    channel_list = ", ".join(channels)

    print(f"Updating system for {guild_id}, with {user_list} and {channel_list}.")
    global guilds
    formatted_system = guilds[guild_id]["systemtext"].format(user_list=user_list, channel_list=channel_list)
    system = [{"role": "system", "content": formatted_system}]
    guilds[guild_id]["system"] = system
    guilds[guild_id]["users"] = users
    guilds[guild_id]["channels"] = channels

def is_owner(ctx):
    global unlocked
    return ctx.author.id == owner_id or unlocked

async def dalle_draw(prompt):
    # Pass the message to the OpenAI API
    response = await openai.Image.acreate(
        prompt=str(prompt)[:950],
        size="256x256",
        n=1,
        response_format="url"
    )
    print("Drew",response["data"][0]["url"])
    return response["data"][0]["url"]

# --------------------------------------------------------------
# Startup
# --------------------------------------------------------------
print("Starting...")
start_time = datetime.datetime.now()

# create the Discord Bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

description = "icarus Discord Bot"
bot = commands.Bot(command_prefix='/', intents=intents, description=description)

@bot.command()
async def hello(ctx):
    await ctx.send("Hello!")

@bot.command()
async def lock(ctx):
    global unlocked
    if is_owner(ctx):
        unlocked = False
        await ctx.send("Some functions are now locked.")
    else:
        await ctx.send("You're not allowed to lock.")

@bot.command()
async def unlock(ctx):
    global unlocked
    if is_owner(ctx):
        unlocked = True
        await ctx.send("Some functions are now open.")
    else:
        await ctx.send("You're not allowed to unlock.")

@bot.command()
async def status(ctx):
    global guilds
    current_time = datetime.datetime.now()
    delta = str(current_time - start_time)
    messages = guilds[ctx.guild.id]["messages"]
    await ctx.send(f'Online for {delta}. {num_tokens_from_messages(messages)} tokens in cache.')

@bot.command()
async def allstatus(ctx):
    if is_owner(ctx):
        global guilds
        current_time = datetime.datetime.now()
        delta = str(current_time - start_time)
        await ctx.send(f'Online for {delta}. We are talking in {ctx.guild.id}.')

        for guild in guilds:
            await ctx.send(f'{num_tokens_from_messages(guilds[guild]["messages"])} tokens in cache for {guild}.')
        await ctx.send("allstatus done.")
    else:
        await ctx.send("I'm afraid I can't do that.")

@bot.command()
async def draw(ctx):
    if is_owner(ctx):
        inbound_prompt = ctx.message.clean_content.split(" ")[1:]
        result = await dalle_draw(inbound_prompt)
        r = requests.get(result)
        with io.BytesIO(r.content) as inmemoryfile:
            await ctx.send(file=discord.File(inmemoryfile, 'result.png'))
    else:
        await ctx.send("I'm afraid I can't do that.")

@bot.command()
async def reset(ctx):
    global guilds
    guild_id = ctx.guild.id
    guilds[guild_id]["messages"] = []
    messages = guilds[guild_id]["messages"]
    await ctx.send(f'Ok, reset. {num_tokens_from_messages(messages)} tokens in cache.')

@bot.command()
async def refresh(ctx):
    update_system(ctx.guild.id)

    global guilds
    users = guilds[ctx.guild.id]["users"]
    channels = guilds[ctx.guild.id]["channels"]
    system = guilds[ctx.guild.id]["system"]

    if users is None:
        users = []
    if channels is None:
        channels = []

    await ctx.send(f'Ok, updated. We have {len(users)} users and {len(channels)} channels online. System is {num_tokens_from_messages(system)} tokens.')

# Pick a message sent to the channel "quotes" between 2019 and 2023.
@bot.command()
async def quote(ctx):
    start_date = datetime.datetime(2019, 1, 1)
    end_date = datetime.datetime(2022, 12, 31)
    random_date = start_date + datetime.timedelta(
        seconds=random.randint(0, int((end_date - start_date).total_seconds()))
    )

    try:
        channel = discord.utils.get(ctx.guild.channels, name='quotes')
        messages = [message async for message in channel.history(after=random_date, limit=1)]
    except:
        await ctx.channel.send("Failed")
        return

    if len(messages) > 0:
        message_date = messages[0].created_at.strftime('%Y-%m-%d')
        res = ""
        res += "💬🎲 | "
        res += message_date + " by " + messages[0].author.mention + ":\n"
        res += messages[0].content
        await ctx.channel.send(res)
    else:
        await ctx.channel.send("Failed")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    update_systems()
    print('------')

@bot.event
async def on_reaction_add(reaction, user):
    if reaction.me:
        return
    if reaction.message.author.id == bot.user.id:
        if str(reaction.emoji) == '🍅':
            await reaction.message.reply("Tomato!")

    elif str(reaction.emoji) == '🍅':
        await reaction.message.add_reaction('🍅')
        await reaction.message.add_reaction('🔴')

@bot.event
async def on_message(message):
    global guilds
    # Only respond to messages that mention the bot
    if message.author == bot.user:
        return
    # Do not process direct messages
    if message.guild is None:
        return

    guild_id = message.guild.id
    guild_name = message.guild.name

    # Exit if the source guild is not in our config
    if guilds.get(guild_id, None) is None:
        print(f"Warning, the guild {guild_id} is not tracked!")
        return

    # Do not respond if everyone is mentioned
    # Otherwise continue and process with OpenAI
    if message.mention_everyone == False and bot.user in message.mentions:
        inbound_prompt = message.author.display_name + ": " + " ".join(message.clean_content.split(" ")[1:])
        print(f"Recv [{guild_id}/{guild_name}]:", inbound_prompt)
        inbound_message = {"role": "user", "content": inbound_prompt}
        guilds[guild_id]["messages"].append(inbound_message)

        # Make sure we cannot exceed 4k tokens
        while num_tokens_from_messages(guilds[guild_id]["messages"]) > 3000:
            print(f"Tokens exceed 3k for [{guild_id}/{guild_name}], popping ...")
            try:
                guilds[guild_id]["messages"].pop(0)
            except:
                print(f"Popping failed for [{guild_id}/{guild_name}]!")
                pass
        # Pass the message to the OpenAI API
        response = await openai.ChatCompletion.acreate(
            timeout=10,
            model="gpt-3.5-turbo",
            messages=guilds[guild_id]["system"] + guilds[guild_id]["messages"],
            max_tokens=500,
            n=1,
            temperature=0.8,
        )

        # Append the response from OpenAI to the list of messages
        r = response.choices[0]["message"]
        guilds[guild_id]["messages"].append(r)

        # Make sure we do not exceed Discords length limit
        c = response.choices[0]["message"]["content"]
        if len(c) > 1999:
            c = c[:1980] + "...[capped]..."
        c2 = message.author.mention + " " + c

        # Send the response to the channel
        await message.channel.send(c2)

    # Process commands, if any
    await bot.process_commands(message)

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # Run the bot
    #bot.run(discord_token, log_handler=handler)
    bot.run(discord_token)