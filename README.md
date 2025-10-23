# WoonnetRijnmondBot

A Python-based bot to automate rental applications on the WoonnetRijnmond website.

## Features

- **Automated Login:** Securely logs into your WoonnetRijnmond account.
- **Listing Discovery:** Efficiently discovers new rental listings using the website's internal API.
- **Timed Applications:** Automatically applies to selected listings at a specific time (20:00 CET).
- **User-Friendly GUI:** A simple graphical interface built with `ttkbootstrap` to manage the bot.
- **Secure Credential Storage:** Uses the `keyring` library to store your credentials securely in your operating system's credential manager.

## How to Use

The easiest way to use this bot is to download the latest executable from the **[Releases](https://github.com/SBalcioglu/WoonnetRijnmondBot/releases)** page.

1.  Go to the [Releases](https://github.com/SBalcioglu/WoonnetRijnmondBot/releases) section on the right.
2.  Download the `WoonnetRijnmondBot.exe` file from the latest release.
3.  Run the executable file.
4.  Enter your WoonnetRijnmond username and password.
5.  Click "Discover Listings" to find new properties.
6.  Select the listings you want to apply for.
7.  Click "Apply to Selected (at 8 PM)". The bot will then wait until 8:00 PM to apply.

## Automated Builds

This repository is configured with a GitHub Actions workflow that automatically builds a new executable (`.exe`) and creates a new release every time a commit is pushed to the `main` branch.
