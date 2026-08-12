from twitchAPI.twitch import Twitch
import twitchAPI.helper
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatMessage

import ctypes
from os import access, path, remove, system, name
import atexit

import json
import tomllib
import re
from random import choice
from datetime import datetime

from tinydb import TinyDB, Query
import tinydb_encrypted_jsonstorage as tae
import asyncio

import splash

import sys

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--debug", action="store_true")
args = parser.parse_args()
debug = args.debug
print(debug)

if debug:
    print(splash.title_debug)
else:
    print(splash.title)

if debug:
    print("Setting user scopes")
USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHAT_EDIT, AuthScope.USER_BOT, AuthScope.CHANNEL_BOT]

if debug:
    print("Fetching quotes DB")
db = TinyDB('quotes.json')

try:
    if debug:
        print("Opening toml file")
    with open("catBot.toml", "rb") as f:
        toml = tomllib.load(f)
        tomlstr = toml.get("format_strings")
        tomlset = toml.get("settings")
except FileNotFoundError:
    print("\033[91mcatBot.toml missing! A new one will be generated for you.\033[0m")
    catBottoml = """[format_strings]
# Available variables are {ID}, {key}, {date}, {user}, {category}, and {quoter}
empty_db = "No quotes found!" # message if your quote database is empty; takes no variables
keyed = "- {user} on {date} ( Quoted by {quoter} with ID #{ID} and key {key} )"
unkeyed = "- {user} on {date} ( Quoted by {quoter} with ID: #{ID} )" # takes any variable but {key}
key_exists = "Quote with key {key} already exists!" # only takes the variable {key}
save_success_keyed = "Successfully saved quote with ID #{ID} and key {key}"
save_success_unkeyed = "Successfully saved quote with ID #{ID}!" # takes any variable but {key}
delete_success = "Successfully deleted quote!" # only takes the variable {ID}
update_success = "Successfully update quote!" # only takes the variable {ID}
invalid_ID = "No quote with ID #{ID} found!" # only takes the variable {ID}
invalid_key = "No quote with key {key} found!" # only takes the variable {key}

[settings]
ignore = ["streamelements", "nightbot"] # list all users (such as your bots) you want to be ignored by catBot
using_bot = true # set to false if you're using your broadcaster account as the bot
vip_only = false # set to true if you only want VIPs and mods to be able to quote streamers directly with !quote "text"
super_vip_only = false # set to true if you only want VIPs and mods to be able to use !quote to quote anyone at all
subs_only = false # as above but for subs, VIPs, and mods
super_subs_only = false # as above but for subs, VIPs, and mods"""
    with open("catBot.toml", mode="w") as fp:
        fp.write(catBottoml)

if debug: 
    input("Checking input: \n")
else:
    input()

def print_splash():
    if not debug:
        system('cls' if name == 'nt' else 'clear')
        print(splash.title2)

def get_last_quote():
    if debug:
        print("Getting most recent quote index")
    db_list = db.all()
    return db_list[-1].doc_id

def insert_quote(key, date, user, category, quote, quoter):
    if debug:
        print("Inserting quote")
    quote_data = {
        "key": key,
        "date": date,
        "user": user,
        "category": category,
        "quote": quote,
        "quoter": quoter
        }
    if debug:
        print(quote_data)
    db.insert(quote_data)

def delete_quote(index):
    if debug:
        print(f"Deleting quote {index}")
    db.remove(doc_ids=[int(index)])

def update_quote(index, new_quote):
    if debug:
        print(f"Updating quote {index} to {new_quote}")
    db.update({ 'quote' : new_quote }, doc_ids=[int(index)])

def check_key(key):
    if debug:
        print(f"Checking key {key}")
    check = db.get(Query().key == key)
    if check != None:
        if debug:
            print("Key found")
        return True
    else:
        if debug:
            print("Key not found")
        return False

def check_index(index):
    if debug:
        print(f"Checking index {index}")
    check = db.get(doc_id=index)
    if check != None:
        if debug:
            print("Index found")
        return True
    else:
        if debug:
            print("Index not found")
        return False

