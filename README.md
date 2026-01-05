# 🤖 Telegram Multi-Bot Farm v2.0

A **powerful, scalable** Telegram bot platform managing 1,000-5,000+ bots with advanced reply management, templates, and broadcast system.

## ✨ Key Features

### 🎯 Reply Management System
- **🌐 Global Reply** - One reply for all bots
- **⚙️ Worker-Level Reply** - Reply per worker group
- **🎯 Bot-Level Reply** - Custom reply per bot
- **✅ Bulk Operations** - Set reply for ALL/Multiple/Single bots
- **📁 Template System** - Save & reuse reply templates
- **🔤 Variable Support** - Dynamic `{user_name}`, `{user_id}`, `{bot_name}`

### 🚀 Core Features
- ✅ Webhook-based (no polling, ultra-low RAM)
- ✅ Horizontal scaling with sharded workers
- ✅ Priority-based reply resolution
- ✅ Broadcast system with pause/resume
- ✅ Health monitoring
- ✅ File ID caching
- ✅ Rate limiting
- ✅ Media support (Photo/Video/Document)

## 📊 Architecture

```
Telegram → Nginx → FastAPI Workers → MongoDB + Redis
                    ↓
            Reply Priority System:
            Bot Reply > Worker Reply > Global Reply
```

## 🎨 Reply Priority System

The system automatically resolves which reply to use:

1. **Bot-specific reply** (Highest Priority)
   - Custom message set for individual bot
   
2. **Worker-level reply** (Medium Priority)
   - All bots in same worker use this
   
3. **Global reply** (Lowest Priority)
   - Default reply for all bots

