import asyncio
import atexit
import ctypes
import re
import sqlite3
from datetime import datetime
from os import path, remove
from random import choice

import tinydb_encrypted_jsonstorage as tae
import tomllib
from tinydb import TinyDB
from twitchAPI.chat import Chat, ChatMessage, EventData
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, ChatEvent, InvalidTokenException

import splash
import toml_string


class Quote:
    """Contains all the info for inserting quotes into the quote database or printing them to Twitch chat.

    :param ID: The ID for the quote, defaults to None
    :type ID: int
    :param key: The key, in format !key, defaults to ""
    :type key: str
    :param date: A date string in format MM/DD/YY, defaults to None
    :type date: str
    :param user: The user being quoted. A user ID when inserting a quote, a user display name when fetching one, defaults to None
    :type user: str
    :param category: The Twitch category active at the time of the quote, defaults to None
    :type category: str
    :param quote: The text of the quote, defaults to None
    :type quote: str
    :param quoter: The user doing the quoting. A user ID when inserting a quote, a user display name when fetching one, defaults to None
    :type quoter: str
    """

    def __init__(
        self,
        ID: int | None = None,
        key: str = "",
        date: str | None = None,
        user: str | None = None,
        category: str | None = None,
        quote: str | None = None,
        quoter: str | None = None,
    ):
        self.ID = ID
        self.key = key
        self.date = date
        self.user = user
        self.category = category
        self.quote = quote
        self.quoter = quoter

    def __str__(self):
        return f"{self.ID}, {self.key}, {self.date}, {self.user}, {self.category}, {self.quote}, {self.quoter}"

    def __iter__(self):
        yield self.ID
        yield self.key
        yield self.date
        yield self.user
        yield self.category
        yield self.quote
        yield self.quoter


class Config:
    """Contains several variables that are frequently passed from function to function.

    :param con: The connection to the quotes database, defaults to None
    :type con: sqlite3.Connection
    :param cur: The cursor for querying the quotes database, defaults to None
    :type cur: sqlite3.Connection.cursor
    :param chat: The chat instance for sending and receiving Twitch chat messages, defaults to None
    :type chat: twitchAPI.chat.Chat
    :param twitch: The Twitch API connection, defaults to None
    :type twitch: twitchAPI.twitch.Twitch
    :param TARGET_CHANNEL: The channel for the bot to connect to, defaults to None
    :type TARGET_CHANNEL: str
    :param channel_id: The user ID for TARGET_CHANNEL, defaults to None
    :type channel_id: str
    :param ignored_list: A list of user IDs for the bot to ignore. Included despite being part of tomlset because they need to be converted to IDs from display names, defaults to None
    :type ignored_list: list
    :param tomlset: Settings fetched from catBot.toml, defaults to None
    :type tomlset: dict
    :param tomlstr: Format strings fetched from catBot.toml, defaults to None
    :type tomlstr: dict
    :param bot_data: Client ID, Client Secret, and target channel fetched from cache_db, defaults to None
    :type bot_data: dict
    :param twitch_data: Token and refresh token fetched from cache_db, defaults to None
    :type twitch_data: dict
    :param cache_db: The encrypted storage for credentials.
    :type cache_db: tinydb.database.TinyDB
    :param scopes: A list of :class:`twitchAPI.type.AuthScope`s for the bot to use, defaults to None
    :type scopes: list
    """

    def __init__(
        self,
        con: sqlite3.Connection | None = None,
        cur: sqlite3.Connection.cursor | None = None,
        chat: Chat | None = None,
        twitch: Twitch | None = None,
        TARGET_CHANNEL: str | None = None,
        channel_id: str | None = None,
        ignored_list: list | None = None,
        tomlset: dict | None = None,
        tomlstr: dict | None = None,
        bot_data: dict | None = None,
        twitch_data: dict | None = None,
        cache_db: TinyDB | None = None,
        scopes: list | None = None,
    ):
        self.con = con
        self.cur = cur
        self.chat = chat
        self.twitch = twitch
        self.target = TARGET_CHANNEL
        self.id = channel_id
        self.ignored = ignored_list
        self.set = tomlset
        self.str = tomlstr
        self.bd = bot_data
        self.td = twitch_data
        self.cache = cache_db
        self.scopes = scopes


def get_last_quote(config: Config):
    """Queries the quotes database to find the maximum value in the ID column.

    :param config: A :class:`catBot.Config`
    :type config: catBot.Config
    :return: The integer value of the highest ID.
    :rtype: int
    """
    for ids in config.cur.execute("SELECT max(CAST(id AS INT)) FROM quotes"):
        quote_id = ids[0]
    return int(quote_id)


