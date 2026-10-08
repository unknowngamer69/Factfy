# Factfy

Factfy is a Discord bot that checks factual claims.

You can use it in a few different ways:

- `/factcheck <claim>`
- Mention the bot with a claim
- Right-click a message and use the fact-check option
- Enable passive tracking for a channel
- Send an image or screenshot containing a claim
- Reply to a message with something like `is this true?`

Factfy tries to find useful sources before giving a verdict. It does not rely on an AI model alone.

The result can be:

- True
- False
- Misleading
- Unverifiable

## How Factfy checks a claim

Factfy uses a three-step checking process.

### Tier 1: Google Fact Check

Factfy first checks Google's Fact Check database.

This can provide:

- Existing fact-check articles
- The claim that was checked
- The published verdict
- The explanation
- The source URL

If a suitable fact-check is found, Factfy can use that information instead of doing a more expensive search.

### Tier 2: Wikidata and Wikipedia

If Tier 1 does not have a useful result, Factfy looks for structured information and related pages.

Wikidata is useful for things such as:

- Dates
- Places
- People
- Populations
- Countries
- Basic relationships between entities

Wikipedia is also used to find related pages and supporting information.

The information found here is passed to the AI, which uses it as evidence when producing the final verdict.

### Tier 3: Web Search

If the first two tiers cannot provide enough information, Factfy uses web search.

Search results are passed to the AI as evidence.

The AI is instructed to make its answer from the supplied evidence instead of simply guessing from its own knowledge.

## Image checking

Factfy can check claims inside images.

For example, if someone uploads a screenshot containing:

```text
The Eiffel Tower was built in 1982.
```

Factfy uses OCR to read the text from the image and then checks the extracted claim.

Tesseract OCR is used for this.

If the image is too blurry or the OCR confidence is too low, Factfy avoids treating the extracted text as reliable.

Factfy also supports follow-up messages.

For example:

1. A user sends an image containing a claim.
2. The user sends `@Factfy is this true?`

Factfy can use the previous message as the claim instead of trying to fact-check only the words `is this true?`.

Replies to messages are also supported.

## Requirements

Factfy currently uses:

- Python 3.13
- Tesseract OCR
- SQLite
- SQLAlchemy
- Alembic
- spaCy
- scikit-learn
- discord.py
- Pillow
- httpx
- SPARQLWrapper
- Pydantic
- Pydantic Settings

You also need:

- A Discord bot application
- A Discord bot token
- A Discord Application ID
- Google Fact Check API access
- Hack Club Search API access
- Hack Club AI API access

Python 3.13 is recommended for the current version of Factfy.

Do not use Python 3.14 with the current dependency versions unless you have updated and tested the dependencies.

## Discord bot setup

Before installing Factfy, create a Discord application.

Open the Discord Developer Portal and create a new application.

Create a bot for the application.

You will need:

- Bot Token
- Application ID

The bot token must be kept private.

Never commit your `.env` file to GitHub.

### Message Content Intent

Factfy needs Discord's Message Content Intent.

In the Discord Developer Portal:

1. Open your application.
2. Open the Bot section.
3. Find Privileged Gateway Intents.
4. Enable Message Content Intent.
5. Save the changes.

Without this intent, Factfy may not be able to read normal message text correctly.

### Bot permissions

When inviting Factfy to a server, the bot needs permissions that allow it to:

- View channels
- Read message history
- Send messages
- Add reactions
- Use application commands
- Embed links

Factfy also needs access to the channels where passive tracking is enabled.

For message replies and recent-message context, the bot must be able to read message history.

## API keys

Factfy uses several external services.

The `.env` file contains the following values:

- `Bot_Token`
- `App_ID`
- `Factchecker`
- `Search`
- `HCAI`

Their purpose is:

### Bot_Token

Your Discord bot token.

### App_ID

Your Discord Application ID.

### Factchecker

Google Fact Check API key.

