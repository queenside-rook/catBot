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

print(splash.title)

USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHAT_EDIT, AuthScope.USER_BOT, AuthScope.CHANNEL_BOT]

db = TinyDB('quotes.json')

try:
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
vip_only = false # set to true if you only want VIPs and mods to be able to quote streamers directly with !quote "text"
super_vip_only = false # set to true if you only want VIPs and mods to be able to use !quote to quote anyone at all
subs_only = false # as above but for subs, VIPs, and mods
super_subs_only = false # as above but for subs, VIPs, and mods"""
    with open("catBot.toml", mode="w") as fp:
        fp.write(catBottoml)

input()

def get_last_quote():
    db_list = db.all()
    return db_list[-1].doc_id

def insert_quote(key, date, user, category, quote, quoter):
    quote_data = {
        "key": key,
        "date": date,
        "user": user,
        "category": category,
        "quote": quote,
        "quoter": quoter
        }

    db.insert(quote_data)

def delete_quote(index):
    db.remove(doc_ids=[int(index)])

def update_quote(index, new_quote):
    db.update({ 'quote' : new_quote }, doc_ids=[int(index)])

def check_key(key):
    check = db.get(Query().key == key)
    if check != None:
        return True
    else:
        return False

def check_index(index):
    check = db.get(doc_id=index)
    if check != None:
        return True
    else:
        return False

async def find_quote(index = None, key = None):
    if len(db) == 0:
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
            await chat.send_message(TARGET_CHANNEL, quote)
            await chat.send_message(TARGET_CHANNEL, tomlstr.get("keyed").format(key=key,user=user,date=date,ID=ID,quoter=quoter))
        else:
            await chat.send_message(TARGET_CHANNEL, quote)
            await chat.send_message(TARGET_CHANNEL, tomlstr.get("unkeyed").format(key=key,user=user,date=date,ID=ID,quoter=quoter))

    except Exception as e:
        raise Exception(
            "The following error occurred: ", e)

def is_auth(msg):
    if tomlset.get("vip_only") and not (msg.user.vip or msg.user.mod or msg.user.id == channel_id):
        return False
    elif tomlset.get("subs_only") and not (msg.user.vip or msg.user.mod or msg.user.subscriber or msg.user.id == channel_id):
        return False
    else:
        return True

def is_super_auth(msg):
    if tomlset.get("super_vip_only") and not (msg.user.vip or msg.user.mod or msg.user.id == channel_id):
        return False
    elif tomlset.get("super_subs_only") and not (msg.user.vip or msg.user.mod or msg.user.subscriber or msg.user.id == channel_id):
        return False
    else:
        return True

async def on_ready(ready_event: EventData):
    await ready_event.chat.join_room(TARGET_CHANNEL)