def insert_quote(quote_info: Quote, config: Config):
    """Takes the Quote object, converts it to a tuple, and inserts it into the quote database.

    :param quote_info: A :class:`catBot.Quote` object containing all the quote info.
    :type quote_info: catBot.Quote
    """
    config.cur.execute(
        """INSERT INTO quotes(id, key, date, user, category, quote, quoter) 
            VALUES (?,?,?,?,?,?,?);""",
        tuple(quote_info),
    )
    config.con.commit()


def delete_quote(index: int, config: Config):
    """Deletes the row from the quote database with the ID field matching index param.

    :param index: The ID to search for in the quotes database.
    :type index: int
    :param config: A :class:`catBot.Config`
    :type config: catBot.Config
    """
    config.cur.execute("DELETE FROM quotes WHERE id = ?", (index,))
    config.con.commit()


def update_quote(index: int, new_quote: str, config: Config):
    """Updates the quote field from the quote database with the ID field matching index param.

    :param index: The ID to search for in the quotes database.
    :type index: int
    :param new_quote: The text to replace the existing :class:`catBot.Quote.quote` with.
    :type new_quote: str
    :param config: A :class:`catBot.Config`
    :type config: catBot.Config
    """
    config.cur.execute("UPDATE quotes SET quote = ? WHERE id = ?", (new_quote, index))
    config.con.commit()


def check_key(key: str, config: Config):
    """Checks the key column in the quote database for the key param.

    :param key: A string in format "!key" to search the quote database for.
    :type key: str
    :param config: A :class:`catBot.Config`
    :type config: catBot.Config
    :return: True if the key is found, False otherwise
    :rtype: bool
    """
    check = []
    for keys in config.cur.execute("SELECT key FROM quotes WHERE key = ?", (key,)):
        check.append(keys[0])
    return check != []


def check_index(index: int, config: Config):
    """Checks the ID column in the quote database for the index param.

    :param index: The ID to search for in the database.
    :type index: int
    :param config: A :class:`catBot.Config`
    :type config: catBot.Config
    :return: True if the index is found, False otherwise
    :rtype: bool
    """
    index = int(index)
    check = []
    for indicies in config.cur.execute(
        "SELECT CAST(id AS INT) FROM quotes WHERE CAST(id AS INT) = ?", (index,)
    ):
        check.append(indicies[0])
    return check != []


def check_quoter(user_id: str, config: Config):
    """Checks the quoter column in the quote database for the user_id param.

    :param user_id: A user ID to search the quote database for. Will not accept display names.
    :type user_id: str
    :param config: A :class:`catBot.Config`
    :type config: catBot.Config
    :return: True if the key is found, False otherwise
    :rtype: bool
    """
    check = []
    for users in config.cur.execute(
        "SELECT quoter FROM quotes WHERE quoter = ?", (user_id,)
    ):
        check.append(users[0])
    return check != []


def check_quoted(user_id: str, config: Config):
    """Checks the user column in the quote database for the user_id param.

    :param user_id: A user ID to search the quote database for. Will not accept display names.
    :type user_id: str
    :param config: A :class:`catBot.Config`
    :type config: catBot.Config
    :return: True if the key is found, False otherwise
    :rtype: bool
    """
    check = []
    for users in config.cur.execute(
        "SELECT user FROM quotes WHERE user = ?", (user_id,)
    ):
        check.append(users[0])
    return check != []


