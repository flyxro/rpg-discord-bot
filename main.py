import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
import random
import asyncio
from datetime import datetime, timedelta
import sys
import asyncio

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

intents = discord.Intents.all()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# MongoDB setup
client = MongoClient("")
db = client[""]
users_collection = db["users"]

# Define Character Classes with Unique Abilities
class CharacterClass:
    def __init__(self, name, health, attack, defense, ability, ability_desc):
        self.name = name
        self.health = health
        self.attack = attack
        self.defense = defense
        self.ability = ability
        self.ability_desc = ability_desc

classes = {
    "warrior": CharacterClass("Warrior", 120, 15, 10, "Power Strike", "Deals 1.5x damage"),
    "mage": CharacterClass("Mage", 90, 20, 5, "Fireball", "Burns enemy for 5 damage per turn for 3 turns"),
    "archer": CharacterClass("Archer", 100, 13, 8, "Piercing Arrow", "Ignores 50% of enemy defense"),
    "healer": CharacterClass("Healer", 80, 8, 6, "Heal", "Restores 20 health during combat"),
    "rogue": CharacterClass("Rogue", 100, 14, 7, "Backstab", "Deals 2x damage if enemy health is below 30%")
}

# Helper Functions
def get_character(user_id):
    return users_collection.find_one({"_id": user_id})

def level_up(user_id):
    character = get_character(user_id)
    if character["experience"] >= character["level"] * 100:
        users_collection.update_one({"_id": user_id}, {"$inc": {"level": 1}, "$set": {"experience": 0}})
        users_collection.update_one(
            {"_id": user_id},
            {"$inc": {"health": 10, "attack": 5, "defense": 3}}
        )

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} - Syncing global slash commands...')
    try:
        # Sync all commands globally
        await bot.tree.sync()
        print("Global slash commands synced successfully!")
    except Exception as e:
        print(f"Failed to sync commands globally: {e}")

# Character Creation
@bot.tree.command(name="create", description="Create your RPG character")
@app_commands.describe(name="Character name", character_class="Choose a character class")
async def create(interaction: discord.Interaction, name: str, character_class: str):
    if character_class not in classes:
        await interaction.response.send_message("Invalid class. Choose from: warrior, mage, archer, healer, rogue.", ephemeral=True)
        return

    user_id = interaction.user.id
    if get_character(user_id):
        await interaction.response.send_message("You already have a character!", ephemeral=True)
        return

    class_info = classes[character_class]
    character = {
        "_id": user_id,
        "name": name,
        "class": character_class,
        "level": 1,
        "experience": 0,
        "health": class_info.health,
        "attack": class_info.attack,
        "defense": class_info.defense,
        "ability": class_info.ability,
        "inventory": [],
        "gold": 50,
        "last_death": None
    }
    users_collection.insert_one(character)
    await interaction.response.send_message(f"Character {name} created as a {character_class.capitalize()} with ability: {class_info.ability_desc}")

# View Stats
@bot.tree.command(name="stats", description="Check your character stats")
async def stats(interaction: discord.Interaction):
    character = get_character(interaction.user.id)
    if not character:
        await interaction.response.send_message("You don't have a character yet! Use /create_character to get started.", ephemeral=True)
        return
    class_info = classes[character["class"]]
    stat_message = (
        f"Name: {character['name']}\n"
        f"Class: {character['class'].capitalize()}\n"
        f"Level: {character['level']}\n"
        f"Experience: {character['experience']}\n"
        f"Health: {character['health']}/{class_info.health}\n"
        f"Attack: {character['attack']}\n"
        f"Defense: {character['defense']}\n"
        f"Gold: {character['gold']}\n"
        f"Ability: {character['ability']}\n"
        f"Inventory: {', '.join(character['inventory']) if character['inventory'] else 'Empty'}"
    )
    await interaction.response.send_message(stat_message)

# PvP Challenge
@bot.tree.command(name="challenge", description="Challenge another player to PvP")
@app_commands.describe(opponent="The player you want to challenge")
async def challenge(interaction: discord.Interaction, opponent: discord.Member):
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("You can't challenge yourself!", ephemeral=True)
        return
    
    user_char = get_character(interaction.user.id)
    opponent_char = get_character(opponent.id)

    if not user_char:
        await interaction.response.send_message("You don't have a character! Use /create_character first.", ephemeral=True)
        return
    if not opponent_char:
        await interaction.response.send_message(f"{opponent.display_name} doesn't have a character!", ephemeral=True)
        return

    await interaction.response.send_message(f"{interaction.user.display_name} has challenged {opponent.display_name} to a duel!")
    await pvp_battle(interaction, user_char, opponent_char, interaction.user, opponent)