async def on_message(msg: ChatMessage):
    if msg.user.id in ignored_list:
        return
    if re.search("^!quote", msg.text) != None:
        if msg.reply_parent_msg_body != None:
            if not is_super_auth(msg):
                return
            command = re.search("^@[A-Za-z_]* !quote( |)(?P<key>!.*$|$)", msg.text)
            if command != None:
                key = command.group(2)
                date = datetime.now().strftime("%m/%d/%y")
                user = msg.reply_parent_user_id
                category = re.search('game_name=(?P<name>.*?),', str(list(await twitch.get_channel_information(channel_id))[0])).group('name')
                quote = msg.reply_parent_msg_body.replace("\\s", " ")
                quoter = msg.user.id
                insert_quote(key, date, user, category, quote, quoter)
                ID = get_last_quote()

                await chat.send_message(TARGET_CHANNEL, tomlstr.get("save_success_unkeyed").format(user=user,date=date,ID=ID,quoter=quoter))

        elif re.search("^!quote (?P<number>\\d*$)", msg.text) != None:
            command = re.search("^!quote (?P<number>\\d*$)", msg.text)
            if command != None and check_index(command.group(1)):
                await find_quote(int(command.group(1)))
            else:
                ID = command.group(1)

                await chat.send_message(TARGET_CHANNEL, tomlstr.get("invalid_ID").format(ID=ID))

        elif re.search("^!quote (?P<key>![^ ]*$)", msg.text):
            command = re.search("^!quote (?P<key>![^ ]*$)", msg.text)
            if command != None:
                await find_quote(None, command.group(1))

        elif re.search("(?P<command>^!quote) *(?P<key>![^ ]*|) *(?P<user>@[A-Za-z_]*|) *\"(?P<quote>.*)\"$", msg.text):
            if not is_super_auth(msg):
                return
            command = re.search("(?P<command>^!quote) *(?P<key>![^ ]*|) *(?P<user>@[A-Za-z_]*|) *\"(?P<quote>.*)\"$", msg.text)
            if command.group(4) == "":
                return
            if command.group(2) == "" and command.group(3) == "":
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

                await chat.send_message(TARGET_CHANNEL, tomlstr.get("save_success_unkeyed").format(user=user,date=date,ID=ID,quoter=quoter))

            elif command.group(2) != "" and command.group(3) == "":
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

                    await chat.send_message(TARGET_CHANNEL, tomlstr.get("save_success_keyed").format(key=key,user=user,date=date,ID=ID,quoter=quoter))

            elif command.group(2) == "" and command.group(3) != "":
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

                await chat.send_message(TARGET_CHANNEL, tomlstr.get("save_success_unkeyed").format(user=user,date=date,ID=ID,quoter=quoter))

            elif command.group(2) != "" and command.group(3) != "":
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

                    await chat.send_message(TARGET_CHANNEL, tomlstr.get("save_success_keyed").format(key=key,user=user,date=date,ID=ID,quoter=quoter))

        elif re.search("^!quote$", msg.text):
            await find_quote()

        elif re.search("^!quote -\\d$", msg.text):
            if int(re.search("-(\\d)", msg.text).group(1)) > len(db):
                await chat.send_message(TARGET_CHANNEL, "Requested negative index is too large!")
            else:
                quote_id = db.all()[int(re.search("(-\\d)", msg.text).group(1))].doc_id

                await find_quote(quote_id)

        elif re.search("^!quote delete \\d$", msg.text):
            if not msg.user.mod and not msg.user.id == channel_id:
                return
            delete_quote(int(re.search("^!quote delete (\\d$)", msg.text).group(1)))
            ID = re.search("^!quote delete (\\d$)", msg.text).group(1)

            await chat.send_message(TARGET_CHANNEL, tomlstr.get("delete_success").format(ID=ID))

        elif re.search("^!quote update (\\d) \"(.*)\"", msg.text):
            if not msg.user.mod and not msg.user.id == channel_id:
                return
            update_quote(re.search("^!quote update (\\d) \"(.*)\"", msg.text).group(1), re.search("^!quote update (\\d) \"(.*)\"", msg.text).group(2))
            ID = db.search(index=re.search("^!quote update (\\d) \"(.*)\"", msg.text).group(1))

            await chat.send_message(TARGET_CHANNEL, tomlstr.get("update_success").format(ID=ID))

        elif re.search("^!quote help$", msg.text):
            await chat.send_message(TARGET_CHANNEL, "Find out how to use !quote at https://github.com/queenside-rook/catBot/blob/main/README.md")

def already_running(title, text, style):
    atexit.unregister(exit_script)
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)

async def stop_loop(option=None):
        system('cls' if name == 'nt' else 'clear')
        print(splash.title2)
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

    if twitch_data.get("refresh_token") != "":
        token, refresh_token = twitch_data.get("token"), twitch_data.get("refresh_token")
    else:
        token, refresh_token = await auth.authenticate()
        cache_db.update({'Twitch Tokens' : {
            'token' : token,
            'refresh_token' : refresh_token }})

    try:
        await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)
    except Exception:
        token, refresh_token = await auth.authenticate()
        
        cache_db.update({'Twitch Tokens' : {
            'token' : token,
            'refresh_token' : refresh_token }})
        try:
            await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)
        except Exception:
            print("Unrecoverable error.")

    global ignored_list
    ignored = twitch.get_users(None, list(tomlset.get("ignore")))
    ignored_list = []
    async for data in ignored:
        ignored = data.id
        ignored_list.append(ignored)

    chat = await Chat(twitch, no_shared_chat_messages=False)
    channel_data = twitch.get_users(logins=TARGET_CHANNEL)
    async for data in channel_data:
        channel_id = data
    channel_id = channel_id.id

    chat.register_event(ChatEvent.READY, on_ready)
    chat.register_event(ChatEvent.MESSAGE, on_message)

    chat.start()

    await stop_loop()

