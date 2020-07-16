# Description

Runs [matterbridge](https://github.com/42wim/matterbridge/) as a docker-compose service
to bridge channels across chat services used by the community.

## Bridges

- IRC `#openmrs` channel
- Telegram `OpenMRS Chat` channel ([t.me/OpenMRS](https://t.me/OpenMRS))
- Slack `#general` channel

## Configuration

All credentials are configured via the `.env` file.

# Setup

## IRC

The `omrsbridge` user is registered to openmrs-infrastructure+irc email address
and has voice in the `#openmrs` channel.

We mute Travis notifications and OpenMRSBot short link generation from being copied
from IRC, since they create too much noise for Slack's #general channel.

## Telegram

The `omrsbridge_bot` was created using BotFather from the `OpenMRS_Admin` user
registered to the OpenMRS telephone number.

## Slack

An `omrsbridge` app was created using classic bot settings per the
[Slack bot setup](https://github.com/42wim/matterbridge/wiki/Slack-bot-setup)
instructions in the matterbridge documentation. When it was created in July 2020,
matterbridge used Slack "classic" bot creation and did not support granular permissions,
so you needed to use a special link when creating the bot, add the specific scopes
mentioned in the documentation, and avoid upgrading to granular permissions despite
Slack promoting their use (don't click on links/buttons offering to upgrade to granular
permissions or it won't work). matterbridge uses the Bot User OAuth Access Token (starting
with `xoxb-`) and will bridge to any channels the `omrsbridge` app is invited to within
Slack.