async def find_quote(index = None, key = None):
    if debug:
        print(f"Finding quote. Index = {index} and key = {key}")
    if len(db) == 0:
        if debug:
            print("Database empty")
        await chat.send_message(TARGET_CHANNEL, tomlstr.get('empty_db'))
        return
    try:
        if key != None:
            if check_key(key):
                results = db.get(Query().key == key)
            else:
                await chat.send_message(TARGET_CHANNEL, tomlstr.get('invalid_key').format(key=key))
                return
        elif index != None:
            results = db.get(doc_id=int(index))
            if results == None:
                return None
        else:
            all_quotes = db.all()
            if debug:
                print("Finding random quote")
            results = choice(all_quotes)

        user = twitch.get_users(results.get("user"))
        async for document in user:
            user = document
        user = user.display_name
        quoter = twitch.get_users(results.get("quoter"))
        async for document in quoter:
            quoter = document
        quoter = quoter.display_name
        quote = results.get("quote")
        date = results.get("date")
        ID = results.doc_id
        key = results.get("key")

        if key != "":
            if debug:
                print("No key. Sending chat message")
            await chat.send_message(TARGET_CHANNEL, quote)
            await chat.send_message(TARGET_CHANNEL, tomlstr.get("keyed").format(key=key,user=user,date=date,ID=ID,quoter=quoter))
        else:
            if debug:
                print("Sending keyed chat message")
            await chat.send_message(TARGET_CHANNEL, quote)
            await chat.send_message(TARGET_CHANNEL, tomlstr.get("unkeyed").format(key=key,user=user,date=date,ID=ID,quoter=quoter))

    except Exception as e:
        raise Exception(
            "The following error occurred: ", e)

def is_auth(msg):
    if tomlset.get("vip_only") and not (msg.user.vip or msg.user.mod or msg.user.id == channel_id):
        if debug:
            print("Auth failed due to vip_only")
        return False
    elif tomlset.get("subs_only") and not (msg.user.vip or msg.user.mod or msg.user.subscriber or msg.user.id == channel_id):
        if debug:
            print("Auth failed due to subs_only")
        return False
    else:
        if debug:
            print("Passed auth")
        return True

def is_super_auth(msg):
    if tomlset.get("super_vip_only") and not (msg.user.vip or msg.user.mod or msg.user.id == channel_id):
        if debug:
            print("Auth failed due to super_vip_only")
        return False
    elif tomlset.get("super_subs_only") and not (msg.user.vip or msg.user.mod or msg.user.subscriber or msg.user.id == channel_id):
        if debug:
            print("Auth failed due to super_subs_only")
        return False
    else:
        if debug:
            print("Passed super auth")
        return True

async def on_ready(ready_event: EventData):
    if debug:
        print("Bot is ready and joining chat rooms")
    await ready_event.chat.join_room(TARGET_CHANNEL)

