# 🧭 Telegram Signal Auto-Trading Bot [P-495]

A bot that listens to Telegram channels for trading signals (text and images) and automatically executes trades on MetaTrader 4 or MetaTrader 5.

---

## 📚 Table of Contents

- [About](#about)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Screenshots](#screenshots)
- [API Documentation](#api-documentation)
- [Contact](#contact)

---

## 🧩 About

This project automates forex/CFD trading by reading signals from Telegram channels and placing orders on MT4 or MT5. It supports both text-based signals and image-based signals (via OCR). Key goals: reduce manual execution, enforce risk (max loss), and log trades to CSV.

---

## ✨ Features

- **Telegram signal monitoring** – Listens to one or more Telegram channels for BUY/SELL signals
- **Image signal parsing** – Uses Tesseract OCR to read signals from shared screenshots
- **MT4 & MT5 support** – Separate scripts for MetaTrader 4 and MetaTrader 5
- **Risk management** – Configurable max loss and lot sizing
- **Trade logging** – Records all trades to `trading_history.csv`

---

## 🧠 Tech Stack

| Category   | Technologies |
| ---------- | ------------ |
| Languages  | Python       |
| Libraries  | Telethon, MetaTrader5, pytesseract, Pillow |
| Database   | CSV (trading history) |
| Tools      | Tesseract OCR |

---

## ⚙️ Installation

```bash
# Clone the repository
git clone https://github.com/MaxValueBuilder/telegram-signal-auto-trading-bot.git

# Navigate to the project directory
cd telegram-signal-auto-trading-bot/codebase

# Install Tesseract OCR (required for image signals)
# Windows: https://sourceforge.net/projects/tesseract-ocr.mirror/
# Add to PATH: C:\Program Files\Tesseract-OCR and C:\Program Files\Tesseract-OCR\tessdata

# Install Python dependencies
pip install -r requirements.txt
# Or minimal: pip install pytesseract Pillow python-telegram-bot telethon MetaTrader5
```

---

## 🚀 Usage

**MT5:**
```bash
python mt5_auto_trading.py
```

**MT4:**
```bash
python mt4-auto_trading.py
```

Ensure MetaTrader (MT4 or MT5) is installed and running; the bot will connect and start listening to the configured Telegram channel(s).

---

## 🧾 Configuration

Set these in the script (or move to a `.env` and load them):

| Variable          | Description                    |
| ----------------- | ------------------------------ |
| `api_id`          | Telegram API ID                |
| `api_hash`        | Telegram API hash              |
| `phone_number`    | Your Telegram phone number     |
| `channel_id_1` / `channel_id_2` | Telegram channel ID(s) to monitor |
| `login`           | MT4/MT5 account ID             |
| `password`        | MT4/MT5 account password       |
| `server` (MT5) / `broker` (MT4) | Broker server name     |
| `max_loss`        | Max loss in dollars            |
| `pip_value`       | Pip value per standard lot (MT4) |

---

## 🖼 Screenshots

_Add demo images, GIFs, or UI preview screenshots here._

---

## 📜 API Documentation

This project does not expose a REST API. It uses:

- **Telethon** – Telegram client API
- **MetaTrader5** – MT5 terminal API (for `mt5_auto_trading.py`)
- **MT4** – Broker connection via external token/API (for `mt4-auto_trading.py`)

---

## 📬 Contact

| | |
|---|---|
| **Author** | Kanjiro Honda |
| **Email** | kanjirohonda@gmail.com |
| **GitHub** | https://github.com/MaxValueBuilder |
| **Website/Portfolio** | https://kanjiro-honda-portfolio.vercel.app/ |

---

## 🌟 Acknowledgements

- [Telethon](https://github.com/LonamiWebs/Telethon) – Telegram client
- [MetaTrader5](https://www.mql5.com/en/docs/integration/python_metatrader5) – Python API for MT5
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) – Image text recognition
