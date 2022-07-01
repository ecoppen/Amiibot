# Amiibot
A python (3.9+) web scraper and stock notifier for Amiibo

![amiibot](https://user-images.githubusercontent.com/51025241/176945832-469f75d2-c3e8-4ba0-be54-77e1823b2987.png)

## Getting started
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
