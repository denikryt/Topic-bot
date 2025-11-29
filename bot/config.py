"""Bot configuration constants."""

# Maximum number of topics that may be rendered in a single message.
MAX_TOPICS_PER_MESSAGE = 10

# User-facing strings. Adjust here to change defaults or provide translations.
DEFAULT_WELCOME_MESSAGE = "Add a welcome message."
CONTRIBUTORS_HEADER = "## Теми додали:"
CONTRIBUTORS_EMPTY_STATE = "(empty at first)"
DEFAULT_CONTRIBUTORS_MESSAGE = f"{CONTRIBUTORS_HEADER}\n{CONTRIBUTORS_EMPTY_STATE}"
TOPICS_INITIALIZING_MESSAGE = "Setting up topics board..."
INIT_ALREADY_EXISTS = "У цьому каналі вже є Topic Board."
INIT_FOLLOWUP_PROMPT = "Topics board initialized. Would you like to set a custom welcome message now?"

WELCOME_MODAL_TITLE = "Edit Welcome Message"
WELCOME_MODAL_LABEL = "Welcome Message"
WELCOME_EDIT_BUTTON_LABEL = "Edit Welcome Message"
ACTION_ONLY_IN_CONFIGURED_SERVER = "This action can only be used inside the configured server."
MANAGE_SERVER_REQUIRED_EDIT_WELCOME = "You need the Manage Server permission to edit the welcome message."
CONFIGURED_CHANNEL_INACCESSIBLE = "Unable to access the configured channel for this server."
WELCOME_MESSAGE_INACCESSIBLE = "Unable to access the welcome message in the configured channel."
WELCOME_MESSAGE_UPDATE_FAILED = "Failed to update the welcome message. Please try again."
WELCOME_MESSAGE_UPDATED = "Welcome message updated."

SERVER_ONLY_COMMAND = "This command can only be used inside a server."
SERVER_NOT_INITIALIZED = "This server is not initialized. Run /init first."
TEXT_CHANNEL_ONLY_COMMAND = "This command must be used in a text channel."
MANAGE_SERVER_REQUIRED_INIT = "You need the Manage Server permission to run this command."
MANAGE_SERVER_REQUIRED_REMOVE_BOARDS = "You need the Manage Server permission to remove the topics board."
NO_WELCOME_MESSAGE_CONFIGURED = "No welcome message is configured. Run /init to set up the board."
REMOVE_BOARDS_CHANNEL_ONLY = "This command can only be used in the topic board channel."

INIT_COMMAND_DESCRIPTION = "Initialize the topics board in this channel."
EDIT_WELCOME_COMMAND_DESCRIPTION = "Edit the welcome message created during initialization."
ADD_TOPIC_COMMAND_DESCRIPTION = "Add a topic for this guild."
REMOVE_TOPIC_COMMAND_DESCRIPTION = "Remove one of your topics or any if you are an admin."
REMOVE_BOARDS_COMMAND_DESCRIPTION = "Remove all topic board messages and data for this guild."
TOPICS_HELP_COMMAND_DESCRIPTION = "Show a quick guide to all topic commands."

EMOJI_ALREADY_USED = "This emoji is already in use in this guild. Choose another one."
SINGLE_EMOJI_REQUIRED = "Please enter exactly one emoji."
TOPIC_ADDED = "Topic added!"
TOPIC_NOT_FOUND = "Topic not found."
TOPIC_REMOVAL_NOT_ALLOWED = "You can only remove topics you created."
TOPIC_REMOVED = "Topic removed."
NOTIFICATION_TEMPLATE = "🔔 {user} додав нову тему — {emoji} **{text}**!"
REMOVE_BOARDS_SUCCESS = "Topic board removed. Run /init again to start fresh."
TOPICS_HELP_MESSAGE = (
    "Доступні команди:\n"
    "• **/addtopic** — додати тему (емодзі та текст)\n"
    "• **/removetopic** — видалити одну зі своїх тем (з автозаповненням)\n"
    "• **/editwelcomemessage** — редагувати привітальне повідомлення (відкриває модальне вікно)\n"
    "• **/removeboards** — лише для адміністраторів, видаляє всі дошки тем і скидає все\n"
    "• **/topicshelp** — справка по командам"
)

TOPIC_ENTRY_TEMPLATE = "> - {emoji} — **{text}**"
TOPICS_EMPTY_MESSAGE = "No topics yet. Add one with /addtopic."

MISSING_TOKEN_MESSAGE = "DISCORD_TOKEN environment variable is not set."
