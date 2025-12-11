# Quick Start Guide - UA2-125 AI Chatbot Assistant

Get up and running in 5 minutes!

## Step-by-Step Setup

### 1. Prerequisites Check

Ensure you have:
- Python 3.9+ installed: `python --version`
- OpenAI API key: [Get one here](https://platform.openai.com/api-keys)

### 2. Setup Virtual Environment

**Windows:**
```bash
cd ua2125-chat
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
cd ua2125-chat
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Configure API Key

Create `.env` file in the `backend` directory:

**Windows:**
```bash
copy .env.example .env
```

**macOS/Linux:**
```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=sk-your-actual-openai-api-key-here
```

### 5. Ingest Knowledge Base

```bash
python ingest_docs.py
```

Wait for the embeddings to be created (1-2 minutes).

### 6. Start the Server

```bash
python app.py
```

### 7. Open Your Browser

Navigate to: **http://localhost:8000**

---

## Try These Queries

### Specifications
- "What's the power output at 4 ohms?"
- "What is the frequency response?"
- "What are the physical dimensions?"

### Installation
- "How do I connect a TV using HDMI ARC?"
- "What's the proper speaker wiring for stereo mode?"
- "How do I rack mount the amplifier?"

### Troubleshooting
- "Why is my amplifier going into protection mode?"
- "I have no sound from HDMI ARC, what should I check?"
- "The LED is blinking red, what does that mean?"

### Setup
- "What are the input priority settings?"
- "How do I configure the analog input trim?"
- "Can the UA2-125 play Dolby Digital audio?"

---

## Common Issues

### "Index files not found"
**Fix:** Run `python ingest_docs.py` first

### "OpenAI API Error"
**Fix:** Check your API key in `.env` file

### Port 8000 in use
**Fix:** Edit `backend/config.py` and change `PORT = 8001`

---

## What's Next?

- **Add More Documents:** Place PDFs, TXT, or JSON files in `backend/data/raw/` and re-run `ingest_docs.py`
- **Customize Personality:** Edit `SYSTEM_PROMPT` in `backend/config.py`
- **Deploy to Production:** See [DEPLOYMENT.md](DEPLOYMENT.md)
- **Run Tests:** See [TESTING.md](TESTING.md)

---

## Need Help?

- Check [README.md](README.md) for detailed documentation
- Review logs in terminal for error messages
- Ensure your OpenAI account has credits

---

**Congratulations!** Your UA2-125 AI Assistant is ready to help installers and technicians.
