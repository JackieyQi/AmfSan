# AmfSan 加密货币行情策略报警系统

<p align="left">
  <a href="./README.md" target="_Self">English</a>
  |
  <strong style="background-color: green;">简体中文</strong>
</p>

## 项目简介
本项目是一个基于 Python 和 Web3 的智能交易行情分析系统，结合 RabbitMQ + MySQL 构建分布式数据处理架构，实现市场数据的实时分析和交易策略优化。
API文档参考：Binance OpenAPI文档、Huobi.pro OpenAPI文档

## 业务特点
- **数据爬取**：定期爬取币安市场 K 线数据，支持多种数据源，支持多种交易对。
- **技术指标计算**：计算 KDJ、MACD、均线等多种技术指标。
- **定时与实时报警**：结合预设策略进行交易信号报警。预设策略的优化，主要基于ChatGPT、Claude、Gemini进行历史行情数据分析和提高工程优化。


## 实现功能
- **价格报警**：实时价格突破止盈价/止损价，进行实时报警。
- **MACD报警**：MACD的金叉/死叉(时间周期包含1天、4小时、1小时、15分钟、5分钟)，进行实时报警。
- **KDJ报警**：KDJ的金叉/死叉(时间周期包含1天、4小时、1小时、15分钟、5分钟)，进行实时报警。
- **策略信号报警**：买入/卖出信号的实时报警


## 策略算子
- **移动平均值**：指标值为12和26的EMA
- **MACD值**：DEA、DIF、MACD趋势判断
- **KDJ值**：KDJ的趋势判断和交叉判断
- **交易量**：4小时和1小时的流入/流出交易量
- **布林带**：BOLL上轨、下轨计算阻力位和支撑位


## 安装与使用
### 1. 环境准备
确保系统已安装以下依赖：
- Python 3.8+
- RabbitMQ
- Redis
- MySQL

### 2. 安装依赖
```bash
    pip install -r requirements.txt
```

### 3. 配置数据库
----------
    mysql> CREATE DATABASE amf DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    mysql> CREATE USER 'myuser'@'localhost' IDENTIFIED BY 'mypass';
    mysql> CREATE USER 'myuser'@'%' IDENTIFIED BY 'mypass';
    mysql> GRANT ALL ON amf.* TO 'myuser'@'localhost';
    mysql> GRANT ALL ON amf.* TO 'myuser'@'%';
    mysql> flush privileges;
----------

### 4. 配置消息队列
----------
    $ rabbitmqctl add_user username password
    $ rabbitmqctl authenticate_user username password
----------

### 5. 启动服务
----------
    $ python run.py
    $ python runscheduler.py
    $ python runconsumer.py
----------