async def find_quote(
    index: int | None = None,
    key: str | None = None,
    quoted: str | None = None,
    quoter: str | None = None,
    username: str | None = None,
    config: Config | None = None,
):
    """Versatile function to find rows in the quote database matching the params.
    Finds a random row if no inputs are given.
    Will send error messages to Twitch chat if inputs to params aren't found in the quotes database.
    Never takes every available param, at most taking (optionally) index, quoted/quoter, and username, otherwise taking only index or only key.
    Trying to pass other combinations of inputs may lead to unexpected behavior.

    :param index: The ID to seach the quotes database for.
    :type index: int, optional
    :param key: A string in format "!key" to search the quote database for.
    :type key: str, optional
    :param quoted: A user ID to search the user column of the quote database for. Will not accept display names. Mutually exclusive with `quoter`.
    :type user_id: str, optional
    :param quoter: A user ID to search the quoter column of the quote database for. Will not accept display names. Mutually exclusive with `quoted`.
    :type user_id: str, optional
    :param username: The display name associated with the entered `quoted` or `quoter`.
    :type username: str, optional
    :param config: A :class:`catBot.Config`
    :type config: catBot.Config

    :raises TypeError: When no `config` is passed.

    :return: A :class:`catBot.Quote` object containing the fetched info from the quotes database.
    :rtype: catBot.Quote
    """
    if config == None:
        raise TypeError("Required config argument not passed.")
    for data in config.cur.execute("SELECT count(*) FROM quotes"):
        db_count = data[0]
    if db_count == 0:
        await config.chat.send_message(config.target, config.str.get("empty_db"))
        return
    if quoted != None:
        if check_quoted(quoted, config):
            results = []
            for data in config.cur.execute(
                "SELECT * FROM quotes WHERE user = ?", (quoted,)
            ):
                results.append(data)
            if index == None:
                results = choice(results)
            elif abs(index) > len(results):
                await config.chat.send_message(
                    config.target, f"Not enough quotes found for index {index}!"
                )
                return
            else:
                results = results[index]
        else:
            await config.chat.send_message(
                config.target, config.str.get("invalid_quoted").format(user=username)
            )
            return
    elif quoter != None:
        if check_quoter(quoter, config):
            results = []
            for data in config.cur.execute(
                "SELECT * FROM quotes WHERE quoter = ?", (quoter,)
            ):
                results.append(data)
            if index == None:
                results = choice(results)
            elif abs(index) > len(results):
                await config.chat.send_message(
                    config.target, f"Not enough quotes found for index {index}!"
                )
                return
            else:
                results = results[index]
        else:
            await config.chat.send_message(
                config.target, config.str.get("invalid_quoter").format(user=username)
            )
            return
    elif key != None:
        if check_key(key, config):
            for data in config.cur.execute(
                "SELECT * FROM quotes WHERE key = ?", (key,)
            ):
                results = data
        else:
            await config.chat.send_message(
                config.target, config.str.get("invalid_key").format(key=key)
            )
            return
    elif index != None:
        if check_index(index, config):
            for data in config.cur.execute(
                "SELECT * FROM quotes WHERE CAST(id AS INT) = ?", (index,)
            ):
                results = data
        else:
            await config.chat.send_message(
                config.target, config.str.get("invalid_ID").format(ID=index)
            )
    else:
        quote_ids = []
        for ids in config.cur.execute(
            "SELECT CAST(id AS INT) FROM quotes ORDER BY CAST(id AS INT)"
        ):
            quote_ids.append(ids[0])
        quote_id = choice(quote_ids)
        for data in config.cur.execute(
            "SELECT * FROM quotes WHERE CAST(id AS INT) = ?", (quote_id,)
        ):
            results = data

    # Setting all the variables to be passed into post_quote().
    # User and quoter were fetched as user IDs, so need to be converted to display names.
    quote_info = Quote(
        ID=results[0],
        key=results[1],
        date=results[2],
        user=(await anext(config.twitch.get_users(str(results[3])))).display_name,
        category=results[4],
        quote=results[5],
        quoter=(await anext(config.twitch.get_users(str(results[6])))).display_name,
    )

    return quote_info


async def post_quote(quote_info: Quote, config: Config):
    """Posts a Twitch chat message with the information from `quote_info`.

    :param quote_info: A :class:`catBot.Quote` object containing all the quote info.
    :type quote_info: catBot.Quote
    :param config: A :class:`catBot.Config`
    :type config: catBot.Config
    """
    if quote_info.key != "":
        await config.chat.send_message(config.target, quote_info.quote)
        await config.chat.send_message(
            config.target,
            config.str.get("keyed").format(
                ID=quote_info.ID,
                key=quote_info.key,
                date=quote_info.date,
                user=quote_info.user,
                category=quote_info.category,
                quoter=quote_info.quoter,
            ),
        )
    else:
        await config.chat.send_message(config.target, quote_info.quote)
        await config.chat.send_message(
            config.target,
            config.str.get("unkeyed").format(
                ID=quote_info.ID,
                date=quote_info.date,
                user=quote_info.user,
                category=quote_info.category,
                quoter=quote_info.quoter,
            ),
        )


def is_auth(msg: ChatMessage, config: Config):
    """Checks if the input :class:`twitchAPI.chat.ChatMessage` is authorized to save manual quotes of the streamer based on the setting in catBot.toml.

    :param msg: The Twitch chat message to be checked for authorization.
    :type msg: twitchAPI.chat.ChatMessage
    :param config: A :class:`catBot.Config`
    :type config: catBot.Config
    :return: True if the user is authorized, False otherwise.
    :rtype: bool
    """
    return (
        config.set.get("vip_only")
        and not (msg.user.vip or msg.user.mod or msg.user.id == config.id)
        or config.set.get("subs_only")
        and not (
            msg.user.vip
            or msg.user.mod
            or msg.user.subscriber
            or msg.user.id == config.id
        )
    )


def is_super_auth(msg: ChatMessage, config: Config):
    """Checks if the input :class:`twitchAPI.chat.ChatMessage` is authorized to save any type of quote based on the setting in catBot.toml.

    :param msg: The Twitch chat message to be checked for authorization.
    :type msg: twitchAPI.chat.ChatMessage
    :param config: A :class:`catBot.Config`
    :type config: catBot.Config
    :return: True if the user is authorized, False otherwise.
    :rtype: bool
    """
    return (
        config.set.get("super_vip_only")
        and not (msg.user.vip or msg.user.mod or msg.user.id == config.id)
        or config.set.get("super_subs_only")
        and not (
            msg.user.vip
            or msg.user.mod
            or msg.user.subscriber
            or msg.user.id == config.id
        )
    )


