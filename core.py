#!/usr/bin/env python

import configparser
import discord
import sys
import os
import time
import threading
import secrets
import hashlib
import asyncio
import aiohttp
from aiohttp import web
import ujson
import collections

configFileName = "cabeiri.config.ini"
webhookFileName = "cabeiri.webhooks.pdb"
running = True

# Helper Functions
def writeBackConfig():
    config["server"]["fqhost"] = "http://{0}:{1}/".format(config.get("server","host"), config.get("server", "port"))
    with open(configFileName, 'w') as configFile:
        config.write(configFile)

def writeBackWebhooks():
    with open(webhookFileName, 'w') as webhookFile:
        for webhook in webhooks:
            webhookFile.write("{0}\t{1}\t{2}\n".format(webhook, webhooks[webhook][0], webhooks[webhook][1]))
        webhookFile.close()

def createWebhook(author, webhook):
    return hashlib.md5(bytes(str(author) + webhook, "utf-8")).hexdigest()

def startServer(runner):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, config.get("server","host"), config.get("server", "port"))
    loop.run_until_complete(site.start())
    loop.run_forever()


# Asynchronous Functions
async def cleanUp():
    while running:
        timedOut = []
        currentTime = time.monotonic()
        for registrant in registrants:
            if (currentTime - registrants[registrant]) > 300:
                timedOut.append(registrant)
        for registrant in timedOut:
            try:
                del registrants[registrant]
            except:
                pass
            finally:
                pass
        for initiation in initiations:
            if (currentTime - initiations[initiation]) > 10800:
                timedOut.append(initiation)
        for initiation in timedOut:
            try:
                del initiations[initiation]
            except:
                pass
            finally:
                pass
        while len(completions) > 0:
            id, payload = completions.popleft()
            if config.get("discord", "channel", fallback="") != "":
                await client.get_channel(int(config.get("discord","channel"))).send("Chain completed for <@{0}> with payload: `{1}`".format(id, payload))
            else:
                await client.get_user(int(id)).send("Chain completed with payload: `{0}`".format(payload))
        await asyncio.sleep(1)

async def fireWebhook(id, token):
    initiations[id] = time.monotonic()
    webhookURI = webhooks[id][0]
    b = {"id" : id, "payload" : token}
    async with aiohttp.ClientSession(json_serialize=ujson.dumps) as session:
        try:
            async with session.post(webhookURI, json=b) as response:
                return response.status
        except:
            return -1
        finally:
            pass

async def webhookHandler(request):
    identifier = request.match_info["encode"]
    try:
        json = await request.json(loads=ujson.loads)
        if json["id"] in initiations:
            del initiations[json["id"]]
            _, incoming = webhooks[json["id"]]
            if incoming == identifier:
                completions.append((json["id"],json["payload"]))
            else:
                raise web.HTTPForbidden
        else:
            if json["id"] in webhooks:
                raise web.HTTPRequestTimeout
            else:
                raise web.HTTPUnauthorized
    except:
        raise web.HTTPBadRequest
    raise web.HTTPOk




# Data Structures
webhooks = {}
registrants = {}
initiations = {}
completions = collections.deque()


# Load config.ini
config = configparser.ConfigParser()
if os.path.isfile(configFileName):
    config.read(configFileName)
else:
    print("No config found")
    config["discord"] = {"token":"", "owner":""}
    config["server"] = {"host":"localhost", "port":6280}
    writeBackConfig()

# Configure from command line if needed
if len(sys.argv) > 1:
    token = False
    owner = False
    host = False
    port = False
    for arg in sys.argv[1:]:
        if arg == "-T":
            token = True
        elif arg == "-O":
            owner = True
        elif arg == "-H":
            host = True
        elif arg == "-P":
            port = True
        elif token:
            config["discord"]["token"] = arg
            token = False
            print("Token set")
        elif owner:
            config["discord"]["owner"] = arg
            owner = False
            print("Owner set")
        elif host:
            config["server"]["host"] = arg
            host = False
            print("Host set")
        elif port:
            config["server"]["port"] = arg
            host = False
            print("Port set")
        else:
            print ("Bad arguments, ending")
            exit(1)
        writeBackConfig()


# Load from pseudodatabase
if os.path.isfile(webhookFileName):
    with open(webhookFileName, "r") as webhookFile:
        entries = webhookFile.readlines()
        for entry in entries:
            (userid, outgoing, incoming) = entry.split()
            webhooks[int(userid)] = (outgoing, incoming)
        webhookFile.close()



