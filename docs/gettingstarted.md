# Getting started

Amiibot is a web scraper and stock notifier for Amiibo. You can select a range of different websites to track and 
when a stock update occurs (`In stock`, `Out of stock`, `Price change`) you will notified via your selected medium.

## Server acquisition

!!! info "Why do I need a server?"

    An external server setup is recommended over one in your home because of speed, reliability and location. 
    You are welcome to skip this section if you are confident that your device will be on 24/7, 
    maintain a stable internet connection and have no issue with accessing IP or geographically blocked websites.

## Installation
- Create a postgres database named `amiibot` or skip this step if using sqlite
- Install git `apt-get install git` 
- Clone the repo `git clone https://github.com/ecoppen/Amiibot.git`
- Navigate to the repo root `cd Amiibot`
- Navigate to the config folder `cd config`
- Create the config file from template `cp config.json.example config.json`
- Populate the `config.json` files as required
- Navigate back to the repo root `cd ..`
- Install pipenv `pip install pipenv`
- Install required packages `pipenv install`
- Activate the environment `pipenv shell`

## Developers
- Install developer requirements from pipenv `pipenv install --dev`
- Install pre-commit hooks `pre-commit install`