async def on_message(msg: ChatMessage):
    if debug:
        print("Chat message detected")
    if msg.user.id in ignored_list:
        if debug:
            print(f"{msg.user.display_name}'s message ignored")
        return
    if re.search("!quote", msg.text) != None:
        if debug:
            print("!quote detected")
        if msg.reply_parent_msg_body != None:
            if debug:
                print("Message is reply. Checking is_super_auth()")
            if not is_super_auth(msg):
                return
            command = re.search("^@[A-Za-z_]* !quote( |)(?P<key>!.*$|$)", msg.text)
            if command != None:
                if debug:
                    print("Reply with command detected.")
                key = command.group(2)
                date = datetime.now().strftime("%m/%d/%y")
                user = msg.reply_parent_user_id
                category = re.search('game_name=(?P<name>.*?),', str(list(await twitch.get_channel_information(channel_id))[0])).group('name')
                quote = msg.reply_parent_msg_body.replace("\\s", " ")
                quoter = msg.user.id
                insert_quote(key, date, user, category, quote, quoter)
                ID = get_last_quote()
                if re.search("^!quote", quote):
                    if debug:
                        print("Cannot save quotes beginning with !quote")
                    await chat.send_message(TARGET_CHANNEL, 'Cannot save quotes beginning with \"!quote\"')
                    return

                await chat.send_message(TARGET_CHANNEL, tomlstr.get("save_success_unkeyed").format(user=user,date=date,ID=ID,quoter=quoter))

        elif re.search("^!quote (?P<number>\\d*$)", msg.text) != None:
            if debug:
                print("!quote <#> detected")
            command = re.search("^!quote (?P<number>\\d*$)", msg.text)
            if command != None and check_index(command.group(1)):
                await find_quote(int(command.group(1)))
            else:
                ID = command.group(1)

                await chat.send_message(TARGET_CHANNEL, tomlstr.get("invalid_ID").format(ID=ID))

        elif re.search("^!quote (?P<key>![^ ]*$)", msg.text):
            if debug:
                print("!quote <!key> detected")
            command = re.search("^!quote (?P<key>![^ ]*$)", msg.text)
            if command != None:
                await find_quote(None, command.group(1))

        elif re.search("(?P<command>^!quote) *(?P<key>![^ ]*|) *(?P<user>@[A-Za-z_]*|) *\"(?P<quote>.*)\"$", msg.text):
            if debug:
                print("Manual !quote detected. Checking super auth")
            if not is_super_auth(msg):
                return
            command = re.search("(?P<command>^!quote) *(?P<key>![^ ]*|) *(?P<user>@[A-Za-z_]*|) *\"(?P<quote>.*)\"$", msg.text)
            if command.group(4) == "":
                if debug:
                    print("Empty string detected. Stopping insert.")
                return
            if command.group(2) == "" and command.group(3) == "":
                if debug:
                    print("No key and no @ detected. Checking auth")
                if not is_auth(msg):
                    return
                key = command.group(2)
                date = datetime.now().strftime("%m/%d/%y")
                if msg.source_room_id == None:
                    user = channel_id
                else:
                    user = msg.source_room_id
                category = re.search('game_name=(?P<name>.*?),', str(list(await twitch.get_channel_information(channel_id))[0])).group('name')
                quote = command.group(4)
                quoter = msg.user.id
                insert_quote(key, date, user, category, quote, quoter)
                ID = get_last_quote()
                if re.search("^!quote", quote):
                    await chat.send_message(TARGET_CHANNEL, 'Cannot save quotes beginning with \"!quote\"')
                    return

                await chat.send_message(TARGET_CHANNEL, tomlstr.get("save_success_unkeyed").format(user=user,date=date,ID=ID,quoter=quoter))

            elif command.group(2) != "" and command.group(3) == "":
                if debug:
                    print("Key and no @ detected. Checking auth")
                if not is_auth(msg):
                    return
                if check_key(command.group(2)):
                    key = command.group(2)

                    await chat.send_message(TARGET_CHANNEL, tomlstr.get("key_exists").format(key=key))
                else:
                    key = command.group(2)
                    date = datetime.now().strftime("%m/%d/%y")
                    if msg.source_room_id == None:
                        user = channel_id
                    else:
                        user = msg.source_room_id
                    category = re.search('game_name=(?P<name>.*?),', str(list(await twitch.get_channel_information(channel_id))[0])).group('name')
                    quote = command.group(4)
                    quoter = msg.user.id
                    insert_quote(key, date, user, category, quote, quoter)
                    ID = get_last_quote()
                    if re.search("^!quote", quote):
                        await chat.send_message(TARGET_CHANNEL, 'Cannot save quotes beginning with \"!quote\"')
                        return

                    await chat.send_message(TARGET_CHANNEL, tomlstr.get("save_success_keyed").format(key=key,user=user,date=date,ID=ID,quoter=quoter))

            elif command.group(2) == "" and command.group(3) != "":
                if debug:
                    print("No key and @ found")
                if not is_auth(msg):
                    return
                key = command.group(2)
                date = datetime.now().strftime("%m/%d/%y")
                user = command.group(3).replace("@","")
                user = twitch.get_users(None, user)
                async for document in user:
                    user = document
                user = user.id
                category = re.search('game_name=(?P<name>.*?),', str(list(await twitch.get_channel_information(channel_id))[0])).group('name')
                quote = command.group(4)
                quoter = msg.user.id
                insert_quote(key, date, user, category, quote, quoter)
                ID = get_last_quote()
                if re.search("^!quote", quote):
                    await chat.send_message(TARGET_CHANNEL, 'Cannot save quotes beginning with \"!quote\"')
                    return

                await chat.send_message(TARGET_CHANNEL, tomlstr.get("save_success_unkeyed").format(user=user,date=date,ID=ID,quoter=quoter))

            elif command.group(2) != "" and command.group(3) != "":
                if debug:
                    print("Key and @ found")
                if check_key(command.group(2)):
                    key = command.group(2)

                    await chat.send_message(TARGET_CHANNEL, tomlstr.get("key_exists").format(key=key,user=user,date=date,ID=ID,quoter=quoter))
                else:
                    key = command.group(2)
                    date = datetime.now().strftime("%m/%d/%y")
                    user = command.group(3).replace("@","")
                    user = twitch.get_users(None, user)
                    async for document in user:
                        user = document
                    user = user.id
                    category = re.search('game_name=(?P<name>.*?),', str(list(await twitch.get_channel_information(channel_id))[0])).group('name')
                    quote = command.group(4)
                    quoter = msg.user.id
                    insert_quote(key, date, user, category, quote, quoter)
                    ID = get_last_quote()
                    if re.search("^!quote", quote):
                        await chat.send_message(TARGET_CHANNEL, 'Cannot save quotes beginning with \"!quote\"')
                        return

                    await chat.send_message(TARGET_CHANNEL, tomlstr.get("save_success_keyed").format(key=key,user=user,date=date,ID=ID,quoter=quoter))

        elif re.search("^!quote$", msg.text):
            await find_quote()

        elif re.search("^!quote -\\d$", msg.text):
            if debug:
                print("!quote negative index detected")
            if int(re.search("-(\\d)", msg.text).group(1)) > len(db):
                if debug:
                    print("Index too large")
                await chat.send_message(TARGET_CHANNEL, "Requested negative index is too large!")
            else:
                quote_id = db.all()[int(re.search("(-\\d)", msg.text).group(1))].doc_id

                await find_quote(quote_id)

        elif re.search("^!quote delete \\d$", msg.text):
            if debug:
                print("!quote delete detected")
            if not msg.user.mod and not msg.user.id == channel_id:
                return
            delete_quote(int(re.search("^!quote delete (\\d$)", msg.text).group(1)))
            ID = re.search("^!quote delete (\\d$)", msg.text).group(1)

            await chat.send_message(TARGET_CHANNEL, tomlstr.get("delete_success").format(ID=ID))

        elif re.search("^!quote update (\\d) \"(.*)\"", msg.text):
            if debug:
                print("!quote update detected")
            if not msg.user.mod and not msg.user.id == channel_id:
                return
            update_quote(re.search("^!quote update (\\d) \"(.*)\"", msg.text).group(1), re.search("^!quote update (\\d) \"(.*)\"", msg.text).group(2))
            ID = db.search(index=re.search("^!quote update (\\d) \"(.*)\"", msg.text).group(1))

            await chat.send_message(TARGET_CHANNEL, tomlstr.get("update_success").format(ID=ID))

        elif re.search("^!quote help$", msg.text):
            if debug:
                print("!quote help detected")
            await chat.send_message(TARGET_CHANNEL, "Find out how to use !quote at https://github.com/queenside-rook/catBot/blob/main/README.md")