async def message_handler(msg: ChatMessage, config: Config):
    """Function is called when twitchAPI.chat.Chat.register_event(twitchAPI.type.ChatEvent(MESSAGE)) is triggered, i.e. when any message is sent in TARGET_CHANNEL.
    Checks messages for the !quote command, then uses regex to parse what the user intended to do. See `Usage` in the README to see what patterns are matched

    :param msg: The Twitch chat message to be checked for authorization.
    :type msg: twitchAPI.chat.ChatMessage
    :param config: A :class:`catBot.Config`
    :type config: catBot.Config
    :return: True if the user is authorized, False otherwise.
    :rtype: bool
    """
    if msg.user.id in config.ignored:
        return
    if (
        re.search(r"!quote", msg.text) != None
    ):  # checks the message for "!quote" so it can more efficiently ignore messages
        if msg.reply_parent_msg_body != None:  # checks if message is a reply
            if not is_super_auth(msg, config):
                return
            command = re.search(
                r"^@[A-Za-z_0-9]* !quote( |)(?P<key>!.*$|$)", msg.text
            )  # checks message and matches an optional key for the quote
            if command != None:
                quote_info = Quote(
                    ID=get_last_quote(config) + 1,
                    key=command.group(2),
                    date=datetime.now().strftime("%m/%d/%y"),
                    user=msg.reply_parent_user_id,
                    category=re.search(
                        r"game_name=(?P<name>.*?),",
                        str(
                            list(
                                await config.twitch.get_channel_information(config.id)
                            )[0]
                        ),
                    ).group("name"),
                    quote=msg.reply_parent_msg_body.replace("\\s", " "),
                    quoter=msg.user.id,
                )
                if re.search(r"^!quote", quote_info.quote):
                    await config.chat.send_message(
                        config.target, 'Cannot save quotes beginning with "!quote"'
                    )
                    return
                insert_quote(quote_info, config)
                quote_info = await find_quote(
                    index=get_last_quote(config), config=config
                )
                if config.set.get("repeat_quote_on_save"):
                    await post_quote(quote_info, config)
                else:
                    await config.chat.send_message(
                        config.target,
                        config.str.get("save_success_unkeyed").format(
                            ID=quote_info.ID,
                            user=quote_info.user,
                            date=quote_info.date,
                            category=quote_info.category,
                            quoter=quote_info.quoter,
                        ),
                    )

        elif (
            re.search(r"^!quote (?P<number>\d*$)", msg.text) != None
        ):  # matches !quote followed by a number
            command = re.search(r"^!quote (?P<number>\d*$)", msg.text)
            if command != None and check_index(command.group(1), config):
                await post_quote(
                    await find_quote(
                        index=int(command.group(1), config=config), config=config
                    )
                )
            else:
                ID = command.group(1)
                await config.chat.send_message(
                    config.target, config.set.get("invalid_ID").format(ID=ID)
                )

        elif re.search(
            r"^!quote (?P<key>![^ ]*$)", msg.text
        ):  # matches !quote followed by a key
            command = re.search(r"^!quote (?P<key>![^ ]*$)", msg.text)
            if command != None:
                await post_quote(
                    find_quote(key=command.group(1), config=config), config=config
                )

        elif re.search(
            r'(?P<command>^!quote) *(?P<key>![^ ]*|) *(?P<user>@[A-Za-z_0-9]*|) *"(?P<quote>.*)"$',  # matches !quote followed by an optional key, an optional @user, and a manually entered "quote"
            msg.text,
        ):
            if not is_super_auth(msg, config):
                return
            command = re.search(
                r'(?P<command>^!quote) *(?P<key>![^ ]*|) *(?P<user>@[A-Za-z_0-9]*|) *"(?P<quote>.*)"$',
                msg.text,
            )
            if command.group(4) == "":
                return
            if (
                command.group(2) == "" and command.group(3) == ""
            ):  # case with no key and no @user
                if not is_auth(msg, config):
                    return
                if msg.source_room_id == None:
                    user = config.id
                else:
                    user = msg.source_room_id
                quote_info = Quote(
                    ID=get_last_quote(config) + 1,
                    key=command.group(2),
                    date=datetime.now().strftime("%m/%d/%y"),
                    user=user,
                    category=re.search(
                        r"game_name=(?P<name>.*?),",
                        str(
                            list(
                                await config.twitch.get_channel_information(config.id)
                            )[0]
                        ),
                    ).group("name"),
                    quote=command.group(4),
                    quoter=msg.user.id,
                )
                if re.search(r"^!quote", quote_info.quote):
                    await config.chat.send_message(
                        config.target, 'Cannot save quotes beginning with "!quote"'
                    )
                    return
                insert_quote(quote_info, config)
                quote_info = await find_quote(
                    index=get_last_quote(config), config=config
                )
                if config.set.get("repeat_quote_on_save"):
                    await post_quote(quote_info, config)
                else:
                    await config.chat.send_message(
                        config.target,
                        config.str.get("save_success_unkeyed").format(
                            user=quote_info.user,
                            date=quote_info.date,
                            category=quote_info.category,
                            ID=quote_info.ID,
                            quoter=quote_info.quoter,
                        ),
                    )

            elif (
                command.group(2) != "" and command.group(3) == ""
            ):  # case with key and no @user
                if not is_auth(msg, config):
                    return
                if check_key(command.group(2), config):
                    key = command.group(2)
                    await config.chat.send_message(
                        config.target, config.str.get("key_exists").format(key=key)
                    )
                else:
                    if msg.source_room_id == None:
                        user = config.id
                    else:
                        user = msg.source_room_id
                    quote_info = Quote(
                        ID=get_last_quote(config) + 1,
                        key=command.group(2),
                        date=datetime.now().strftime("%m/%d/%y"),
                        user=user,
                        category=re.search(
                            r"game_name=(?P<name>.*?),",
                            str(
                                list(
                                    await config.twitch.get_channel_information(
                                        config.id
                                    )
                                )[0]
                            ),
                        ).group("name"),
                        quote=command.group(4),
                        quoter=msg.user.id,
                    )
                    if re.search(r"^!quote", quote_info.quote):
                        await config.chat.send_message(
                            config.target, 'Cannot save quotes beginning with "!quote"'
                        )
                        return
                    insert_quote(quote_info, config)
                    quote_info = await find_quote(
                        index=get_last_quote(config), config=config
                    )
                    if config.set.get("repeat_quote_on_save"):
                        await post_quote(quote_info, config)
                    else:
                        await config.chat.send_message(
                            config.target,
                            config.str.get("save_success_keyed").format(
                                ID=quote_info.ID,
                                key=quote_info.key,
                                user=quote_info.user,
                                date=quote_info.date,
                                quoter=quote_info.quoter,
                            ),
                        )

            elif (
                command.group(2) == "" and command.group(3) != ""
            ):  # case with no key and found @user
                if not is_auth(msg, config):
                    return
                user = command.group(3).replace("@", "")
                user = (await anext(config.twitch.get_users(None, user))).id
                quote_info = Quote(
                    ID=get_last_quote(config) + 1,
                    key=command.group(2),
                    date=datetime.now().strftime("%m/%d/%y"),
                    user=user,
                    category=re.search(
                        r"game_name=(?P<name>.*?),",
                        str(
                            list(
                                await config.twitch.get_channel_information(config.id)
                            )[0]
                        ),
                    ).group("name"),
                    quote=command.group(4),
                    quoter=msg.user.id,
                )

                if re.search(r"^!quote", quote_info.quote):
                    await config.chat.send_message(
                        config.target, 'Cannot save quotes beginning with "!quote"'
                    )
                    return
                insert_quote(quote_info, config)
                quote_info = await find_quote(
                    index=get_last_quote(config), config=config
                )
                if config.set.get("repeat_quote_on_save"):
                    await post_quote(quote_info, config)
                else:
                    await config.chat.send_message(
                        config.target,
                        config.str.get("save_success_unkeyed").format(
                            ID=quote_info.ID,
                            date=quote_info.date,
                            user=quote_info.user,
                            category=quote_info.category,
                            quoter=quote_info.quoter,
                        ),
                    )

            elif (
                command.group(2) != "" and command.group(3) != ""
            ):  # case with found key and found @user
                if check_key(command.group(2), config):
                    key = command.group(2)
                    await config.chat.send_message(
                        config.target,
                        config.str.get("key_exists").format(
                            key=key,
                        ),
                    )
                else:
                    user = command.group(3).replace("@", "")
                    user = (await anext(config.twitch.get_users(None, user))).id
                    quote_info = Quote(
                        ID=get_last_quote() + 1,
                        key=command.group(2),
                        date=datetime.now().strftime("%m/%d/%y"),
                        user=user,
                        category=re.search(
                            r"game_name=(?P<name>.*?),",
                            str(
                                list(
                                    await config.twitch.get_channel_information(
                                        config.id
                                    )
                                )[0]
                            ),
                        ).group("name"),
                        quote=command.group(4),
                        quoter=msg.user.id,
                    )
                    if re.search(r"^!quote", quote_info.quote):
                        await config.chat.send_message(
                            config.target, 'Cannot save quotes beginning with "!quote"'
                        )
                        return
                    insert_quote(quote_info, config)
                    quote_info = await find_quote(
                        index=get_last_quote(config), config=config
                    )
                    if config.str.get("repeat_quote_on_save"):
                        await post_quote(quote_info, config)
                    else:
                        await config.chat.send_message(
                            config.target,
                            config.str.get("save_success_keyed").format(
                                ID=quote_info.ID,
                                key=quote_info.key,
                                date=quote_info.date,
                                user=quote_info.user,
                                category=quote_info.category,
                                quoter=quote_info.quoter,
                            ),
                        )

        elif re.search(r"^!quote$", msg.text):
            await post_quote(await find_quote(config=config), config)

        elif re.search(
            r"^!quote -\d$", msg.text
        ):  # matches !quote followed by a negative index
            quote_ids = []
            for ids in config.cur.execute(
                "SELECT CAST(id AS INT) FROM quotes ORDER BY CAST(id AS INT)"
            ):
                quote_ids.append(ids[0])
            if int(re.search(r"-(\d)", msg.text).group(1)) > len(quote_ids):
                await config.chat.send_message(
                    config.target, "Requested negative index is too large!"
                )
            else:
                quote_id = quote_ids[int(re.search(r"(-\d)", msg.text).group(1))]
                await post_quote(
                    await find_quote(index=quote_id, config=config), config
                )

        elif re.search(r"^!quote delete \d$", msg.text):
            if not msg.user.mod and msg.user.id != config.id:
                return
            delete_quote(int(re.search(r"^!quote delete (\d$)", msg.text).group(1)))
            ID = re.search(r"^!quote delete (\d$)", msg.text).group(1)
            await config.chat.send_message(
                config.target, config.str.get("delete_success").format(ID=ID)
            )

        elif re.search(r'^!quote update (\d) "(.*)"', msg.text):
            command = re.search(r'^!quote update (\d) "(.*)"', msg.text)
            if not msg.user.mod and msg.user.id != config.id:
                return
            if check_index(int(command.group(1)), config):
                update_quote(int(command.group(1)), command.group(2), config)
                ID = command.group(1)
                await config.chat.send_message(
                    config.target, config.str.get("update_success").format(ID=ID)
                )
            else:
                await config.chat.send_message(
                    config.target, config.str.get("invalid_ID").format(ID=ID)
                )

        elif re.search(r"^!quote help$", msg.text):
            await config.chat.send_message(
                config.target,
                "Find out how to use !quote at https://github.com/queenside-rook/catBot/blob/main/README.md",
            )

        elif re.search(r"^!quoted", msg.text):
            command = re.search(
                r"^!quoted *(@|)(?P<user>[A-Za-z_0-9]*|) *(-|)(\d*)", msg.text
            )
            user_id = (
                await anext(config.twitch.get_users(logins=command.group("user")))
            ).id
            try:
                index = int(command.group(3) + command.group(4))
            except ValueError:
                index = None
            if check_quoted(user_id, config):
                await post_quote(
                    await find_quote(
                        index=index,
                        quoted=user_id,
                        username=command.group("user"),
                        config=config,
                    ),
                    config,
                )

        elif re.search(r"^!quoter", msg.text):
            command = re.search(
                r"^!quoter *(@|)(?P<user>[A-Za-z_0-9]*|) *(-|)(\d*)", msg.text
            )
            user_id = (
                await anext(config.twitch.get_users(logins=command.group("user")))
            ).id
            try:
                index = int(command.group(3) + command.group(4))
            except ValueError:
                index = None
            if check_quoter(user_id, config):
                await post_quote(
                    await find_quote(
                        index=index,
                        quoter=user_id,
                        username=command.group("user"),
                        config=config,
                    ),
                    config,
                )


