from twitchAPI.twitch import Twitch
import twitchAPI.helper
from twitchAPI.oauth import UserAuthenticationStorageHelper, UserAuthenticator
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatMessage, ChatSub, ChatCommand

from pymongo import AsyncMongoClient
from pymongo import InsertOne

from psutil import process_iter
import ctypes
import tkinter as tk
import os

import json
import re
import webbrowser
from os import system
from random import randrange
from datetime import datetime

import tinydb

import asyncio

from headless_bot import get_data

"""APP_ID = 'phrykzyjna2rmxvpe5njapojtj88iw'
APP_SECRET = 'yxih292gauifeysl001646m7ncu5pn'
TARGET_CHANNEL = 'queenside_rook'"""
USER_SCOPE = [AuthScope.CHAT_READ, AuthScope.CHAT_EDIT, AuthScope.USER_BOT, AuthScope.CHANNEL_BOT]

db = tinydb.TinyDB('quotes.json')

async def get_last_quote():
    try:
        uri = "mongodb://localhost:27017/"
        client = AsyncMongoClient(uri)

        database = client["TwitchQuotes"]
        collection = database["Quotes"]

        results = collection.find()

        async for document in results:
            result_dict = document
      

        await client.close()
        
        return result_dict.get("_id")

    except Exception as e:
        raise Exception(
            "The following error occurred: ", e)

async def insert_quote(key, ID, date, user, category, quote, quoter):
    try:
        uri = "mongodb://localhost:27017/"
        client = AsyncMongoClient(uri)

        database = client["TwitchQuotes"]
        collection = database["Quotes"]
        
        quote_data = {
            "_id": ID,
            "key": key,
            "date": date,
            "user": user,
            "category": category,
            "quote": quote,
            "quoter": quoter
            }

        await collection.insert_one(quote_data)
        
        await client.close()

    except Exception as e:
        raise Exception(
            "The following error occurred: ", e)

async def check_key(key):
    try:
        uri = "mongodb://localhost:27017/"
        client = AsyncMongoClient(uri)

        database = client["TwitchQuotes"]
        collection = database["Quotes"]

        results = collection.find({"key" : key})
        try:
            await results.next()
            return True
        except StopAsyncIteration:
            return False

        await client.close()
    except Exception as e:
        raise Exception(
            "The following error occurred: ", e)

async def check_index(index):
    try:
        uri = "mongodb://localhost:27017/"
        client = AsyncMongoClient(uri)

        database = client["TwitchQuotes"]
        collection = database["Quotes"]

        results = collection.find({"_id" : index})
        try:
            await results.next()
            return True
        except StopAsyncIteration:
            return False

        await client.close()
    except Exception as e:
        raise Exception(
            "The following error occurred: ", e)

async def find_quote(index = None, key = None):
    try:
        uri = "mongodb://localhost:27017/"
        client = AsyncMongoClient(uri)

        database = client["TwitchQuotes"]
        collection = database["Quotes"]

        max_id = collection.find()

        async for document in max_id:
            result_dict = document

        max_id = int(result_dict.get("_id"))

        if key != None:
            results = collection.find({"key" : key})
        elif index != None:
            results = collection.find({"_id" : index})
        else:
            if max_id != 1:
                index = randrange(1,max_id)
            else:
                index = 1
            results = collection.find({"_id" : index})

        async for document in results:
            result_dict = document

        user = twitch.get_users(result_dict.get("user"))
        async for document in user:
            user = document
        user = user.display_name
        quoter = twitch.get_users(result_dict.get("quoter"))
        async for document in quoter:
            quoter = document
        quoter = quoter.display_name

        if result_dict.get("key") != "":
            #print(f"Quote {result_dict.get("_id")}: \"{result_dict.get("quote")}\"")
            #print(f"{user} quoted by {quoter} on {result_dict.get("date")} with key {result_dict.get("key")}")
            await chat.send_message(TARGET_CHANNEL, f"{result_dict.get("quote")}")
            await chat.send_message(TARGET_CHANNEL, f"- {user} on {result_dict.get("date")} ( Quoted by {quoter} with ID: #{result_dict.get("_id")} and key: {result_dict.get("key")} )")
        else:
            #print(f"Quote {result_dict.get("_id")}: \"{result_dict.get("quote")}\"")
            #print(f"From {user} quoted by {quoter} on {result_dict.get("date")}")
            await chat.send_message(TARGET_CHANNEL, f"{result_dict.get("quote")}")
            await chat.send_message(TARGET_CHANNEL, f"- {user} on {result_dict.get("date")} ( Quoted by {quoter} with ID: #{result_dict.get("_id")} )")

        await client.close()
    except Exception as e:
        raise Exception(
            "The following error occurred: ", e)

