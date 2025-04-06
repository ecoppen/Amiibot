<p align="center">
  <a href="https://ecoppen.github.io/amiibot/">
    <img src="https://raw.githubusercontent.com/ecoppen/Amiibot/main/docs/amiibot.png" width="200"  alt="Amiibot">
  </a>
</p>

<h1 align="center">
Amiibot
</h1>

<p align="center">
A python (3.12+) web scraper and stock notifier for Amiibo
</p>
<p align="center">
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

## Installation

1. Run updates
   ```sh
   sudo apt update && sudo apt upgrade -y
   ```

2. Clone the repository and setup:
   ```sh
   git clone https://github.com/ecoppen/Amiibot.git
   cd Amiibot
   cd config
   cp config.example.json config.json
   nano config.json
   cd ~/
   ```
   
3. Install `uv` package manager and then install the dependencies:
   ```sh
   curl -LsSf https://astral.sh/uv/install.sh | sh 
   uv sync
   ```

4. Make the script executable 
   ```sh
   chmod +x ~/Amiibot/amiibot_runner.sh
   ```

5. Add the script to crontab
   ```sh
   crontab -e
   */20 * * * * ~/Amiibot/amiibot_runner.sh
   ```