def already_running():
    """Called when running.temp is found to stop the user from running multiple instances of catBot.

    :return: An error window popup.
    :rtype: ctypes.windll.user32.MessageBoxW
    """

    atexit.unregister(exit_script)
    return ctypes.windll.user32.MessageBoxW(
        0,
        "Error",
        "Bot already running! If you believe this is in error, delete running.temp",
        0,
    )


async def stop_loop(config: Config):
    """Waits for the user to input "stop" to close the :class:`twitchAPI.chat.Chat` instance and :class:`twitchAPI.twitch.Twitch` instance.

    :param config: A :class:`catBot.Config`
    :type config: Config
    """
    splash.print_splash()
    print(
        f"\nBot is running on channel {config.target}. Type STOP to stop the quote bot.\n"
    )
    option = input().lower()
    if option == "stop":
        config.chat.stop()
        await config.twitch.close()
        exit_script()
        await user_input()
    else:
        print("\n\033[93mInvalid input. Press ENTER to continue.\033[0m\n")
        input()
        await stop_loop()


async def start_bot(config: Config):
    """Starts the bot, finishes filling out missing Config fields, authenticates the bot, registers :class:`twitchAPI.type.ChatEvent`s,
    defines the functions to handle those events, opens the :class:`twitchAPI.chat.Chat` instance and :class:`twitchAPI.twitch.Twitch` instance, then calls `catBot.stop_loop`.

    :param config: A :class:`catBot.Config`
    :type config: Config
    """
    APP_ID, APP_SECRET, config.target = (
        config.bd.get("APP_ID"),
        config.bd.get("APP_SECRET"),
        config.bd.get("TARGET_CHANNEL"),
    )
    config.twitch = await Twitch(APP_ID, APP_SECRET)
    auth = UserAuthenticator(config.twitch, config.scopes)

    if config.td.get("refresh_token") != "":
        token, refresh_token = (
            config.td.get("token"),
            config.td.get("refresh_token"),
        )
    else:
        token, refresh_token = await auth.authenticate()
        config.cache.update(
            {"Twitch Tokens": {"token": token, "refresh_token": refresh_token}}
        )

    try:
        await config.twitch.set_user_authentication(token, config.scopes, refresh_token)
    except InvalidTokenException:
        token, refresh_token = await auth.authenticate()
        config.cache.update(
            {"Twitch Tokens": {"token": token, "refresh_token": refresh_token}}
        )
        try:
            await config.twitch.set_user_authentication(
                token, config.scopes, refresh_token
            )
        except InvalidTokenException:
            print("Unrecoverable error.")
    config.chat = await Chat(
        config.twitch, no_shared_chat_messages=config.set.get("ignore_shared_chat")
    )
    channel_data = config.twitch.get_users(logins=config.target)
    async for data in channel_data:
        channel_id = data
    config.id = channel_id.id

    # global ignored_list
    ignored = config.twitch.get_users(logins=config.ignored)
    bot_id = (
        await anext(config.twitch.get_users())
    ).id  # with no argument, this function fetches the ID of the twitch account that's currently authenticated
    config.ignored = []
    async for data in ignored:
        ignored = data.id
        config.ignored.append(ignored)
    if not config.set.get("using_bot"):
        try:
            config.ignored.remove(bot_id)
        except ValueError:
            pass

    async def on_ready(ready_event: EventData):
        await ready_event.chat.join_room(config.target)

    async def on_message(msg: ChatMessage):
        await message_handler(msg, config)

    config.chat.register_event(ChatEvent.READY, on_ready)
    config.chat.register_event(ChatEvent.MESSAGE, on_message)
    config.chat.start()

    await stop_loop(config)