async def pvp_battle(interaction, user_char, opponent_char, user, opponent):
    user_hp, opponent_hp = user_char["health"], opponent_char["health"]
    while user_hp > 0 and opponent_hp > 0:
        opponent_hp -= max(user_char["attack"] - opponent_char["defense"], 1)
        user_hp -= max(opponent_char["attack"] - user_char["defense"], 1)
        await asyncio.sleep(1)
    
    if user_hp <= 0:
        await interaction.followup.send(f"{user.display_name} has been defeated by {opponent.display_name}!")
        users_collection.update_one({"_id": user.id}, {"$set": {"last_death": datetime.utcnow()}})
    else:
        await interaction.followup.send(f"{opponent.display_name} has been defeated by {user.display_name}!")
        users_collection.update_one({"_id": opponent.id}, {"$set": {"last_death": datetime.utcnow()}})

# Monster Command
@bot.tree.command(name="monster", description="Fight a random monster")
async def monster(interaction: discord.Interaction):
    user_char = get_character(interaction.user.id)
    if not user_char:
        await interaction.response.send_message("You don't have a character! Use /create_character first.", ephemeral=True)
        return
    
    monster_list = [
        {"name": "Goblin", "health": 60, "attack": 8, "defense": 4, "exp": 20, "gold": 15},
        {"name": "Orc", "health": 100, "attack": 12, "defense": 6, "exp": 50, "gold": 30},
        {"name": "Dragon", "health": 200, "attack": 20, "defense": 10, "exp": 200, "gold": 100, "drop": "Dragon Scale Armor"},
    ]
    monster = random.choice(monster_list)
    await interaction.response.send_message(f"A wild {monster['name']} appears! 🐉")
    await monster_battle(interaction, user_char, monster)

async def monster_battle(interaction, user_char, monster):
    user_hp, monster_hp = user_char["health"], monster["health"]
    while user_hp > 0 and monster_hp > 0:
        monster_hp -= max(user_char["attack"] - monster["defense"], 1)
        user_hp -= max(monster["attack"] - user_char["defense"], 1)
        await asyncio.sleep(1)
    
    if user_hp <= 0:
        await interaction.followup.send("You have been defeated by the monster!")
        users_collection.update_one({"_id": interaction.user.id}, {"$set": {"last_death": datetime.utcnow()}})
    else:
        reward_text = f"You defeated the {monster['name']}! You gained {monster['exp']} EXP and {monster['gold']} gold."
        if "drop" in monster:
            reward_text += f" You also obtained a rare item: {monster['drop']}!"
            users_collection.update_one({"_id": interaction.user.id}, {"$addToSet": {"inventory": monster["drop"]}})
        
        users_collection.update_one({"_id": interaction.user.id}, {"$inc": {"experience": monster["exp"], "gold": monster["gold"]}})
        await interaction.followup.send(reward_text)
        level_up(interaction.user.id)

# Solo and Team Quests
@bot.tree.command(name="quest", description="Go on a quest for rewards!")
@app_commands.describe(partner="Choose a partner for a more challenging quest")
async def quest(interaction: discord.Interaction, partner: discord.Member = None):
    user_char = get_character(interaction.user.id)
    if not user_char:
        await interaction.response.send_message("You don't have a character! Use /create_character first.", ephemeral=True)
        return

    quest_rewards = {
        "solo": {"exp": 50, "gold": 25, "item": "Mystic Cloak"},
        "team": {"exp": 150, "gold": 100, "item": "Sword of Legends"}
    }

    if partner:
        partner_char = get_character(partner.id)
        if not partner_char:
            await interaction.response.send_message(f"{partner.display_name} does not have a character!", ephemeral=True)
            return
        await interaction.response.send_message(f"{interaction.user.display_name} and {partner.display_name} embarked on a team quest!")
        reward = quest_rewards["team"]
    else:
        await interaction.response.send_message(f"{interaction.user.display_name} embarked on a solo quest!")
        reward = quest_rewards["solo"]
    
    await asyncio.sleep(3)
    users_collection.update_one({"_id": interaction.user.id}, {"$inc": {"experience": reward["exp"], "gold": reward["gold"]}, "$addToSet": {"inventory": reward["item"]}})
    if partner:
        users_collection.update_one({"_id": partner.id}, {"$inc": {"experience": reward["exp"], "gold": reward["gold"]}, "$addToSet": {"inventory": reward["item"]}})
        await interaction.followup.send(f"The team quest was a success! Both players gained {reward['exp']} EXP, {reward['gold']} gold, and found a {reward['item']}!")
    else:
        await interaction.followup.send(f"The solo quest was a success! You gained {reward['exp']} EXP, {reward['gold']} gold, and found a {reward['item']}!")
    level_up(interaction.user.id)
    if partner:
        level_up(partner.id)

@bot.tree.command(name="shop", description="Browse the shop for items")
async def shop(interaction: discord.Interaction):
    items = {
        "Basic Sword": 50,
        "Bow of Swiftness": 80,
        "Healing Potion": 20,
        "Enchanted Shield": 150,
        "Mage's Robe": 90,
        "Power Armor": 200,
        "Dragon Bow": 250,
        "Ultimate Health Potion": 100,
        "Fire Resistance Potion": 70,
        "Mystic Cloak": 180
    }
    item_list = "\n".join([f"{item}: {price} gold" for item, price in items.items()])
    await interaction.response.send_message(f"**Shop Items**:\n{item_list}")

bot.run("")