**Example:**
```
Bot A: Uses Custom Reply
Bot B: Uses Worker-1 Reply  
Bot C: Uses Global Reply
Bot D: Uses Global Reply
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Domain with SSL certificate
- Admin bot token

### 1. Generate Encryption Key

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Configure Environment

```bash
cp .env.example .env
nano .env
```

Fill in:
- `ADMIN_BOT_TOKEN` - Your admin bot token
- `ADMIN_USER_IDS` - Admin user IDs (comma-separated)
- `ENCRYPTION_KEY` - Generated encryption key
- `WEBHOOK_DOMAIN` - Your domain
- `MONGODB_URI` - MongoDB connection
- `REDIS_HOST` - Redis host

### 3. Setup SSL

```bash
mkdir ssl
# Place your SSL certificates:
# ssl/fullchain.pem
# ssl/privkey.pem
```

### 4. Start Services

```bash
docker-compose up -d
```

### 5. Check Logs

```bash
docker logs -f bot_farm_admin
docker logs -f bot_farm_worker1
```

## 📋 Admin Commands

### Bot Management
- `/start` - Show all commands
- `/addbot` - Add a new bot
- `/listbots` - List all bots
- `/stats` - System statistics
- `/health` - Health check

### Reply Management
- `/setreply` - Set auto-reply (ALL/Multiple/Single/Worker)
- `/viewreply` - View current reply configuration
- `/globalreply` - Quick set global reply
- `/workerreply` - Set worker-level reply

### Templates
- `/createtemplate` - Create reply template
- `/templates` - View all templates
- `/usetemplate` - Apply template to bots

### Broadcasting
- `/broadcast` - Start a broadcast

## 📝 Usage Examples

### Example 1: Set Global Reply for All Bots

```
Admin: /setreply
Bot: Choose mode...
Admin: [Click "ALL Bots"]
Bot: Send your message...
Admin: Welcome to our service! {user_name} 👋
       
       [Visit Website](https://example.com)
       [Join Channel](https://t.me/channel)
Bot: ✅ Global Reply Set!
```

Now **all 1000 bots** will use this reply!

### Example 2: Set Custom Reply for Specific Bots

```
Admin: /setreply
Bot: Choose mode...
Admin: [Click "Select Multiple"]
Bot: [Shows bot list]
Admin: [Select bot1, bot2, bot3]
Admin: [Click "Done"]
Bot: Send message...
Admin: Premium Service Message 💎
       
       [Upgrade Now](https://premium.com)
Bot: ✅ Reply set for 3 bots!
```

### Example 3: Create and Use Template

```
# Create Template
Admin: /createtemplate
Bot: Give template name...
Admin: Welcome Template
Bot: Send content...
Admin: Hi {user_name}! Welcome! 🎉
       
       [Get Started](https://example.com)
Bot: ✅ Template created!

# Use Template
Admin: /usetemplate
Bot: Select template...
Admin: [Click "Welcome Template"]
Bot: Where to apply?
Admin: [Click "ALL Bots"]
Bot: ✅ Applied to 1000 bots!
```

### Example 4: Worker-Level Reply

```
Admin: /setreply
Bot: Choose mode...
Admin: [Click "By Worker"]
Bot: Select worker...
Admin: [Click "worker-1"]
Bot: Send message...
Admin: This is Worker 1 message
Bot: ✅ All bots in worker-1 will use this!
```

## 🔤 Variables

Use these in your messages:

| Variable | Output |
|----------|--------|
| `{user_name}` | User's first name (e.g., "Rahul") |
| `{user_id}` | User's ID (e.g., "123456789") |
| `{username}` | User's username (e.g., "@rahul") |
| `{bot_name}` | Bot's name (e.g., "MyBot") |
| `{bot_username}` | Bot's username (e.g., "@MyBot") |

**Example:**
```
Message: "Hello {user_name}! Your ID is {user_id}"
Output: "Hello Rahul! Your ID is 123456789"
```

## 📁 Template System

### Why Use Templates?

- **Save Time**: Create once, use many times
- **Consistency**: Same message across multiple bots
- **Easy Updates**: Update template, apply to all
- **Reusable**: Use for different bot groups

### Template Workflow

```
1. Create Template
   └─ Name: "Promo 2024"
   └─ Content: Message with buttons
   └─ Save
   
2. Use Template
   └─ Select: "Promo 2024"
   └─ Apply to: ALL/Multiple/Single
   └─ Done!
```

## 🎯 Reply Strategy Examples

### Strategy 1: Global Default
```
- 1000 bots → ALL use Global Reply
- Easy management
- One message for all
```

### Strategy 2: Worker-Based
```
- worker-1 (250 bots) → Worker Reply 1
- worker-2 (250 bots) → Worker Reply 2  
- worker-3 (250 bots) → Worker Reply 3
- worker-4 (250 bots) → Worker Reply 4
```

### Strategy 3: Mixed
```
- 900 bots → Global Reply
- 50 VIP bots → Custom Premium Reply
- 50 Test bots → Custom Test Reply
```

### Strategy 4: Template-Based
```
- Template "Welcome" → 400 bots
- Template "Promo" → 300 bots
- Template "Support" → 300 bots
```

## 📊 Monitoring

### Check System Stats

```
Admin: /stats

Output:
📊 System Statistics

🤖 Bots:
├ Total: 1000
├ Active: 987
├ Global Reply: 800
├ Worker Reply: 150
└ Custom Reply: 50

👥 Users: 45,234
📁 Templates: 5
```

### View Reply Configuration

```
Admin: /viewreply

Output:
💬 Reply Configuration

🌐 Global Reply: ✅ Enabled
Text: Welcome to our service...

📊 Bot Distribution:
├ Using Global: 800
├ Using Worker: 150
└ Custom Reply: 50
```

## 🔧 Advanced Usage

### Bulk Update All Bots

Update all bots to use global reply:

```javascript
// MongoDB Shell
db.bots.updateMany(
  {},
  {$set: {use_global_reply: true, auto_reply: null}}
)
```

### Set Reply for Specific Worker

```javascript
db.bots.updateMany(
  {assigned_worker: "worker-1"},
  {$set: {use_worker_reply: true, use_global_reply: false}}
)
```

## 📈 Scaling Guide

### Small Setup (< 1000 bots)
```yaml
Workers: 4
Bots per worker: 250
Strategy: Global Reply
```

### Medium Setup (1000-3000 bots)
```yaml
Workers: 12
Bots per worker: 250
Strategy: Worker-based Replies
```

### Large Setup (3000-5000 bots)
```yaml
Workers: 20
Bots per worker: 250
Strategy: Mixed (Global + Custom)
Templates: Use heavily
```

## 🎨 Message Design Tips

### 1. Keep It Short
```
❌ Bad: 10 lines of text
✅ Good: 2-3 lines max
```

### 2. Use Emojis
```
Welcome! 👋
✅ Feature 1
✅ Feature 2
🚀 Get Started
```

### 3. Clear Call-to-Action
```
[Get Started Now](url)
[Learn More](url)
```

### 4. Test Variables
```
Before: "Hello {user_name}!"
After: "Hello Rahul!" ✅
```

## 🔐 Security

- ✅ Encrypted bot tokens (Fernet)
- ✅ Webhook secret tokens
- ✅ Admin-only commands
- ✅ SSL/TLS encryption
- ✅ Worker isolation

## 🐛 Troubleshooting

### Reply Not Working?

```bash
# Check reply configuration
Admin: /viewreply

# Check bot status
Admin: /health

# Check worker logs
docker logs bot_farm_worker1
```

### Template Not Applying?

```bash
# List templates
Admin: /templates

# Check if bots received update
Admin: /listbots
```

### Variables Not Replacing?

- Ensure `use_variables: true` in reply
- Check variable spelling: `{user_name}` not `{username}`
- Test with simple message first

## 📦 Backup

### Backup MongoDB

```bash
docker exec bot_farm_mongodb mongodump --out=/tmp/backup
docker cp bot_farm_mongodb:/tmp/backup ./mongodb_backup_$(date +%F)
```

### Restore MongoDB

```bash
docker cp ./mongodb_backup bot_farm_mongodb:/tmp/backup
docker exec bot_farm_mongodb mongorestore /tmp/backup
```

## 🎯 Best Practices

1. **Start with Global Reply** - Set one reply for all bots first
2. **Use Templates** - Create templates for common messages
3. **Test Variables** - Always test variable replacement
4. **Monitor Stats** - Check `/stats` regularly
5. **Health Checks** - Run `/health` weekly
6. **Backup Database** - Backup MongoDB daily
7. **Use Worker Replies** - Group similar bots by worker
8. **Keep Messages Short** - 2-3 lines optimal
9. **Update Gradually** - Test on few bots first
10. **Document Templates** - Add descriptions to templates

## 📚 File Structure

```
telegram-bot-farm/
├── admin_bot/
│   ├── main.py                 # Entry point
│   ├── handlers.py             # Core handlers
│   ├── handlers_templates.py   # Template handlers
│   ├── broadcast_health.py     # Broadcast & health
│   ├── broadcast.py            # Broadcast logic
│   └── utils.py                # Helper functions
│
├── worker/
│   ├── main.py                 # FastAPI worker
│   ├── webhook_handler.py      # Handle user messages
│   ├── broadcast_engine.py     # Send broadcasts
│   └── health_checker.py       # Health monitoring
│
├── shared/
│   ├── database.py             # MongoDB operations
│   ├── redis_client.py         # Redis operations
│   ├── models.py               # Data models
│   ├── crypto.py               # Encryption
│   └── reply_manager.py        # Reply resolution logic
│
├── docker-compose.yml
├── nginx.conf
└── .env
```

## 🆘 Support

### Common Issues

**Q: How to change global reply?**
A: Just run `/setreply` → "ALL Bots" → Send new message

**Q: Can I have different replies for different bots?**
A: Yes! Use "Select Multiple" or "Single Bot" mode

**Q: Do variables work in broadcasts?**
A: Yes! Variables work in both auto-replies and broadcasts

**Q: How many templates can I create?**
A: Unlimited! Create as many as you need

**Q: Can I update a template?**
A: Delete old template and create new one with same name

## 📄 License

MIT License

## 🙏 Contributing

Pull requests welcome! Please test thoroughly before submitting.

---

**Made with ❤️ for efficient bot management**

**Version:** 2.0
**Last Updated:** 2024