### Search

Hack Club Search API key.

### HCAI

Hack Club AI API key.

Keep all of these values private.

Do not put real keys directly into source code.

## Configuration

Factfy includes an `.env.example` file.

Copy it to `.env`.

The file looks like this:

```env
# Discord
Bot_Token=your-bot-token-here
App_ID=your-application-id-here

# Database
Database_URL=sqlite+aiosqlite:///./data/factcheckbot.db

# External APIs
Factchecker=your-google-api-key-here
Search=your-hackclub-search-key-here
HCAI=your-hackclub-ai-api-key-here

# Cascade tuning
Claim_Dectection_Threshold=0.65
Teir1_Threshold=0.6
Teir3_Limit=20
OCR_Threshold=60
Cache_Expiry=7

# Misc
Log_lvl=INFO
```

Replace the placeholder values with your actual credentials.

The SQLite database is stored at:

```text
data/factcheckbot.db
```

The `data` directory must exist before running the database migration when installing manually.

## Configuration options

### Database_URL

The database connection string.

The default is:

```env
Database_URL=sqlite+aiosqlite:///./data/factcheckbot.db
```

This uses SQLite.

### Claim_Dectection_Threshold

Controls how confident the claim classifier must be before treating a message as a factual claim.

Default:

```env
Claim_Dectection_Threshold=0.65
```

### Teir1_Threshold

Controls the matching threshold used for Tier 1 fact-check results.

Default:

```env
Teir1_Threshold=0.6
```

### Teir3_Limit

Controls the daily Tier 3 AI usage limit.

Default:

```env
Teir3_Limit=20
```

### OCR_Threshold

Controls the minimum OCR confidence accepted by the image text extraction system.

Default:

```env
OCR_Threshold=60
```

### Cache_Expiry

Controls how long cached results remain valid.

Default:

```env
Cache_Expiry=7
```

### Log_lvl

Controls the logging level.

Default:

```env
Log_lvl=INFO
```
# Docker installation

Docker can be used instead of installing Python and Tesseract directly on the host.

The included Docker setup installs the required Python version, Tesseract, Python packages, spaCy model, and the Factfy application inside the container.

## Docker requirements

Install:

- Docker
- Docker Compose

Check the installation:

```bash
docker --version
docker compose version
```

Modern Docker installations normally provide Compose through the `docker compose` command.

## 1. Clone the repository

```bash
git clone https://github.com/unknowngamer69/Factfy.git
cd Factfy
```

## 2. Create the environment file

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Open `.env` and add your real credentials.

## 3. Build and start Factfy

```bash
docker compose up -d --build
```

The first build can take some time because Docker needs to install the Python dependencies and download the spaCy model.

## 4. Check the container

```bash
docker compose ps
```

The Factfy container should show as running.

## 5. View logs

```bash
docker compose logs -f factfy
```

Press `Ctrl+C` to stop viewing the logs.

This does not stop the container.

## 6. View the last 100 lines

```bash
docker compose logs --tail 100 factfy
```

## 7. Restart Factfy

```bash
docker compose restart factfy
```

## 8. Stop Factfy

```bash
docker compose stop
```

## 9. Start it again

```bash
docker compose start
```

## 10. Stop and remove the container

```bash
docker compose down
```

The database remains in the local `data` directory because Docker Compose mounts it into the container.

## Updating a Docker installation

After new code has been pushed:

```bash
cd Factfy
git pull origin main
docker compose up -d --build
```

If you need to completely rebuild the image without using Docker's build cache:

```bash
docker compose build --no-cache
docker compose up -d
```

# Manual installation

Factfy can be installed directly on Windows, Linux, or macOS.

Manual installation gives you direct access to the Python environment and is useful when you are developing or debugging the bot.

---

# Windows installation

## 1. Install Python

Install Python 3.13.

Check that it is installed:

```powershell
python --version
```

It should show something similar to:

