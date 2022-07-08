# Getting started

Amiibot is a web scraper and stock notifier for Amiibo. You can select a range of different websites to track and 
when a stock update occurs (`In stock`, `Out of stock`, `Price change`) you will notified via your selected medium.

## Requirements
### Hardware requirements
To run this bot it is recommended that you run a linux cloud instance however it will run perfectly fine on a Raspberry Pi. 

!!! info "Do I need a server?"

    An external server setup is recommended over one in your home because of speed, reliability and location. 
    You are welcome to skip this section if you are confident that your device will be on 24/7, 
    maintain a stable internet connection and have no issue with accessing IP or geographically blocked websites.

### Software requirements

- git
- Python 3.9
- pip (pip3)
- pipenv

Optional:

- PostgreSQL

## Installation

!!! Example "Linux pre-setup requirements"

     - Make sure your repositories are up-to-date `sudo apt-get update`
     - Upgrade any installed packages that are out of date `sudo apt-get upgrade`
     - Install pip and git `sudo apt install -y python3-pip git`

### Linux/MacOS/Raspberry (terminal)
- Create a PostgreSQL database named `amiibot` or skip this step if using sqlite
- Clone the repo `git clone https://github.com/ecoppen/Amiibot.git`
- Navigate to the repo root `cd Amiibot`
- Navigate to the config folder `cd config`
- Create the config file from template `cp config.json.example config.json`
- Populate the `config.json` files as required using a text editor e.g. `nano config.json`
- Navigate back to the repo root `cd ..`
- Install pipenv `pip install pipenv`
- Install required packages `pipenv install`
- Activate the environment `pipenv shell`

### Developers
- Install developer requirements from pipenv `pipenv install --dev`
- Install pre-commit hooks `pre-commit install`

## Configuration
Amiibot has many configurable features and possibilities. By default, these settings are configured via the configuration file (see below).

### The Amiibot configuration file
Amiibot uses a set of configuration parameters during its operation that all together conform to the bot configuration.

By default, the bot loads the configuration from the config.json file, located in the `config` folder.

### Configuration parameters

The table below will list all configuration parameters available.

| Parameter                      | Description                                                                                                                                                                                                                                                  |
|--------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `database.engine`              | **Required.** The database engine you wish to use to keep track of stock. Currently support is for `postgres` and `sqlite`. <br>*Defaults to `"sqlite"`.* <br> **Datatype: ** String.                                                                        |
| `database.username`            | If required by the database engine, this is the username you wish to login with. <br>**Datatype:** String.                                                                                                                                                   |
| `database.password`            | If required by the database engine, this is the password required for the username above. <br>**Datatype:** String.                                                                                                                                          |
| `database.host`                | If required by the database engine, this is the IP address of the database server. <br>*Defaults to `127.0.0.1`.* <br> **Datatype:** IP Address.                                                                                                             |
| `database.port`                | If required by the database engine, this is the port number of the database server. <br>*Defaults to `5432`.* <br> **Datatype:** Integer between 1 and 65535.                                                                                                |
| `database.name`                | **Required.** The name of the database. <br>*Defaults to `amiibot`.* <br> **Datatype:** String.                                                                                                                                                              |
| `messengers`                   | **Required.** A dictionary with uniquely named keys for each messenger. You can have multiple instances of messengers e.g. 5 for discord, 3 for telegram. <br>*Defaults to `messenger_1`.* <br> **Datatype:** String.                                        |
| `messengers.active`            | **Required.** Allows you to specify whether messages should be sent to this messenger or not. If `False` then the bot will still gather stock information for the database. <br>*Defaults to `true`.* <br> **Datatype:** Boolean.                            |
| `messengers.embedded_messages` | **Required.** Allows you to specify whether messages should contain pictures or just be text only.<br>*Defaults to `true`.* <br> **Datatype:** Boolean.                                                                                                      |
| `messengers.messenger_type`    | **Required.** Which messenger service should this messenger setup send to? Current options are `discord` and `telegram`.<br>*Defaults to `discord`.* <br> **Datatype:** String.                                                                              |
| `messengers.webhook_url`       | If the `messenger_type` is `discord` then you will need the `webhook_url` for the discord channel you wish to send to.<br>*Defaults to `https://discord.com/api/webhooks/`.* <br> **Datatype:** URL.                                                         |
| `messengers.bot_token`         | If the `messenger_type` is `telegram` then you will need the `bot_token` for the telegram bot you wish to use to send the messages from.<br>**Datatype:** String.                                                                                            |
| `messengers.chat_id`           | If the `messenger_type` is `telegram` then you will need the `chat_id` for the telegram user or group you wish to send the messages to.<br>**Datatype:** String.                                                                                             |
| `messengers.stockists`         | **Required.** A list of domain names for stockists you wish the scraper to collect information from. See the list below for options currently available.<br> **Datatype:** List of Strings.                                                                  |
| `scrape_interval`              | **Required.** How long of a gap in seconds between scraping sessions?<br>*Defaults to `1800` seconds e.g. `30 minutes`.* <br> **Datatype:** Integer >= 600.                                                                                                  |
| `notify_first_run`             | **Required.** Do you want to be notified/messaged as the database first initialises? Be warned, depending on your settings this could result in hundreds of pings if you have added lots of stockists.<br>*Defaults to `false`.* <br> **Datatype:** Boolean. |
| `heartbeat`                    | **Required.** Do you want a daily message to be sent letting you know that the bot is still active? If all messengers are set to `false` then these messages will not be recevied but will be logged.<br>*Defaults to `true`.* <br> **Datatype:** Boolean.   |
| `check_version_daily`          | **Required.** Do you want the bot to automatically check every day whether a new update is available? <br>*Defaults to `true`.* <br> **Datatype:** Boolean.                                                                                                  |

### Stockists
Currently supported websites for scraping are: 

- bestbuy.com
- bestbuy.ca
- gamestop.com
- game.co.uk
- mecca-japan.com
- nintendo.co.uk
- play-asia.com
- shopto.net
- thesource.ca