async def on_ready(ready_event: EventData):
    print('Bot is ready for work, joining channels')

    await ready_event.chat.join_room(TARGET_CHANNEL)

async def on_message(msg: ChatMessage):
    if re.search("^!quote", msg.text) != None:
        if msg.reply_parent_msg_body != None:
            #print(msg.reply_parent_msg_body)
            #print(msg.text)
            command = re.search("^@[A-Za-z_]* !quote( |)(?P<key>!.*$|$)", msg.text)
            if command != None:
                #print(msg.text)
                key = command.group(2)
                ID = await get_last_quote()
                ID += 1
                date = datetime.now().strftime("%m/%d/%y")
                user = str(msg.reply_parent_user_id)
                category = re.search('game_name=(?P<name>.*?),', str(list(await twitch.get_channel_information('471878036'))[0])).group('name')
                quote = msg.reply_parent_msg_body.replace("\\s", " ")
                quoter = msg.user.id
                await insert_quote(key, ID, date, user, category, quote, quoter)
                await chat.send_message(TARGET_CHANNEL, f"Successfully saved quote with ID #{ID}!")
        elif re.search("^!quote (?P<number>\\d*$)", msg.text) != None:
            command = re.search("^!quote (?P<number>\\d*$)", msg.text)
            if command != None and await check_index(int(command.group(1))):
                await find_quote(int(command.group(1)))
            else:
                await chat.send_message(TARGET_CHANNEL, f"No quote with ID #{int(command.group(1))} found!")
        elif re.search("^!quote (?P<key>![^ ]*$)", msg.text):
            command = re.search("^!quote (?P<key>![^ ]*$)", msg.text)
            if command != None:
                await find_quote(None, command.group(1))
        elif re.search("(?P<command>^!quote) *(?P<key>![^ ]*|) *(?P<user>@[A-Za-z_]*|) *\"(?P<quote>.*)\"$", msg.text):
            command = re.search("(?P<command>^!quote) *(?P<key>![^ ]*|) *(?P<user>@[A-Za-z_]*|) *\"(?P<quote>.*)\"$", msg.text)
            if command.group(2) == "" and command.group(3) == "":
                key = command.group(2)
                ID = await get_last_quote()
                ID += 1
                date = datetime.now().strftime("%m/%d/%y")
                if msg.source_room_id == None:
                    user = "471878036"
                else:
                    user = msg.source_room_id
                category = re.search('game_name=(?P<name>.*?),', str(list(await twitch.get_channel_information('471878036'))[0])).group('name')
                quote = command.group(4)
                quoter = msg.user.id
                await insert_quote(key, ID, date, user, category, quote, quoter)
                await chat.send_message(TARGET_CHANNEL, f"Successfully saved quote with ID #{ID}!")
            elif command.group(2) != "" and command.group(3) == "":
                if await check_key(command.group(2)):
                    await chat.send_message(TARGET_CHANNEL, f"Quote with key {command.group(2)} already exists!")
                else:
                    key = command.group(2)
                    ID = await get_last_quote()
                    ID += 1
                    date = datetime.now().strftime("%m/%d/%y")
                    if msg.source_room_id == None:
                        user = "471878036"
                    else:
                        user = msg.source_room_id
                    category = re.search('game_name=(?P<name>.*?),', str(list(await twitch.get_channel_information('471878036'))[0])).group('name')
                    quote = command.group(4)
                    quoter = msg.user.id
                    await insert_quote(key, ID, date, user, category, quote, quoter)
                    await chat.send_message(TARGET_CHANNEL, f"Successfully saved quote with ID #{ID} and key {key}")
            elif command.group(2) == "" and command.group(3) != "":
                key = command.group(2)
                ID = await get_last_quote()
                ID += 1
                date = datetime.now().strftime("%m/%d/%y")
                user = command.group(3).replace("@","")
                user = twitch.get_users(None, user)
                async for document in user:
                    user = document
                user = user.id
                category = re.search('game_name=(?P<name>.*?),', str(list(await twitch.get_channel_information('471878036'))[0])).group('name')
                quote = command.group(4)
                quoter = msg.user.id
                await insert_quote(key, ID, date, user, category, quote, quoter)
                await chat.send_message(TARGET_CHANNEL, f"Successfully saved quote with ID #{ID}!")
            elif command.group(2) != "" and command.group(3) != "":
                if await check_key(command.group(2)):
                    await chat.send_message(TARGET_CHANNEL, f"Quote with key {command.group(2)} already exists!")
                else:
                    key = command.group(2)
                    ID = await get_last_quote()
                    ID += 1
                    date = datetime.now().strftime("%m/%d/%y")
                    user = command.group(3).replace("@","")
                    user = twitch.get_users(None, user)
                    async for document in user:
                        user = document
                    user = user.id
                    category = re.search('game_name=(?P<name>.*?),', str(list(await twitch.get_channel_information('471878036'))[0])).group('name')
                    quote = command.group(4)
                    quoter = msg.user.id
                    await insert_quote(key, ID, date, user, category, quote, quoter)
                    await chat.send_message(TARGET_CHANNEL, f"Successfully saved quote with ID #{ID} and key {key}")
        elif re.search("^!quote$", msg.text):
            await find_quote()
        elif re.search("^!quote -\\d$", msg.text):
            quote_id = await get_last_quote() + 1 + int(re.search("(?P<number>-\\d)", msg.text).group(1))
            await find_quote(quote_id)