def already_running(title, text, style):
    if debug:
        print("Bot is already running or running.temp did not get removed properly")
    atexit.unregister(exit_script)
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)

async def stop_loop(option=None):
    if debug:
        print("stop_loop() called")
    print_splash()
    print(f'\nBot is running on channel {TARGET_CHANNEL}. Type STOP to stop the quote bot.\n')
    if option == None:
        option = input().lower()
    if option == "stop":
        chat.stop()
        await twitch.close()
        exit_script()
        await user_input()
    else:
        print("\n\033[93mInvalid input. Press ENTER to continue.\033[0m\n")
        input()
        await stop_loop()

async def start_bot():
    if debug:
        print("start_bot() called")
    global twitch
    global auth
    global token
    global refresh_token
    global chat
    global TARGET_CHANNEL
    global channel_id

    APP_ID, APP_SECRET, TARGET_CHANNEL = bot_data.get("APP_ID"), bot_data.get("APP_SECRET"), bot_data.get("TARGET_CHANNEL")
    twitch = await Twitch(APP_ID, APP_SECRET)
    auth = UserAuthenticator(twitch, USER_SCOPE)
    
    if debug:
        print("Checking for refresh token")
    if twitch_data.get("refresh_token") != "":
        if debug:
            print("Token found.")
        token, refresh_token = twitch_data.get("token"), twitch_data.get("refresh_token")
    else:
        if debug:
            print("Token not found. Opening browser to fetch tokens")
        token, refresh_token = await auth.authenticate()
        if debug:
            print("Saving tokens to encrypted db")
        cache_db.update({'Twitch Tokens' : {
            'token' : token,
            'refresh_token' : refresh_token }})

    try:
        if debug:
            print("Setting user authentication.")
        await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)
    except Exception:
        if debug:
            print("Tokens invalid. Fetching new tokens.")
        token, refresh_token = await auth.authenticate()
        if debug:
            print("Saving token to encrypted db")
        cache_db.update({'Twitch Tokens' : {
            'token' : token,
            'refresh_token' : refresh_token }})
        try:
            if debug:
                print("Re-attempting user authentication")
            await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)
        except Exception as e:
            print("Unrecoverable error.")
            print(e)
    if debug:
        print("Setting chat instance")
    chat = await Chat(twitch, no_shared_chat_messages=False)
    channel_data = twitch.get_users(logins=TARGET_CHANNEL)
    async for data in channel_data:
        channel_id = data
    channel_id = channel_id.id

    global ignored_list
    ignored = twitch.get_users(logins=list(tomlset.get("ignore")))
    bot_id = twitch.get_users()
    async for data in bot_id:
        bot_id = data.id
    ignored_list = []
    async for data in ignored:
        ignored = data.id
        ignored_list.append(ignored)
    if not tomlset.get("using_bot"):
        try:
            ignored_list.remove(bot_id)
        except Exception:
            pass
    if debug:
        print("Registering events")
    chat.register_event(ChatEvent.READY, on_ready)
    chat.register_event(ChatEvent.MESSAGE, on_message)
    if debug:
        print("Starting chat instance")
    chat.start()

    await stop_loop()

