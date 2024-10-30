import os
import math
import discord
from discord.ext import commands
from discord import app_commands

USER_ROLES = [role.strip() for role in os.getenv('USER_ROLES').split(',')] if os.getenv('USER_ROLES') else []
MAX_GENERATION_TOKEN = os.getenv('MAX_GENERATION_TOKEN') or 20

class SplitBillView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, people: list, items: list, prices: list, sub_total: float, total: float):
        super().__init__()
        # Initialize variables
        self.interaction = interaction
        self.people = people
        self.items = items
        self.prices = prices
        self.sub_total = sub_total
        self.total = total
        self.data = [] # [{"name": "Item one", "price": 10.0, "people": ["Person One", "Person Two"]}]
        self.person_sub_total = {} # {"Person One": 8.0, "Person Two": 2.0}
        self.person_percentage = {} # {"Person One": 0.8, "Person Two": 0.2}
        self.current_page = 1
        self.max_page = len(self.items)
        self.embed = discord.Embed(title=f"Split Bill Calculator ({self.current_page}/{self.max_page})")

    async def start(self):
        # Initialize the data
        for item, price in zip(self.items, self.prices):
            self.data.append({"name": item, "price": price, "people": []})

        # Populate select options
        self.people_Select.options.clear()
        for person in self.people:
            self.people_Select.add_option(label=person)
        self.people_Select.max_values = len(self.people)

        # Display the view
        await self.interaction.response.send_message(view=self, embed=self.embed)
        await self.update_page()
    
    async def update_page(self):
        # Check if all items have been split
        done = True
        for item in self.data:
            if not item["people"]:
                done = False
                break

        # Update buttons
        if self.current_page == 1:
            self.previous_button.disabled = True
        else:
            self.previous_button.disabled = False

        self.done_button.disabled = not done

        if self.current_page == self.max_page:
            self.next_button.disabled = True
        else:
            self.next_button.disabled = False            

        # Update the page
        self.embed.clear_fields()
        self.embed.title = f"Split Bill Calculator ({self.current_page}/{self.max_page})"
        self.embed.add_field(name=self.data[self.current_page-1]["name"], value=f"${self.data[self.current_page-1]['price']} ({', '.join(self.data[self.current_page-1]['people'])})", inline=False)
        await self.interaction.edit_original_response(view=self, embed=self.embed)

    async def display_result(self):        
        self.embed.clear_fields()
        self.embed.title = f"Split Bill Calculator"

        # Calculate the total amount
        for item in self.data:
            for person in item["people"]:
                self.person_sub_total[person] = self.person_sub_total.get(person, 0) + float(item["price"] / len(item["people"]))

        # Calculate the percentage
        for person in self.people:
            self.person_percentage[person] = self.person_sub_total.get(person, 0) / self.sub_total

        # Display the result
        total = 0
        for person, percentage in self.person_percentage.items():
            share = math.ceil((percentage * self.total) * 100) / 100
            self.embed.add_field(name=person, value=f"${share:.2f} ({percentage * 100:.2f}%)", inline=False)
            total += share
        
        # Calculate total
        self.embed.add_field(name="Total", value=f"${total:.2f}", inline=False)

        self.clear_items()
        await self.interaction.edit_original_response(view=self, embed=self.embed)        
        self.stop()

    @discord.ui.select(cls=discord.ui.Select, options=[], placeholder="Select people to split the item.", row=2)
    async def people_Select(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer()
        self.data[self.current_page-1]["people"] = self.people_Select.values
        await self.update_page()

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary, row=3)
    async def previous_button(self, interaction:discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_page -= 1
        await self.update_page()
    
    @discord.ui.button(label="DONE", style=discord.ButtonStyle.green, row=3, disabled=True)
    async def done_button(self, interaction:discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.display_result()

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary, row=3)
    async def next_button(self, interaction:discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_page += 1
        await self.update_page()

class Commands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Commands cog loaded")

    @app_commands.command(name="profile", description="Shows your profile")
    async def profile(self, interaction: discord.Interaction):
        database = self.bot.get_cog("Database")
        user = interaction.user
        generation_token = await database.get_generation_token(user)
        await interaction.response.send_message(embed=discord.Embed(title=f"{user.display_name}'s Profile", description=f"Generation Token: {generation_token}/{MAX_GENERATION_TOKEN}"))

    @app_commands.command(name="roleadd", description="Add a role to yourself")
    @app_commands.describe(
        role="The role to add to yourself"
    )
    async def roleadd(self, interaction: discord.Interaction, role: str):
        if role not in USER_ROLES:
            await interaction.response.send_message(f'Role "{role}" is invalid.', ephemeral=True)
            return

        guild = interaction.guild
        member = guild.get_member(interaction.user.id)
        role = discord.utils.get(guild.roles, name=role)

        if role in member.roles:
            await interaction.response.send_message(f'You already have the "{role.name}" role.', ephemeral=True)
            return

        await member.add_roles(role)
        await interaction.response.send_message(f'You have received the "{role.name}" role.', ephemeral=True)

    @app_commands.command(name="roleremove", description="Remove a role from yourself")
    @app_commands.describe(
        role="The role to remove from yourself"
    )
    async def roleremove(self, interaction: discord.Interaction, role: str):
        if role not in USER_ROLES:
            await interaction.response.send_message(f'Role "{role}" is invalid.', ephemeral=True)
            return

        guild = interaction.guild
        member = guild.get_member(interaction.user.id)
        role = discord.utils.get(guild.roles, name=role)

        if role not in member.roles:
            await interaction.response.send_message(f'You don\'t have the "{role.name}" role.', ephemeral=True)
            return
        
        await member.remove_roles(role)
        await interaction.response.send_message(f'You have lost the "{role.name}" role.', ephemeral=True)

    @app_commands.command(name="split", description="Split the bill between people.")
    @app_commands.describe(
        people="The list of people to split the bill seperated by commas. Ex: John, Jane, Doe",
        items="The list of items seperated by commas. Ex: Item one, Item two, Item three",
        prices="The list of prices seperated by commas (without $). Ex: 10.0, 15.0, 10.0 (The number of prices must be the same as the number of items!)",
        total="The total amount of the bill after tax, tips, cashback, etc."
    )
    async def split(self, interaction: discord.Interaction, people: str, items: str, prices: str, total: float):
        if total <= 0:
            await interaction.response.send_message("The total amount must be greater than zero.", ephemeral=True)
            return
        
        itemList = []
        for item in items.split(","):
            itemList.append(item.strip())
        
        priceList = []
        for price in prices.split(","):
            try:
                float_price = float(price.strip())
                rounded_price = math.ceil(float_price * 100) / 100
                priceList.append(rounded_price)
            except ValueError:
                await interaction.response.send_message("The prices must be valid numbers.", ephemeral=True)
                return
        
        if len(itemList) != len(priceList):
            await interaction.response.send_message("The number of items and prices must be the same.", ephemeral=True)
            return
        
        sub_total = sum(priceList)
        if sub_total <= 0:
            await interaction.response.send_message("The sum of the prices must be greater than zero.", ephemeral=True)
            return
        
        peopleList = []
        for person in people.split(","):
            peopleList.append(person.strip())    

        splitBillView = SplitBillView(interaction, peopleList, itemList, priceList, sub_total, total)
        await splitBillView.start()

async def setup(bot: commands.Bot):
    await bot.add_cog(Commands(bot))