def already_running(title, text, style):
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)

async def start_bot():
    global twitch
    global auth
    global token
    global refresh_token
    global chat
    global TARGET_CHANNEL
    global quotesDB

    APP_ID, APP_SECRET, TARGET_CHANNEL = bot_data.get("APP_ID"), bot_data.get("APP_SECRET"), bot_data.get("TARGET_CHANNEL")
    print(APP_ID)
    print(APP_SECRET)
    print(TARGET_CHANNEL)
    twitch = await Twitch(APP_ID, APP_SECRET)
    auth = UserAuthenticator(twitch, USER_SCOPE)

    if twitch_data.get("refresh_token") != "":
        token, refresh_token = twitch_data.get("Twitch Tokens").get("token"), twitch_data.get("Twitch Tokens").get("refresh_token")
    else:
        token, refresh_token = await auth.authenticate()

    await twitch.set_user_authentication(token, USER_SCOPE, refresh_token)

    system("taskkill /im chrome.exe /f")

    chat = await Chat(twitch, no_shared_chat_messages=False)

    chat.register_event(ChatEvent.READY, on_ready)
    chat.register_event(ChatEvent.MESSAGE, on_message)

    chat.start()

    try:
        print('press ENTER to stop\n')
    finally:
        input()
        chat.stop()
        await twitch.close()

def startup_checks():
    program_running = "HydraTextClient.exe" in (p.name() for p in process_iter())
    if not program_running:
        if os.path.isfile('cache.json') and os.access('cache.json', os.R_OK):
            try:
                global bot_data
                global twitch_data
                with open('cache.json') as fp:
                    data = json.load(fp)
                #print("No error")
                data = data[0]
                bot_data = data.get("Bot Info")
                twitch_data = data.get("Twitch Tokens")
                asyncio.run(start_bot())
            except json.JSONDecodeError:
                print("Error 1")
                get_data()
        else:
            print("Error 2")
            get_data()
    else:
        already_running('Error', 'Bot already running!', 0)

startup_checks()