async def initialize_cache():
    """Initializes the encrypted credential cache, then passes it to `catBot.startup_checks`."""
    splash.print_splash()
    KEY = input("Desired password: ")
    PATH = "cache.encrypted_db"
    cache_db = TinyDB(encryption_key=KEY, path=PATH, storage=tae.EncryptedJSONStorage)
    APP_ID = input("Input Twitch App Client ID: ")
    APP_SECRET = input("Input Twitch App Client Secret: ")
    TARGET_CHANNEL = input("Channel for bot to operate in: ")
    cache_db.insert(
        {
            "Bot Info": {
                "APP_ID": APP_ID.replace("\n", ""),
                "APP_SECRET": APP_SECRET.replace("\n", ""),
                "TARGET_CHANNEL": TARGET_CHANNEL.replace("\n", ""),
            }
        }
    )
    cache_db.insert({"Twitch Tokens": {"token": "", "refresh_token": ""}})
    exit_script()
    await startup_checks(cache_db)


def get_cache():
    """_summary_

    :return: Returns the info from the encrypted `cache.encrypted_db`
    :rtype: tinydb.database.TinyDB
    """
    splash.print_splash()
    KEY = input("\nPassword: ")
    if KEY == "":
        cache_db = False
    try:
        cache_db = TinyDB(
            encryption_key=KEY,
            path="cache.encrypted_db",
            storage=tae.EncryptedJSONStorage,
        )
    except ValueError:
        print("Invalid password!")
        get_cache()
    return cache_db


