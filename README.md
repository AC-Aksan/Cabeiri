# Cabeiri
A web socket to discord interface for Rube-Goldberg chains.

## Config Arguments
- `-t`, `--token`
  Used to provide the discord bot token to be used.
  
- `-o`, `--owner`
  Used to provide the user ID of the owner, alternative to using the `|claim` command.
  
- `-n`, `--hostname`
  Used to specify the unqualified host name, defaults to `localhost`. 
  
- `-p`, `--port`
  Used to specify the port to operate on, defaults to `6280`.

## Config Commands
- `|claim`
  Used to claim ownership of an unclaimed instance of the bot. 
  
- `|localize`
  Used to set the channel that the bot answers commands in, can be used in any channel and only by the owner.
  
- `|ping`
  Used to get a response from the bot to confirm life.
  
## Basic Commands
- `|register`
  Used to register a new webhook pair, completes in DMs.
  
- `|status`
  Used to check the details of an existing webhook pair, completes in DMs.
  
- `|initiate`
  Used to fire the initial outgoing webhook and begin listening on the incoming webhook, mentions the initiator on completion, in channel if localized or DMs otherwise. 

- `|validate`
  Used to fire a confirmatory outgoing webhook and adds the chain to the valid list if successful, mentions the initiator on completion, in channel if localized or DMs otherwise. 

- `|chain`
  Used to connect all the validated chains into one giant chain.
  
# Webhook Request Format
  The expected format of the final HTTP POST request matches the first in consisting of a JSON body with the following keys, `id` unique to the user and consistent between activations and `payload` unique to the activation. A message without the correct `id` for the URL that is being used will be rejected but the `payload` does not need to be correct to the activation. Overall the outgoing message serves as an example for the ingoing message.

Example request body:
```
{
  "id": 123456789123456789,
  "payload": "abcdefghijklmnop"
}
```
-`id` 
  Required, unique to user, must be accurate.
  
-`payload` 
  Required, unique to activation, can be innacurate.
  
The following header will additionally be expected to specify that the body uses JSON encoding:
```
{
  'Content-Type': 'application/json'
}
```
  

# Competition Premise
  The competition is open to all [HackSocNottingham](https://github.com/HackSocNotts) members and revolves around making the most complicated, convoluted, unreliable and over-engineered methods of plugging one piece of tech into another, beginning and ending with this bot. 
  Prizes are to be awarded for the longest chains, the most protocols used in a chain and the best individual protocol used in a chain and will be awarded after the close of the competition.
  The competition will run from 19:00 28/04/2020 to 19:00 05/05/2020 and entries will be expected to provide evidence of their Rube-Goldberg-Chain whether in the form of source code, that can then be posted after the competition concludes, or appropriate evidence of the more unique stages of the chain. 

# Useful Tools
- [Webhook.site](https://webhook.site/)
  Useful for seeing the output of requests.
- [Postman](https://www.postman.com/)
  Useful for creating and testing requests.
- [Insomnia](https://insomnia.rest/)
  Useful for creating and testing requests.
- [If This Then That](https://ifttt.com/)
  Useful for plugging anything into anything.
