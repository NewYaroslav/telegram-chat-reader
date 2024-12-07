# Telegram Monitoring Tool

## Description

The **Telegram Monitoring Tool** is an asynchronous Python application that allows you to interact with Telegram chats, channels, and forums using the Telethon library. It provides features for sending messages, fetching chat histories, saving chats and forum topics, and monitoring new messages in specified chats or topics.

---

## Features

1. **Send Messages**: Send messages to specific chats or channels.
2. **Fetch Chat History**: Download and save message history, including forum topics.
3. **Save Chats and Topics**: Retrieve and save the list of all chats, channels, and forum topics.
4. **Monitor Chats**: Continuously listen to specified chats or topics for new messages, and save them to a file.
5. **Support for Forums**: Handle Telegram forums and their topics, including filtering by topic ID.

---

## Installation

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd <repository-folder>
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up Environment Variables**:
   Create a `.env` file with the following variables:
   ```env
   API_ID=<your-telegram-api-id>
   API_HASH=<your-telegram-api-hash>
   PHONE_NUMBER=<your-telegram-phone-number>
   TELEGRAM_PASSWORD=<your-telegram-password> # Optional if 2FA is enabled
   ```

---

## Usage

1. **Run the Script**:
   ```bash
   python monitoring_tool.py
   ```

2. **Choose an Action**:
   - `[1] Send a message`: Send a message to a specified chat or channel.
   - `[2] Load and display chat list`: Save all chats and forum topics to a file.
   - `[3] Fetch chat history`: Download and save the message history for a chat or topic.
   - `[4] Listen to messages in chats`: Monitor specified chats or topics for new messages.
   - `[5] Exit`: Close the application.

---

## Monitoring Messages

When you select option `[4]`, you can:
1. Enter chat IDs, usernames, or titles to monitor.
2. Specify topic IDs for forums (optional).
3. Save monitored messages to a file.

### Example Input:
- **Chat by ID**: `-1001234567890`
- **Chat by Username**: `@example_channel`
- **Chat by Title**: `General Chat`

---

## Logging

The tool uses `colorlog` for colored console output and writes logs to `application.log`.

### Example Log Entry:
```text
2024-12-02 10:50:05,594 - INFO - Forum detected: Forum ID=-1001512761594, Topic ID=574381
```

---

## Requirements

- **Python 3.7+**
- **Telethon**
- **python-dotenv**
- **colorlog**
- **rich**

---

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests to improve the tool.

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

### Author

- Developed with ❤️ using the Telethon library.