async def user_input():
    """Checks if the encrypted credentials exist, calls `catBot.initialize_cache` if they don't, then waits for the user to select an option. START starts the quote bot, EXIT stops the program,
    CHANGEPASS lets the user change their password for their encrypted credentials, CHANGEBOT lets the user change their Client ID and Client Secret or the channel for the bot to operate in.
    """
    if path.isfile("cache.encrypted_db"):
        cache_db = get_cache()
    else:
        initialize_cache()
    splash.print_splash()
    print(
        "\nType START to start the quote bot. If this is your first time running the program, start here."
    )
    print("Type EXIT to exit.")
    print("Type CHANGEPASS to change your password.")
    print(
        "Type CHANGEBOT to change your Client ID and Client Secret or your Target Channel.\n"
    )
    option = input().lower()
    if option == "start":
        splash.print_splash()
        await startup_checks(cache_db)
    elif option == "exit":
        return
    elif option == "changepass":
        splash.print_splash()
        try:
            password = input("\nEnter current password: ")
            cache_db = TinyDB(
                encryption_key=password,
                path="cache.encrypted_db",
                storage=tae.EncryptedJSONStorage,
            )
            cache_db.all()
            new_pass = input("\nEnter new password: ")
            cache_db.storage.change_encryption_key(new_pass)
            print("\n\033[92mNew password saved. Press ENTER to continue.\033[0m\n")
            input()
            await user_input()
        except ValueError:
            print(
                "\n\033[93mIncorrect original password. Press ENTER to return.\033[0m\n"
            )
            input()
            await user_input()
    elif option == "changebot":
        splash.print_splash()
        try:
            password = input("\nEnter password: ")
            cache_db = TinyDB(
                encryption_key=password,
                path="cache.encrypted_db",
                storage=tae.EncryptedJSONStorage,
            )
            cache_db.all()
            option = input(
                "\nEnter APP to change Twitch App information. Enter CHANNEL to change target channel.\n\n"
            ).lower()
            if option == "app":
                APP_ID = input("Input Twitch App Client ID: ")
                APP_SECRET = input("Input Twitch App Client Secret: ")
                cache_db.update(
                    {
                        "Bot Info": {
                            "APP_ID": APP_ID.replace("\n", ""),
                            "APP_SECRET": APP_SECRET.replace("\n", ""),
                            "TARGET_CHANNEL": cache_db.get(doc_id=1)
                            .get("Bot Info")
                            .get("TARGET_CHANNEL"),
                        }
                    },
                    doc_ids=[1],
                )
                print("\n\033[92mUpdate successful. Press ENTER to continue.\033[0m")
                input()
                await user_input()
            elif option == "channel":
                TARGET_CHANNEL = input("Channel for bot to operate in: ")
                get_cache().update(
                    {
                        "Bot Info": {
                            "APP_ID": cache_db.get(doc_id=1)
                            .get("Bot Info")
                            .get("APP_ID"),
                            "APP_SECRET": cache_db.get(doc_id=1)
                            .get("Bot Info")
                            .get("APP_SECRET"),
                            "TARGET_CHANNEL": TARGET_CHANNEL,
                        }
                    },
                    doc_ids=[1],
                )
                print("\n\033[92mUpdate successful. Press ENTER to continue.\033[0m")
                input()
                await user_input()
        except ValueError:
            print(
                "\n\033[93mIncorrect original password. Press ENTER to return.\033[0m\n"
            )
            input()
            await user_input()
    else:
        print("\n\033[93mInvalid input. Press ENTER to continue.\033[0m")
        input()
        await user_input()


