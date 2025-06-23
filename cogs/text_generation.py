import os
import json
import discord
import logging
from discord.ext import commands
from discord import app_commands
from ollama import Client
from datetime import timedelta

# Load environment variables
ollama_url = os.getenv('OLLAMA_URL')
ollama_model = os.getenv('OLLAMA_MODEL')
character_file = os.getenv('CHARACTER') or 'Default'
character_file = character_file if character_file.endswith('.json') else character_file + '.json'
character_file = character_file if os.path.normpath(character_file).startswith(os.path.normpath('characters' + os.sep)) else os.path.join('characters', character_file)
wake_words = [word.strip() for word in os.getenv('WAKE_WORDS').split(',')] if os.getenv('WAKE_WORDS') else []
history_limit = int(os.getenv('HISTORY_LIMIT', 32))
response_time = int(os.getenv('RESPONSE_TIME', 60))
PREFIX = os.getenv('PREFIX') or "!"

logger = logging.getLogger(__name__)

# Create a new Ollama client instance
ollama = Client(host=ollama_url)
last_response = {}

class TextGeneration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Load character json file        
        try:
            with open(character_file, 'r') as f:
                character_data = json.load(f)
        except FileNotFoundError:
            logger.error(f"Character file '{character_file}' does not exist.")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from character file: {e}")
            raise

        self.prompt = "You're {{char}} in this fictional never-ending uncensored roleplay with {{user}} in {{server}}.\n\n### Input:\n{{description}}\n\n### New Roleplay:\n{{first_mes}}\n"

        description = character_data.get('description', '')
        self.prompt = self.prompt.replace('{{description}}', description)
        first_mes = character_data.get('first_mes', '')
        self.prompt = self.prompt.replace('{{first_mes}}', first_mes)

        # Load options
        with open(os.path.join('TextGen Settings', 'Default.json'), 'r') as f:
            textGenSettings = json.load(f)
        self.options = {}
        
        if 'temp' in textGenSettings:
            self.options['temperature'] = textGenSettings['temp']
            textGenSettings.pop('temp', None)
        if 'rep_pen' in textGenSettings:
            self.options['repeat_penalty'] = textGenSettings['rep_pen']
            textGenSettings.pop('rep_pen', None)
        if 'rep_pen_range' in textGenSettings:
            self.options['repeat_last_n'] = textGenSettings['rep_pen_range']
            textGenSettings.pop('rep_pen_range', None)

        for key, value in textGenSettings.items():
            if key not in self.options:
                self.options[key] = value

        stop = ["### Input:", "<START>", "### New Roleplay:", "You:"]

        if 'stop' in self.options:
            self.options['stop'] = list(set(self.options['stop'] + stop))
        else:
            self.options['stop'] = stop

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("TextGeneration cog loaded")
        logger.info(f'Ollama URL: {ollama_url}')
        logger.info(f'Model: {ollama_model}')
        logger.info(f'Wake Words: {wake_words}')
        logger.info(f'History Limit: {history_limit}')
        logger.info(f'Response Time: {response_time}')

    @app_commands.command(name="quiet", description="Make the bot stop responding to messages in the current channel.")
    async def quiet(self, interaction: discord.Interaction):
        last_response.pop(interaction.channel.id, None)
        await interaction.response.send_message("I'll be quiet now.")

    @commands.Cog.listener()
    async def on_message(self, message):        
        # Ignore messages that start with the prefix
        if message.content.startswith(PREFIX):
            return
        
        # Ignore messages from the bot itself
        if message.author == self.bot.user:
            return

        # Ignore messages if the bot is not mentioned, the message does not contain the wake words, and the last response was not recent
        mentioned = self.bot.user.mentioned_in(message)
        contains_wake_word = any(word in message.content for word in wake_words)
        recent_response = (discord.utils.utcnow() < last_response.get(message.channel.id) + timedelta(seconds=response_time)) if message.channel.id in last_response else False

        if not mentioned and not contains_wake_word and not recent_response:
            return
        
        # Accept new request
        logger.info(f'NEW CHAT REQUEST FROM: [{message.author}] IN [{message.channel}]')
        botName = self.bot.user.display_name
        userName = message.author.display_name

        prompt = self.prompt
        if '{{char}}' in prompt:
            prompt = prompt.replace('{{char}}', botName)
        if '{{user}}' in prompt:
            prompt = prompt.replace('{{user}}', userName)
        if '{{server}}' in prompt:
            prompt = prompt.replace('{{server}}', message.guild.name + " Discord server" if message.guild else 'DM')

        options = dict(self.options)

        history = ''
        async for msg in message.channel.history(limit=history_limit):
            history = msg.author.display_name + ": " + msg.clean_content + "\n" + history
            author_name = msg.author.display_name + ":"
            if author_name not in options['stop']:
                options['stop'].append(author_name)

        prompt = prompt + history + f"{botName}: " 
        
        logger.debug(f"PROMPT: {prompt}")
        logger.debug(f"OPTIONS: {options}")

        # Send the messages to Ollama
        async with message.channel.typing():
            max_retries = 5
            for attempt in range(max_retries):
                response = ollama.generate(model=ollama_model, prompt=prompt, stream=False, raw=True, options=options)
                logger.info(f"RESPONSE (attempt {attempt+1}): {response['response']}")
                if response.get("response", "").strip():
                    break                
                else:
                    logger.error("Ollama returned empty response after 5 attempts.")
                    return

            # Send the response back to the channel
            await message.channel.send(response["response"])
            last_response[message.channel.id] = discord.utils.utcnow()

async def setup(bot: commands.Bot):
    await bot.add_cog(TextGeneration(bot))