```text
Python 3.13.x
```

If `python` does not work, try:

```powershell
py --version
```

Make sure Python is added to PATH during installation.

Do not use Python 3.14 with the current dependency versions unless you have updated and tested the dependencies.

## 2. Install Tesseract OCR

Factfy uses Tesseract for OCR.

Install a Windows build of Tesseract.

After installing it, make sure the Tesseract executable is available in PATH.

The executable is normally installed somewhere similar to:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

Open a new PowerShell window and test it:

```powershell
tesseract --version
```

If Windows says that `tesseract` is not recognized, add the Tesseract installation directory to your PATH.

After changing PATH, open a new terminal and run:

```powershell
tesseract --version
```

again.

## 3. Clone the repository

```powershell
git clone https://github.com/unknowngamer69/Factfy.git
cd Factfy
```

## 4. Create a virtual environment

```powershell
python -m venv .venv
```

## 5. Activate the virtual environment

PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate the environment again:

```powershell
.venv\Scripts\Activate.ps1
```

## 6. Upgrade pip

```powershell
python -m pip install --upgrade pip setuptools wheel
```

## 7. Install Python dependencies

```powershell
pip install -r requirements.txt
```

## 8. Install the spaCy model

```powershell
python -m spacy download en_core_web_sm
```

## 9. Create the environment file

```powershell
Copy-Item .env.example .env
```

Open it:

```powershell
notepad .env
```

Add your real Discord and API credentials.

Do not commit this file.

## 10. Create the database directory

```powershell
New-Item -ItemType Directory -Force data
```

## 11. Train the local claim classifier

```powershell
python -m bot.detection.train_classifier
```

This creates the local classifier model used by Factfy.

## 12. Run the database migration

```powershell
python -m alembic upgrade head
```

## 13. Start Factfy

```powershell
python -m bot.main
```

If everything is configured correctly, the bot should connect to Discord.

To stop it:

```text
Ctrl+C
```

---

# Linux installation

The following commands are suitable for common Debian and Ubuntu based systems.

## 1. Update packages

```bash
sudo apt update
```

## 2. Install Python and Tesseract

If Python 3.13 is available from your distribution:

```bash
sudo apt install -y python3.13 python3.13-venv python3.13-dev tesseract-ocr
```

Check Python:

```bash
python3.13 --version
```

Check Tesseract:

```bash
tesseract --version
```

If your Linux distribution does not provide Python 3.13 using these package names, install Python 3.13 using the normal method recommended by your distribution.

## 3. Clone the repository

```bash
git clone https://github.com/unknowngamer69/Factfy.git
cd Factfy
```

## 4. Create the virtual environment

```bash
python3.13 -m venv .venv
```

## 5. Activate the virtual environment

```bash
source .venv/bin/activate
```

## 6. Upgrade pip

```bash
python -m pip install --upgrade pip setuptools wheel
```

## 7. Install Python dependencies

```bash
pip install -r requirements.txt
```

## 8. Install the spaCy model

```bash
python -m spacy download en_core_web_sm
```

## 9. Create the environment file

```bash
cp .env.example .env
```

Edit it:

```bash
nano .env
```

Add your actual:

```text
Bot_Token
App_ID
Factchecker
Search
HCAI
```

Save the file.

## 10. Create the database directory

```bash
mkdir -p data
```

## 11. Train the claim classifier

```bash
python -m bot.detection.train_classifier
```

## 12. Run the database migration

```bash
python -m alembic upgrade head
```

## 13. Start Factfy

```bash
python -m bot.main
```

To stop it:

```text
Ctrl+C
```

---

# macOS installation

## 1. Install Python 3.13

Install Python 3.13.

Check:

```bash
python3.13 --version
```

It should show:

```text
Python 3.13.x
```

## 2. Install Tesseract

If you use Homebrew:

```bash
brew install tesseract
```

Check:

```bash
tesseract --version
```

## 3. Clone Factfy