async def initialize_cache():
    if debug:
        print("Initializing cache")
    print_splash()
    KEY = input('Desired password: ')
    PATH = 'cache.encrypted_db'
    cache_db = TinyDB(encryption_key=KEY, path=PATH, storage=tae.EncryptedJSONStorage)
    APP_ID = input('Input Twitch App Client ID: ')
    APP_SECRET = input('Input Twitch App Client Secret: ')
    TARGET_CHANNEL = input('Channel for bot to operate in: ')
    if debug:
        print("Inserting data into encrypted db")
    cache_db.insert({'Bot Info' : {
        'APP_ID' : APP_ID.replace("\n", ""),
        'APP_SECRET' : APP_SECRET.replace("\n", ""),
        'TARGET_CHANNEL' : TARGET_CHANNEL.replace("\n", "") }})
    cache_db.insert({'Twitch Tokens' : {
            'token' : '',
            'refresh_token' : '' }})
    exit_script()
    if debug:
        print("Beginning startup_checks()")
    await startup_checks()


def get_cache():
    if debug:
        print("Fetching encrypted cache")
    global cache_db
    print_splash()
    KEY = input('\nPassword: ')
    if KEY == '':
        cache_db = False
    try:
        if debug:
            print("Trying password")
        cache_db = TinyDB(encryption_key=KEY, path='cache.encrypted_db', storage=tae.EncryptedJSONStorage)
    except ValueError:
        print("Invalid password!")
        get_cache()