async def startup_checks(cache_db: TinyDB):
    """Checks if the bot is already running, loads info from `catBot.toml`, connects to the quotes database, then starts the bot.
    Begins constructing the :class:`catBot.Quote` for use in the rest of the program.

    :param cache_db: The user's encrypted credentials.
    :type cache_db: tinydb.database.TinyDB
    """
    program_running = path.isfile("running.temp")
    if not program_running:
        with open("running.temp", "w"):
            pass
        atexit.register(exit_script)
        try:
            with open("catBot.toml", "rb") as f:
                toml = tomllib.load(f)
                tomlstr = toml.get("format_strings")
                tomlset = toml.get("settings")
        except FileNotFoundError:
            print(
                "\033[91mcatBot.toml missing! A new one will be generated for you.\033[0m"
            )
            with open("catBot.toml", mode="w") as fp:
                fp.write(toml_string.toml_string)
        con = (sqlite3.connect("quotes.db", check_same_thread=False),)
        cur = con.cur
        config = Config(
            con=con,
            cur=cur,
            ignored_list=tomlset.get("ignore"),
            tomlset=tomlset,
            tomlstr=tomlstr,
            bot_data=cache_db.get(doc_id=1).get("Bot Info"),
            twitch_data=cache_db.get(doc_id=2).get("Twitch Tokens"),
            cache_db=cache_db,
            scopes=[
                AuthScope.CHAT_READ,
                AuthScope.CHAT_EDIT,
                AuthScope.USER_BOT,
                AuthScope.CHANNEL_BOT,
            ],
        )
        await start_bot(config)

    else:
        already_running()


def exit_script():
    """Attempts to delete `running.temp` when the bot stops."""
    try:
        remove("running.temp")
    except FileNotFoundError:
        return


def main():
    print(splash.title)
    input()
    asyncio.run(user_input())


if __name__ == "__main__":
    main()
