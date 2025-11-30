# **Topic-Bot**

Topic-Bot is a lightweight Discord bot that turns a dedicated channel into a clean, structured topic board.
Users can add topics, react to the ones they care about, and instantly see activity updates — all while the bot keeps the channel tidy and organized.

---

## **✨ What This Bot Does**

### **• Creates a structured topic board inside a single channel**

After initialization, the channel becomes a fully managed space:

* No random messages — anything that isn’t a command gets deleted.
* Only system messages created by the bot remain:

  1. **Welcome Message**
  2. **Topic Board Header**
  3. **Topic Board(s)**
  4. **Contributors List**
  5. **Notification Message**

Everything stays in a strict, predictable order.

---

## **📝 Adding Topics**

Users add new topics with:

```
/addtopic emoji text
```

The bot:

* inserts the topic into the board,
* ensures the emoji is unique,
* adds the matching reaction under the board message,
* updates the contributor list,
* sends a fresh notification message.

Each board message has a topic limit (configurable).
Once it’s full, the bot automatically creates the next board.

---

## **❌ Removing Topics**

```
/removetopic
```

Features:

* Autocomplete (users see only their own topics, admins see all)
* Reaction cleanup
* Contributor list auto-update
* Board restructuring when needed

---

## **👋 Welcome Message (Modal Editing)**

The welcome message can be edited through a Discord modal:

```
/editwelcomemessage
```

Multiline text, markdown, emojis — everything is preserved.

---

## **🙌 Contributors (Silent Mentions)**

The bot maintains a single-line list of everyone who has added at least one topic.
Mentions are sent **without pinging anyone**, so users don’t get spammed when the board updates.

---

## **🔔 Notifications**

Whenever someone adds a topic:

* the previous notification message is deleted,
* a new one appears at the bottom of the board.

This makes activity on the board instantly visible.

---

## **🧹 Full Reset**

Admins can reset the entire board:

```
/removeboards
```

This deletes:

* the welcome message,
* the topic board header,
* all board messages,
* contributors list,
* notification message,
* all JSON data.

The channel becomes clean again.

---

## **🔒 Guild Whitelist**

For safety and control, the bot only works in guilds explicitly listed in the environment variables.
This prevents unwanted invites and keeps resource use predictable.

---

## **🛠 Easy Customization**

All user-facing text (messages, labels, prompts, errors) is stored in `config.py`.
You can easily:

* change phrasing,
* localize the bot,
* adjust style and structure.

---

## **📦 Commands Overview**

* `/init` — set up the board
* `/addtopic` — add a new topic
* `/removetopic` — remove a topic
* `/editwelcomemessage` — edit the welcome message
* `/topicshelp` — show help
* `/removeboards` — full reset

---

## **⚙️ Setup**

To run the bot locally:

1. **Create a `.env` file** with two required fields:

   ```
   DISCORD_TOKEN=YOUR_BOT_TOKEN
   ALLOWED_GUILDS=123456789012345678,987654321012345678
   ```

   * `ALLOWED_GUILDS` must contain **comma-separated guild IDs** where the bot is allowed to operate.

2. (Optional, recommended) Create a virtual environment and install dependencies:

   ```
   pip install -r requirements.txt
   ```

That's it — run the bot and it will work only in the guilds you’ve listed.
