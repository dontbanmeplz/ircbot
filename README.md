# IRC DCC Bot with Async Support

An async IRC bot that can send messages to IRC channels and receive files via DCC (Direct Client Connection). Built with Python's `irc` library and designed for integration into web interfaces.

## Features

- **Async/await support** - Built on `asyncio` for non-blocking operations
- **Send messages** to IRC channels
- **Receive files via DCC** - Automatically handles DCC SEND requests
- **Web interface** - Flask-based web UI for controlling the bot
- **Callbacks** - Hook into events (file received, message sent, connected)
- **Thread-safe** - Suitable for web application integration

## Installation

```bash
# Install dependencies
pip install irc flask

# Or if using uv (recommended)
uv pip install irc flask
```

## Quick Start

### 1. Command Line Usage

Run the bot directly from the command line:

```python
import asyncio
from async_dcc_bot import AsyncDCCBot

async def main():
    # Create bot
    bot = AsyncDCCBot(
        channel="#ebooks",
        download_dir="./downloads",
        on_file_received=lambda f, s: print(f"Got file: {f} ({s} bytes)"),
    )
    
    # Start bot in background task
    bot_task = asyncio.create_task(
        bot.run("irc.irchighway.net", 6667, "MyBot")
    )
    
    # Wait until ready
    await bot.wait_until_ready()
    
    # Send a message
    await bot.send_message("Hello, IRC!")
    
    # Keep running
    await asyncio.sleep(300)
    
    # Stop
    bot.disconnect()
    bot_task.cancel()

asyncio.run(main())
```

### 2. Web Interface

Start the Flask web interface:

```bash
python web_interface.py
```

Then open http://localhost:5000 in your browser.

The web interface allows you to:
- Connect to IRC servers
- Join channels
- Send messages
- View received files
- Monitor bot status

## Usage Examples

### Basic Bot

```python
import asyncio
from async_dcc_bot import AsyncDCCBot

async def main():
    bot = AsyncDCCBot(
        channel="#mychannel",
        download_dir="./downloads"
    )
    
    # Start bot as background task
    bot_task = asyncio.create_task(
        bot.run("irc.example.net", 6667, "MyBot")
    )
    
    await bot.wait_until_ready()
    await bot.send_message("Hello!")
    
    # Keep bot running
    await asyncio.sleep(3600)
    
    bot.disconnect()
    bot_task.cancel()

asyncio.run(main())
```

### With Callbacks

```python
def on_file_received(filename, size):
    print(f"Downloaded: {filename} ({size} bytes)")
    # Process the file here

def on_connected():
    print("Bot is ready!")

def on_message_sent(message):
    print(f"Sent: {message}")

bot = AsyncDCCBot(
    channel="#downloads",
    download_dir="./downloads",
    on_file_received=on_file_received,
    on_connected=on_connected,
    on_message_sent=on_message_sent,
)
```

### Requesting Files from XDCC Bots

Many IRC channels host bots that serve files via XDCC (an extension of DCC):

```python
await bot.send_message("@search Some Movie")
# Wait for bot to respond with pack numbers

# Request a specific pack
await bot.send_message("/msg XDCCBot xdcc send #123")
# The file will be automatically received via DCC
```

## API Reference

### AsyncDCCBot

**Constructor:**
```python
AsyncDCCBot(
    channel: str,                                      # IRC channel to join
    download_dir: str = "./downloads",                 # Where to save files
    on_file_received: Callable[[str, int], None] = None,  # File callback
    on_connected: Callable[[], None] = None,           # Connection callback
    on_message_sent: Callable[[str], None] = None,     # Message callback
)
```

**Methods:**

- `async run(server, port, nickname, password=None)` - Connect and run bot (call as background task)
- `async wait_until_ready(timeout=30.0)` - Wait until connected and joined
- `async send_message(message)` - Send a message to the channel
- `disconnect(message="Goodbye!")` - Disconnect from server

**Properties:**

- `is_connected` - Whether bot is connected to server
- `is_joined` - Whether bot has joined the channel
- `channel` - The IRC channel name
- `download_dir` - Directory for downloaded files

## Web Interface API

The Flask web interface provides REST endpoints:

- `GET /` - Main web interface
- `GET /api/status` - Get bot connection status
- `POST /api/connect` - Connect to IRC server
- `POST /api/disconnect` - Disconnect from server
- `POST /api/send` - Send a message
- `GET /api/messages` - Get list of sent messages
- `GET /api/files` - Get list of received files

### Example API Request

```bash
# Connect to server
curl -X POST http://localhost:5000/api/connect \
  -H "Content-Type: application/json" \
  -d '{
    "server": "irc.irchighway.net",
    "port": 6667,
    "nickname": "MyBot",
    "channel": "#ebooks"
  }'

# Send a message
curl -X POST http://localhost:5000/api/send \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello from API!"}'
```

## How DCC Works

DCC (Direct Client Connection) is an IRC protocol extension that allows direct file transfers between clients:

1. Bot connects to IRC server and joins a channel
2. Bot sends a message (e.g., requesting a file from an XDCC bot)
3. Remote bot sends a CTCP DCC SEND message with file info and IP/port
4. Your bot connects directly to the remote bot's IP and port
5. File is transferred directly (not through IRC server)
6. Your bot sends acknowledgments as data is received
7. Connection closes when transfer is complete

## Directory Structure

```
ircbot/
├── async_dcc_bot.py      # Main async bot implementation
├── web_interface.py      # Flask web interface
├── downloads/            # Downloaded files (created automatically)
├── main.py              # Original sync example
├── send-recieve.py      # Original async example
└── README.md            # This file
```

## Troubleshooting

### Bot won't connect
- Check that the server and port are correct
- Verify the nickname isn't already in use
- Ensure the channel exists and is accessible

### Files not downloading
- Verify the download directory is writable
- Check that the remote bot is actually sending the file
- Look for CTCP messages in the bot output

### Web interface not responding
- Make sure no other service is using port 5000
- Check that Flask is running (`python web_interface.py`)
- Look for errors in the console output

### Encoding errors (Unicode/UTF-8)
- **Fixed!** The bot automatically handles non-UTF-8 characters
- IRC messages may contain various encodings
- The bot uses `errors='replace'` to handle these gracefully
- Invalid characters are replaced with � (replacement character)

## Advanced Usage

### Custom Event Handlers

You can override any IRC event handler by subclassing `AsyncDCCBot`:

```python
class MyBot(AsyncDCCBot):
    def on_pubmsg(self, connection, event):
        """Handle public messages in the channel."""
        source = event.source.nick
        message = event.arguments[0]
        print(f"<{source}> {message}")
        
        # Respond to mentions
        if self.connection.get_nickname() in message:
            asyncio.create_task(
                self.send_message(f"Hi {source}!")
            )
```

### Multiple Channels

To join multiple channels, you can create multiple bot instances:

```python
bots = [
    AsyncDCCBot(channel="#channel1"),
    AsyncDCCBot(channel="#channel2"),
    AsyncDCCBot(channel="#channel3"),
]

for bot in bots:
    await bot.connect_and_run("irc.server.net", 6667, f"Bot{i}")
```

## Documentation References

- [python-irc Documentation](https://python-irc.readthedocs.io/en/latest/)
- [IRC RFC 1459](https://tools.ietf.org/html/rfc1459)
- [DCC Protocol Specification](http://www.irchelp.org/protocol/dccspec.html)
- [CTCP Specification](http://www.irchelp.org/irchelp/rfc/ctcpspec.html)

## License

This code is provided as-is for educational purposes.
