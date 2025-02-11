# token-telegram-warning
Telegram message if token price is out of range

When this script runs on linux, it checks regularly on DEX for token price and if the price is outside of price range on that particular DEX and chain, it will send you a telegram message.

You need to put Telegram bot key and your telegram ID into the code and activate the bot by /start

Script is tailored to price of MPS/WXDAI pair on sushiswap gnosis chain, but you can replace token addresses and bot keyword.

Example of telegram command you send to bot

```
monitor-mps 3.58 3.73
```

Bot responds with confirmation "Limits updated"

Then when price is out of this range, you will receive alert from bot "ALERT! MPS token out of limits"
