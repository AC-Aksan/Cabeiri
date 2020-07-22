#!/usr/bin/env python

import configparser
import argparse
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
try: 
    from ujson import loads, dumps
except ImportError: # Library unavailable, falling back
    from json import loads, dumps
import collections

configFileName = "cabeiri.config.ini"
webhookFileName = "cabeiri.webhooks.pdb"
chainMessage = "HackSocNotts"
running = True

# Helper Functions
def writeBackConfig():
    config["server"]["fqhost"] = "http://{0}:{1}/".format(config.get("server","host"), config.get("server", "port"))
    with open(configFileName, 'w') as configFile:
        config.write(configFile)

def writeBackWebhooks():
    with open(webhookFileName, 'w') as webhookFile:
        for key, val in webhooks.items():
            webhookFile.write(f"{key}\t{val[0]}\t{val[1]}\n")
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
    global chainSeg
    while running:
        currentTime = time.monotonic()

        registrant_keys = list(registrants.keys())
        for key in registrant_keys:
            if (currentTime - registrants.get(key, currentTime)) > 300:
                del registrants[key]
        
        initiation_keys = list(initiations.keys())
        for key in initiation_keys:
            if (currentTime - initiations.get(key, currentTime)) > 300:
                del initiations[key]
        
        local_channel = config.get("discord", "channel", fallback="")
        localized = local_channel != ""
        if localized:
            local_channel = client.get_channel(int(config.get("discord","channel")))
        while len(completions) > 0:
            user_id, payload = completions.popleft()
            if localized:
                await local_channel.send(f"Chain completed for <@{user_id}> with payload: `{payload}`")
            else:
                await client.get_user(int(user_id)).send(f"Chain completed with payload: `{payload}`")
        while len(validations) > 0:
            user_id, payload = validations.popleft()
            if localized:
                await local_channel.send(f"Validation chain completed for <@{user_id}> with payload: `{payload}`")
            else:
                await client.get_user(int(user_id)).send(f"Validation chain completed with payload: `{payload}`")
            valid[user_id] = webhooks[user_id]
        while len(chainCompletitions) > 0:
            user_id, payload = chainCompletitions.popleft()
            if localized:
                await local_channel.send(f"Chain segment completed for <@{user_id}> with payload: `{payload}`")
            else:
                await client.get_user(int(user_id)).send(f"Chain segment completed with payload: `{payload}`")
            chain.pop(0)
            chainSeg += 1
            if len(chain) == 0:
                if localized:
                    await local_channel.send(f"Chain completed in {chainSeg} segments with payload: `{payload}`")
            else:
                await fireWebhook(chain[0], payload, chainActivations)
        await asyncio.sleep(1)

async def fireWebhook(user_id, token, struct):
    struct[user_id] = time.monotonic()
    webhookURI = webhooks[user_id][0]
    b = {"id" : user_id, "payload" : token}
    async with aiohttp.ClientSession(json_serialize=dumps) as session:
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
        json = await request.json(loads=loads)
        user_id = json["id"]
        if user_id in initiations:
            del initiations[user_id]
            _, incoming = webhooks[user_id]
            if incoming == identifier:
                completions.append((user_id,json["payload"]))
            else:
                raise web.HTTPForbidden
        elif user_id in validationrequests:
            del validationrequests[user_id]
            _, incoming = webhooks[user_id]
            if incoming == identifier:
                validations.append((user_id,json["payload"]))
            else:
                raise web.HTTPForbidden
        elif user_id in chainActivations:
            del chainActivations[user_id]
            _, incoming = webhooks[user_id]
            if incoming == identifier:
                chainCompletitions.append((user_id,json["payload"]))
            else:
                raise web.HTTPForbidden
        else:
            if user_id in webhooks:
                raise web.HTTPRequestTimeout
            else:
                raise web.HTTPUnauthorized
    except:
        raise web.HTTPBadRequest
    raise web.HTTPOk