async def initialize_cache():
    system('cls' if name == 'nt' else 'clear')
    print(splash.title2)
    KEY = input('Desired password: ')
    PATH = 'cache.encrypted_db'
    cache_db = TinyDB(encryption_key=KEY, path=PATH, storage=tae.EncryptedJSONStorage)
    APP_ID = input('Input Twitch App Client ID: ')
    APP_SECRET = input('Input Twitch App Client Secret: ')
    TARGET_CHANNEL = input('Channel for bot to operate in: ')
    cache_db.insert({'Bot Info' : {
        'APP_ID' : APP_ID.replace("\n", ""),
        'APP_SECRET' : APP_SECRET.replace("\n", ""),
        'TARGET_CHANNEL' : TARGET_CHANNEL.replace("\n", "") }})
    cache_db.insert({'Twitch Tokens' : {
            'token' : '',
            'refresh_token' : '' }})
    exit_script()
    await startup_checks()


def get_cache():
    global cache_db
    system('cls' if name == 'nt' else 'clear')
    print(splash.title2)
    KEY = input('\nPassword: ')
    if KEY == '':
        cache_db = False
    try:
        cache_db = TinyDB(encryption_key=KEY, path='cache.encrypted_db', storage=tae.EncryptedJSONStorage)
    except ValueError:
        print("Invalid password!")
        get_cache()

async def user_input():

    system('cls' if name == 'nt' else 'clear')
    print(splash.title2)
    print("\nType START to start the quote bot. If this is your first time running the program, start here.")
    print("Type EXIT to exit.")
    print("Type CHANGEPASS to change your password.")
    print("Type CHANGEBOT to change your Client ID and Client Secret or your Target Channel.\n")
    option = input().lower()
    if option == "start":
        system('cls' if name == 'nt' else 'clear')
        print(splash.title2)
        await startup_checks()
    elif option == "exit":
        return
    elif option == "changepass":
        system('cls' if name == 'nt' else 'clear')
        print(splash.title2)
        try:
            password = input('\nEnter current password: ')
            cache_db = TinyDB(encryption_key=password, path='cache.encrypted_db', storage=tae.EncryptedJSONStorage)
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
        system('cls' if name == 'nt' else 'clear')
        print(splash.title2)
        try:
            password = input('\nEnter password: ')
            cache_db = TinyDB(encryption_key=password, path='cache.encrypted_db', storage=tae.EncryptedJSONStorage)
            cache_db.all()
            option = input("\nEnter APP to change Twitch App information. Enter CHANNEL to change target channel.\n\n").lower()
            if option == "app":
                APP_ID = input('Input Twitch App Client ID: ')
                APP_SECRET = input('Input Twitch App Client Secret: ')
                cache_db.update({ 'Bot Info' : {
                    'APP_ID' : APP_ID.replace("\n", ""),
                    'APP_SECRET' : APP_SECRET.replace("\n", ""),
                    'TARGET_CHANNEL' : cache_db.get(doc_id=1).get('Bot Info').get("TARGET_CHANNEL")}}, doc_ids=[1])
                print("\n\033[92mUpdate successful. Press ENTER to continue.\033[0m")
                input()
                await user_input()
            elif option == "channel":
                TARGET_CHANNEL = input('Channel for bot to operate in: ')
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
    program_running = path.isfile('running.temp')
    if not program_running:
        with open('running.temp', 'w') as fp:
            pass
        atexit.register(exit_script)
        if path.isfile('cache.encrypted_db'):
            get_cache()
            if cache_db != False:
                try:
                    global bot_data
                    global twitch_data
                    bot = 'APP_ID'
                    twitch_tokens = 'Twitch Tokens'
                    bot_data = cache_db.get(doc_id=1).get('Bot Info')
                    twitch_data = cache_db.get(doc_id=2).get('Twitch Tokens')
                    await start_bot()
                except ValueError:
                    print("Invalid password! Press ENTER to return to main menu.")
                    input()
                    exit_script()
                    await user_input()
        else:
            print("\nNo cache found. Running cache initializer.\n")
            initialize_cache()
    else:
        already_running('Error', 'Bot already running! If you believe this is in error, delete running.temp', 0)

def exit_script():
    try:
        remove("running.temp")
    except FileNotFoundError:
        return

asyncio.run(user_input())
