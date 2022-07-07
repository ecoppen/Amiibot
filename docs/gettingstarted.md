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

| Parameter                      | Description                                                                           |
|--------------------------------|---------------------------------------------------------------------------------------|
| `database.engine`              | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `database.username`            | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `database.password`            | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `database.host`                | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `database.port`                | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `database.name`                | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `messengers`                   | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `messengers.active`            | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `messengers.embedded_messages` | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `messengers.messenger_type`    | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `messengers.webhook_url`       | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `messengers.bot_token`         | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `messengers.chat_id`           | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `messengers.stockists`         | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `scrape_interval`              | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `notify_first_run`             | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `heartbeat`                    | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
| `check_version_daily`          | **Required.** .<br>*Defaults to ``.* <br> **Datatype:** . |