if __name__ == "__main__":

    # Data Structures
    webhooks = {}
    registrants = {}
    valid = {}
    initiations = {}
    completions = collections.deque()
    validationrequests = {} 
    validations = collections.deque()
    chainActivations = {}
    chain = []
    chainCompletitions = collections.deque()
    chainSeg = 0

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
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--token", type=str, 
                        help = "the discord bot token to be used")
    parser.add_argument("-o", "--owner", type=str, 
                        help = "a discord user id to preconfigure the bot owner")
    parser.add_argument("-n", "--hostname", type=str, 
                        help = "the hostname to present the server on")
    parser.add_argument("-p", "--port", type=int, 
                        help = "the port to bind the webserver to")
    args = parser.parse_args()

    if args.token != None :
        config["discord"]["token"] = args.token
    if args.owner != None :
        config["discord"]["owner"] = args.owner
    if args.hostname != None :
        config["server"]["host"] = args.hostname
    if args.port != None :
        config["server"]["port"] = args.port
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


    # Print when ready
    @client.event
    async def on_ready():
        print('Online as {0.user}'.format(client))


    # Active Reactions
    @client.event
    async def on_message(message):
        global chainSeg
        # Handle DMs
        if message.channel.type == discord.ChannelType.private:
            if message.author.id in registrants:
                webhooks[message.author.id] = (message.content, createWebhook(message.author.id, message.content))
                await message.author.send(f"Incoming URL: `{config.get('server','fqhost')}cabeiri/{webhooks[message.author.id][1]}`")
                writeBackWebhooks()
            elif message.author != client.user:
                await message.author.send("No active registration exists, you were potentially timed out.")
                if config.get("discord", "channel", fallback="") != "":
                    await message.author.send(f"Registration can be done in <#{config.get('discord', 'channel')}>.")


        # Localize listening to a given channel
        if message.content.lower().startswith("|localize"):
            if int(config.get("discord", "owner")) == message.author.id:
                config["discord"]["channel"] = str(message.channel.id)
                writeBackConfig()
                await message.channel.send(f"Activity localized to <#{config.get('discord', 'channel')}>.")
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
                await message.channel.send(f"Ownership transfered to <@{config.get('discord', 'owner')}>.")
            else:
                await message.channel.send("Ownership can only be transfered by the owner.")

        # Register a new webhook pair
        if message.content.lower() == "|register":
            if message.author.id in webhooks:
                if message.author.id in valid:
                    del valid[message.author.id]
                    await message.channel.send("Chain invalidated.")
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
                    await message.author.send(f"Outgoing URL: `{webhooks[message.author.id][0]}`")
                    await message.author.send(f"Incoming URL: `{config.get('server','fqhost')}cabeiri/{webhooks[message.author.id][1]}`")
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
                await message.channel.send(f"Initiating chain with payload: `{token}`")
                statusCode = await fireWebhook(message.author.id, token, initiations)
                if statusCode == -1:
                    await message.author.send("An error occured and the request could not be sent.")
                elif statusCode != 200:
                    await message.author.send(f"HTTP request failed with code: `{statusCode}`")
            else:
                await message.channel.send("Unregistered.")
        
        # Fire a validation chain
        if message.content.lower() == "|validate":
            if message.author.id in webhooks:
                token = secrets.token_hex(8)
                await message.channel.send(f"Validating chain with payload: `{token}`")
                statusCode = await fireWebhook(message.author.id, token, validationrequests)
                if statusCode == -1:
                    await message.author.send("An error occured and the request could not be sent.")
                elif statusCode != 200:
                    await message.author.send(f"HTTP request failed with code: `{statusCode}`")
            else:
                await message.channel.send("Unregistered.")

        # Loop through the validated chains
        if message.content.lower() == "|chain":
            if len(valid) > 0:
                await message.channel.send("Preparing chain.")
                chain.clear()
                chainSeg = 0
                chainActivations.clear()
                for entry in valid:
                    chain.append(entry)
                await message.channel.send(f"Beginning chain with payload: `{chainMessage}`")
                await fireWebhook(message.author.id, chainMessage, chainActivations)
            else:
                await message.channel.send("No validated chains.")

        # Ping test
        if message.content.lower() == "|ping":
            await message.channel.send("> Online and Active")


    # Set up webhook server
    app = web.Application()
    app.add_routes([web.post('/cabeiri/{encode}', webhookHandler)])
    runner = web.AppRunner(app)


    # Start web server
    webThreadRunner = threading.Thread(target=startServer, args=(runner,))
    webThreadRunner.start()

    # Start discord bot
    client.loop.create_task(cleanUp())
    client.run(config.get("discord", "token"))