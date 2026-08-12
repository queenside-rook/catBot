# catBot
A small, simple Twitch chat bot to save and retrieve quotes.

## Usage

`!quote` by itself will return a random quote from your database

`!quote` by itself as a reply to a message will quote that message

`!quote !key` as a reply to a message will quote that message with the given key

`!quote "text"` will create a quote attributed to the streamer whose channel it was entered in (including during shared chat)

`!quote !key "text"` will do as above but with the given key

`!quote ID` will return quote with entered ID

`!quote !key` will return quote with entered key

`!quote -n` will return the (n-1)th quote from most recent, so `!quote -1` returns the most recent quote, `!quote -2` the one before that, etc

## Setup

Go to https://dev.twitch.tv/console

Click "Register Your Application"

Name it whatever you want

In OAuth Redirect URLs, put "http://localhost:17563" without the quotes

Select Category Chat Bot

Leave it as Confidential

Click "Create"

Return to https://dev.twitch.tv/console

Click "Manage" next to your new app

Copy down your Client ID

Click "New Secret"

Copy down your Client Secret

Run catBot.exe

If you want to run this from a bot account, log in to that bot account in your default browser now.

Type "start", program will direct you from there

## Debugging

To enable debug mode, run catBot.exe with command --debug. To log the debug, open a CLI in catBot.exe's folder and enter `./catBot.exe --debug | tee debug.txt`
