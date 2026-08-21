# Fact-Check Bot 🔍

Ever been in a channel when someone drops a totally wild claim—like *"the Great Wall of China is visible from space"*—and nobody wants to kill the vibe by actually Googling it? well this is its solution 

This Discord bot does that boring things for you. It watches for questionable factual claims, flags them with 🔍 reaction, and waits. If anyone clicks it, the bot runs a full background check and returns a clean embed: **True**, **False**, **Misleading**, or **Unverifiable**.

Also, if you *want* to use commands, you can. Drop `/factcheck <text>`, right-click a message to check it, or just @mention the bot mid-conversation. Example: `@Factfy the Eiffel Tower was built by aliens`. It does the same background checks with that too.

---

## How It Works (The 3-Tier Cascade)

Calling an LLM cold on a random claim or google searches won't give anything meaningful as AI is trained on old datasets and also current big AI Modls is not that cheap. So, I built a three-tier cascade. It fetches the cheapest, most reliable data first, and only moves to the next tier if it fails. At the end of whichever tier succeeds, the data gets pushed to **Hack Club AI (Gemini 2.5 Flash)** to tell the final verdict.

### Tier 1: Google Fact Check Tools (Free & Human-Verified)
We hit Google's Fact Check Tool's database first,which have actual articles written and verified by journalists. If the text similarity matches your claim, we pull the verdict, the explanation, and the URL. Gemini formats and check it.

### Tier 2: Wikidata + Wikipedia (Free & Structured)
If Google's Fact Tool fails, we run SPARQL queries against Wikidata. This is perfect for hard numbers: birth dates, capital cities, populations, etc. We also run a Wikipedia fallback. If we find solid structured data, Gemini takes it and give response as per it.

### Tier 3: Web Search + AI Synthesis (The Last Resort)
If Tiers 1 and 2 come up empty, we then use realtime web search. The bot uses the Hack Club AI EXA Search API to scrape top web snippets. Gemini is strictly prompted to synthesize an answer *only* from these snippets.

---

## Core Features

*   **Zero-Friction Flagging:** Tracked channels get passive 🔍 reactions.
*   **Image Support:** If user uploads as screenshot or image, the bot runs Tesseract OCR to extract the text and do the rest thing as said above. (If it's too blurry, it will tell you instead of guessing).
*   **Built-in Caching:** For checking the exact same claim again, it uses the cache data of claims in the unified database of bot that has claims and result from all channels and servers. This reduces AI Usage.
*   **Setup daily AI limits:** Set a daily limit for AI (default is 20 AI calls). If a server hits the limit, the bot tells them to try again tomorrow.
*   **Source Transparency:** Every single verdict tells you exactly where it came from so you know whether to trust it.

---

## Getting Started

### Prerequisites
You need Python 3.11 and Tesseract OCR system binary.
*   **Ubuntu/Debian:** `sudo apt install tesseract-ocr`
*   **macOS:** `brew install tesseract`
*   **Windows:** Download and Install the installer from [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki).

### Quick Setup

```bash
# Clone the repo and start a venv.
python -m venv .venv
source .venv/bin/activate        
# Windows users: 
.venv\Scripts\activate

# Install the requirements and dependencies:
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Prepare your config
cp .env.example .env
```

Open that `.env` file and write in your keys (`Bot_Token`, `App_ID`, `Factchecker`, `Search`, `HCAI`).

```bash
# Train the local ML claim classifier 
python -m bot.detection.train_classifier

# Start the SQLite tables
alembic upgrade head

# Run the Bot
python -m bot.main
```

### Discord Dev Portal Stuff
1. Create your app on the [Discord Developer Portal](https://discord.com/developers/applications).
2. **Crucial step:** Enable **Message Content Intent** under the Privileged Gateway Intents tab.
3. Get your Bot token and Application ID for the `.env` file. 
(Note: App ID = Application ID and Token = Bot Token)
4. Generate an OAuth2 URL with the `bot` and `applications.commands` scopes to invite it to your server.

---

## Commands

| Action | How to do it |
| :--- | :--- |
| **Manual Check** | `/factcheck the sky is actually green` |
| **Mid-Chat Check** | `@Factfy the sky is green` |
| **Target a Message** | Right-click message → Apps → Fact-check this |
| **Toggle Passive Tracking** | `/track-channel add #channel` (Requires Admin) |

---

## What Needs Work (v1 Limitations)

Let's be real, it's a v1. Here is what you should know:
*   **Ephemeral Storage:** Using SQLite means if you host this on a free Render instance that wipes disk on restart, your cache dies with it. You can swutch to Postgresql for better performance .
*   **Classifier Quirks:** The ML model is trained on a small, hand-labeled dataset. It's going to miss some obvious claims and probably flag a few random opinions. It gets better as we feed it more data.
*   **Tesseract is a pain:** Because it relies on a system-level binary, if your OS path isn't set up right, `pytesseract` will fail silently on import and break later. Double-check your install!

---

## Why Not Just Ask ChatGPT?

Because raw LLMs hallucinate when they don't have context. 

By gating the AI behind a strict cascade of Google Fact Checks, Wikidata, and scraped snippets, we are forcing the model to act as a *synthesizer* rather than a *guesser*. Better data in equals a wildly better verdict out. Plus, nobody wants to tab out of Discord to go argue with a chatbot.