# Set up client
if config.get("discord", "token") == "":
    print("No token specified\nExiting...")
    exit(1)
client = discord.Client()

# Set up webhook server
app = web.Application()
app.add_routes([web.post('/cabeiri/{encode}', webhookHandler)])
runner = web.AppRunner(app)


# Print when ready
@client.event
async def on_ready():
    print('Online as {0.user}'.format(client))


# Active Reactions
@client.event
async def on_message(message):
    # Handle DMs
    if message.channel.type == discord.ChannelType.private:
        if message.author.id in registrants:
            webhooks[message.author.id] = (message.content, createWebhook(message.author.id, message.content))
            await message.author.send("Incoming URL: `{0}cabeiri/{1}`".format(config.get("server","fqhost"),webhooks[message.author.id][1]))
            writeBackWebhooks()
        elif message.author != client.user:
            await message.author.send("No active registration exists, you were potentially timed out.")
            if config.get("discord", "channel", fallback="") != "":
                await message.author.send("Registration can be done in <#{0}>.".format(config.get("discord", "channel")))


    # Localize listening to a given channel
    if message.content.lower().startswith("|localize"):
        if int(config.get("discord", "owner")) == message.author.id:
            config["discord"]["channel"] = str(message.channel.id)
            writeBackConfig()
            await message.channel.send("Activity localized to <#{0}>.".format(config.get("discord", "channel")))
        else:
            await message.channel.send("Activity can only be localized by the owner.")

    # Ignore non-localized channels
    if config.get("discord", "channel", fallback="") != "" and message.channel.id != int(config.get("discord", "channel")):
        return

    # Allow the bot to be claimed from discord
    if message.content.lower() == "|claim":
        if config.get("discord","owner") == "":
            config["discord"]["owner"] = str(message.author.id)
            writeBackConfig()
            await message.channel.send("Ownership claimed.")
        else:
            await message.channel.send("Ownership already claimed.")

    # Transfer ownership to another user
    if message.content.lower().startswith("|transfer"):
        if int(config.get("discord", "owner")) == message.author.id:
            config["discord"]["owner"] = message.content.split()[1]
            writeBackConfig()
            await message.channel.send("Ownership transfered to <@{0}>.".format(config.get("discord", "owner")))
        else:
            await message.channel.send("Ownership can only be transfered by the owner.")

    # Register a new webhook pair
    if message.content.lower() == "|register":
        if message.author.id in webhooks:
            await message.channel.send("Reregistering, details sent directly.")
        else:
            await message.channel.send("Registering, details sent directly.")
        registrants[message.author.id] = time.monotonic()
        try:
            await message.author.send("Please provide the outgoing webhook to register for you:")
        except discord.errors.Forbidden:
            await message.channel.send("Direct messaging forbidden, please adjust and try again.")
        finally:
            pass

    # Check an existing new webhook pair
    if message.content.lower() == "|status":
        if message.author.id in webhooks:
            await message.channel.send("Registered, details sent directly.")
            try:
                await message.author.send("Outgoing URL: `{0}`".format(webhooks[message.author.id][0]))
                await message.author.send("Incoming URL: `{0}cabeiri/{1}`".format(config.get("server","fqhost"),webhooks[message.author.id][1]))
            except discord.errors.Forbidden:
                await message.channel.send("Direct messaging forbidden, please adjust and try again.")
            finally:
                pass
        else:
            await message.channel.send("Unregistered.")

    # Fire a webhook chain
    if message.content.lower() == "|initiate":
        if message.author.id in webhooks:
            token = secrets.token_hex(8)
            await message.channel.send("Initiating chain with payload: `{0}`".format(token))
            statusCode = await fireWebhook(message.author.id, token)
            if statusCode == -1:
                await message.author.send("An error occured and the request could not be sent.")
            elif statusCode != 200:
                await message.author.send("HTTP request failed with code: `{0}`".format(statusCode))
        else:
            await message.channel.send("Unregistered.")


    # Ping test
    if message.content.lower() == "|ping":
        await message.channel.send("> Online and Active")



# Start web server
webThreadRunner = threading.Thread(target=startServer, args=(runner,))
webThreadRunner.start()

# Start discord bot
client.loop.create_task(cleanUp())
client.run(config.get("discord", "token"))
