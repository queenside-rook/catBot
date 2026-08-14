toml_string = """[format_strings]
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
invalid_quoted = "No quotes from {user} found!" # only takes the variable {user}
invalid_quoter = "No quotes quoted by {user} found!" # only takes the variable {user}

[settings]
ignore = [] # list all users (such as your bots) you want to be ignored by catBot
using_bot = true # set to false if you're using your broadcaster account as the bot
vip_only = true # set to true if you only want VIPs and mods to be able to quote streamers directly with !quote "text"
super_vip_only = false # set to true if you only want VIPs and mods to be able to use !quote to quote anyone at all
subs_only = false # as above but for subs, VIPs, and mods
super_subs_only = false # as above but for subs, VIPs, and mods
ignore_shared_chat = false
repeat_quote_on_save = false # set to true to send the quoted message as if you had used !quote <ID#> instead of just sending the save_success_(un)keyed message"""
