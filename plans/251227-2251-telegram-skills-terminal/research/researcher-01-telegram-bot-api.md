# Telegram Bot API Capabilities for Skills Terminal

## Message Formatting

### MarkdownV2 (Recommended)
- **Bold**: `*bold*`
- **Italic**: `_italic_`
- **Code**: `` `inline code` ``
- **Code blocks**: Triple backticks with language
- **Escaping required**: `_*[]()~>#+\-=|{}.!`

### HTML Mode (Alternative)
- Easier for dynamic content
- `<b>`, `<i>`, `<code>`, `<pre>`
- Less escaping issues

## Inline Keyboards

### Button Types
1. **Callback buttons** - `callback_data` string sent to bot
2. **URL buttons** - Open web links
3. **Switch inline** - Trigger inline mode

### Interactive Menus
- Use `editMessageReplyMarkup` for dynamic updates
- Max 100 buttons per message
- Each row: up to 8 buttons

## Message Limits
- **Text**: 4096 characters max
- **Caption**: 1024 characters
- Split long messages into chunks

## File Handling
- Upload: documents, photos, audio, video
- Download: via `getFile` API
- Max file size: 50MB (bots), 2GB (premium users)

## Rate Limits
- 30 messages/second to same chat
- 20 messages/minute to same group
- Bulk notifications: 30 msgs/sec across all chats

## Best Practices
1. Use `python-telegram-bot` library for formatting helpers
2. HTML mode easier for dynamic content
3. Split long outputs into multiple messages
4. Use inline keyboards for skill selection menus

## Sources
- Telegram Bot API Official Docs
- Bot API 8.0 (Nov 2024) Release Notes