```bash
git clone https://github.com/unknowngamer69/Factfy.git
cd Factfy
```

## 4. Create the virtual environment

```bash
python3.13 -m venv .venv
```

## 5. Activate the virtual environment

```bash
source .venv/bin/activate
```

## 6. Upgrade pip

```bash
python -m pip install --upgrade pip setuptools wheel
```

## 7. Install dependencies

```bash
pip install -r requirements.txt
```

## 8. Install the spaCy model

```bash
python -m spacy download en_core_web_sm
```

## 9. Create the environment file

```bash
cp .env.example .env
```

Edit it:

```bash
nano .env
```

Add your actual credentials.

## 10. Create the database directory

```bash
mkdir -p data
```

## 11. Train the classifier

```bash
python -m bot.detection.train_classifier
```

## 12. Run the database migration

```bash
python -m alembic upgrade head
```

## 13. Start the bot

```bash
python -m bot.main
```

Stop it with:

```text
Ctrl+C
```


# Database

Factfy uses SQLite by default.

The database is stored at:

```text
data/factcheckbot.db
```

The database is managed with Alembic.

After installing Factfy manually, create the data directory and run:

```bash
mkdir -p data
python -m alembic upgrade head
```

On Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force data
python -m alembic upgrade head
```

Do not delete the database unless you intentionally want to start with a new database.

# Claim classifier

Factfy has a local machine-learning classifier that helps decide whether a message looks like a factual claim.

After installing the dependencies, run:

```bash
python -m bot.detection.train_classifier
```

This creates the local classifier model.

You normally only need to train it when setting up Factfy or when the classifier training data or code has changed.

You do not need to train it every time the bot starts.

# Using Factfy

## Slash command

Use:

```text
/factcheck the sky is actually green
```

Factfy will check the claim and return a result.

## Mention the bot

You can also write:

```text
@Factfy the sky is green
```

Factfy will treat the message as a fact-check request.

## Image fact-checking

Upload an image containing a claim and ask Factfy to check it.

For example, an image could contain:

```text
The Eiffel Tower was built in 1982.
```

Factfy uses OCR to extract the text before checking it.

## Follow-up question

You can send a claim and then ask:

```text
is this true?
```

Factfy can use the recent message as context for generic fact-checking questions.

For example:

```text
The Eiffel Tower was built in 1982.

@Factfy is this true?
```

Factfy can combine the previous claim with the follow-up request.

## Reply to a message

You can reply directly to a message and write:

```text
@Factfy is this true?
```

Factfy can use the message being replied to as the claim.

This also works when the referenced message contains an image.

## Context menu

Right-click a message and choose the Factfy fact-check option.

This is useful when you want to check a message without copying the text.

# Passive channel tracking

Factfy can monitor selected channels for possible factual claims.

For example:

```text
/track-channel add #channel
```

When passive tracking is enabled, Factfy can react to messages that look like factual claims.

A user can then trigger a fact-check from the reaction.

This avoids automatically running a full fact-check for every message.

# Caching

Factfy stores previous results in the database.

If the same claim is checked again, Factfy can use cached information instead of repeating the entire checking process.

This helps reduce:

- API usage
- AI usage
- Search requests
- Response time

The cache is stored in the SQLite database by default.

# AI usage

Factfy does not send every message directly to the AI.

The cascade is designed to find useful information first.

The AI is mainly used to interpret the evidence and produce the final response.

The default Tier 3 limit is:

```env
Teir3_Limit=20
```


# Current limitations

Factfy is still a work in progress.

The claim classifier is trained using a local training dataset, so it will not perfectly understand every type of message.

OCR also depends on image quality. Screenshots with very small, blurry, rotated, or unusual text may not be read correctly.

The default database is SQLite. This is simple and works well for a small deployment, but a larger deployment may benefit from PostgreSQL.

The quality of the final fact-check also depends on the quality and availability of the external sources.
