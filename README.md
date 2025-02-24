# AmfSan Cryptocurrency Market Strategy Alert System

<p align="left">
  <strong style="background-color: green;">English</strong>
  |
  <a href="./README_zh.md" target="_Self">简体中文</a>
</p>

## Project Overview
This project is an intelligent trading market analysis system based on Python and Web3. It utilizes a distributed data processing architecture with RabbitMQ and MySQL to achieve real-time market data analysis and trading strategy optimization.

API Documentation References: Binance OpenAPI Documentation, Huobi.pro OpenAPI Documentation.

## Business Features
- **Data Crawling**: Periodically fetches Binance market K-line data, supports multiple data sources and trading pairs.
- **Technical Indicator Calculation**: Computes various technical indicators, including KDJ, MACD, and moving averages.
- **Scheduled and Real-time Alerts**: Generates trading signal alerts based on preset strategies. Strategy optimization is primarily achieved through historical market data analysis and engineering optimization using ChatGPT, Claude, and Gemini.

## Implemented Features
- **Price Alerts**: Triggers real-time alerts when prices break take-profit/stop-loss levels.
- **MACD Alerts**: Monitors MACD golden/death crosses at multiple time intervals (1 day, 4 hours, 1 hour, 15 minutes, 5 minutes) and generates alerts.
- **KDJ Alerts**: Monitors KDJ golden/death crosses at multiple time intervals and generates alerts.
- **Strategy Signal Alerts**: Provides real-time buy/sell signal alerts.

## Strategy Operators
- **Moving Averages**: EMA indicators with values of 12 and 26.
- **MACD Values**: DEA, DIF, and MACD trend analysis.
- **KDJ Values**: KDJ trend and crossover analysis.
- **Trading Volume**: Inflow/outflow volume analysis over 4-hour and 1-hour periods.
- **Bollinger Bands**: Calculates upper and lower bands for resistance and support levels.

## Installation and Usage
### 1. Environment Setup
Ensure the system has the following dependencies installed:
- Python 3.8+
- RabbitMQ
- Redis
- MySQL

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Database
```sql
CREATE DATABASE amf DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'myuser'@'localhost' IDENTIFIED BY 'mypass';
CREATE USER 'myuser'@'%' IDENTIFIED BY 'mypass';
GRANT ALL ON amf.* TO 'myuser'@'localhost';
GRANT ALL ON amf.* TO 'myuser'@'%';
FLUSH PRIVILEGES;
```

### 4. Configure Message Queue
```bash
rabbitmqctl add_user username password
rabbitmqctl authenticate_user username password
```

### 5. Start Services
```bash
python run.py
python runscheduler.py
python runconsumer.py
```