async def user_input():
    if debug:
        print("Starting main menu")
    print_splash()
    print("\nType START to start the quote bot. If this is your first time running the program, start here.")
    print("Type EXIT to exit.")
    print("Type CHANGEPASS to change your password.")
    print("Type CHANGEBOT to change your Client ID and Client Secret or your Target Channel.\n")
    option = input().lower()
    if option == "start":
        if debug:
            print("Start selected. Beginning startup_checks()")
        print_splash()
        await startup_checks()
    elif option == "exit":
        if debug:
            print("Exit chosen")
        return
    elif option == "changepass":
        if debug:
            print("Changepass chosen")
        print_splash()
        try:
            password = input('\nEnter current password: ')
            cache_db = TinyDB(encryption_key=password, path='cache.encrypted_db', storage=tae.EncryptedJSONStorage)
            if debug:
                print("Checking password.")
            cache_db.all()
            new_pass = input('\nEnter new password: ')
            cache_db.storage.change_encryption_key(new_pass)
            print("\n\033[92mNew password saved. Press ENTER to continue.\033[0m\n")
            input()
            await user_input()
        except ValueError:
            print("\n\033[93mIncorrect original password. Press ENTER to return.\033[0m\n")
            input()
            await user_input()
    elif option == "changebot":
        if debug:
            print("Changebot chosen")
        print_splash()
        try:
            password = input('\nEnter password: ')
            cache_db = TinyDB(encryption_key=password, path='cache.encrypted_db', storage=tae.EncryptedJSONStorage)
            if debug:
                print("Checking password")
            cache_db.all()
            option = input("\nEnter APP to change Twitch App information. Enter CHANNEL to change target channel.\n\n").lower()
            if option == "app":
                if debug:
                    print("App chosen")
                APP_ID = input('Input Twitch App Client ID: ')
                APP_SECRET = input('Input Twitch App Client Secret: ')
                if debug:
                    print("Updating data in encrypted db")
                cache_db.update({ 'Bot Info' : {
                    'APP_ID' : APP_ID.replace("\n", ""),
                    'APP_SECRET' : APP_SECRET.replace("\n", ""),
                    'TARGET_CHANNEL' : cache_db.get(doc_id=1).get('Bot Info').get("TARGET_CHANNEL")}}, doc_ids=[1])
                print("\n\033[92mUpdate successful. Press ENTER to continue.\033[0m")
                input()
                await user_input()
            elif option == "channel":
                if debug:
                    print("Channel chosen")
                TARGET_CHANNEL = input('Channel for bot to operate in: ')
                if debug:
                    print("Updating data in encrypted db")
                cache_db.update({ 'Bot Info' : {
                    'APP_ID' : cache_db.get(doc_id=1).get('Bot Info').get("APP_ID"),
                    'APP_SECRET' : cache_db.get(doc_id=1).get('Bot Info').get("APP_SECRET"),
                    'TARGET_CHANNEL' : TARGET_CHANNEL}}, doc_ids=[1])
                print("\n\033[92mUpdate successful. Press ENTER to continue.\033[0m")
                input()
                await user_input()
        except ValueError:
            print("\n\033[93mIncorrect original password. Press ENTER to return.\033[0m\n")
            input()
            await user_input()
    else:
        print("\n\033[93mInvalid input. Press ENTER to continue.\033[0m")
        input()
        await user_input()

async def startup_checks():
    if debug:
        print("startup_checks() called. Checking for running.temp")
    program_running = path.isfile('running.temp')
    if not program_running:
        if debug:
            print("running.temp not found. Creating running.temp")
        with open('running.temp', 'w') as fp:
            pass
        if debug:
            print("Registering exit script")
        atexit.register(exit_script)
        if debug:
            print("Looking for encrypted cache")
        if path.isfile('cache.encrypted_db'):
            if debug:
                print("Found cache.")
            get_cache()
            if cache_db != False:
                try:
                    global bot_data
                    global twitch_data
                    bot = 'APP_ID'
                    twitch_tokens = 'Twitch Tokens'
                    bot_data = cache_db.get(doc_id=1).get('Bot Info')
                    twitch_data = cache_db.get(doc_id=2).get('Twitch Tokens')
                    if debug:
                        print("Globals bot_data and twitch_data set. Starting bot")
                    await start_bot()
                except ValueError:
                    print("Invalid password! Press ENTER to return to main menu.")
                    input()
                    exit_script()
                    await user_input()
        else:
            print("\nNo cache found. Running cache initializer.\n")
            await initialize_cache()
    else:
        already_running('Error', 'Bot already running! If you believe this is in error, delete running.temp', 0)

def exit_script():
    try:
        remove("running.temp")
        if debug:
            print("Removed running.temp")
    except FileNotFoundError:
        if debug:
            print("running.temp delete attempted, file not found")
        return

if debug:
    print("Starting...")
asyncio.run(user_input())
