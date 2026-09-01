import json
import uuid
from datetime import datetime
from pathlib import Path

import os
from dotenv import load_dotenv
from google import genai


from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ==========================================================
# Load Environment
# ==========================================================

load_dotenv()

# ==========================================================
# FastAPI App
# ==========================================================

app = FastAPI()

# ==========================================================
# Chat Storage
# ==========================================================

CHAT_FOLDER = Path("chats")
CHAT_FOLDER.mkdir(exist_ok=True)

# ==========================================================
# Gemini Client
# ==========================================================

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

# ==========================================================
# Static Files
# ==========================================================

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# ==========================================================
# Conversation Memory
# ==========================================================

conversation_history = []

current_chat_id = str(uuid.uuid4())

MAX_HISTORY = 12

# ==========================================================
# System Prompt
# ==========================================================

SYSTEM_PROMPT = """
You are Ayan AI.

You are a professional AI assistant similar to ChatGPT.

Your personality:

- Friendly
- Intelligent
- Professional
- Honest
- Helpful

Rules:

- Never reveal your thinking process.
- Never reveal internal reasoning.
- Never output "Thinking Process", "Analysis", "Reasoning", or similar.
- Only provide the final answer.
- Use Markdown when appropriate.
- If writing code, use proper Markdown code blocks.
- Never invent facts.
- If unsure, say you don't know.
- Don't repeatedly greet the user.
- Only introduce yourself if the user asks who you are.
- Answer naturally like ChatGPT.
"""

# ==========================================================
# Home
# ==========================================================
# ==========================================================
# Helper Functions
# ==========================================================

def build_prompt():

    prompt = SYSTEM_PROMPT.strip()
    prompt += "\n\nConversation:\n\n"

    for msg in conversation_history:

        if msg["role"] == "user":
            prompt += f"User: {msg['content']}\n"

        else:
            prompt += f"Assistant: {msg['content']}\n"

    prompt += "\nAssistant:"

    return prompt


def clean_response(text: str) -> str:

    if not text:
        return "Sorry, I couldn't generate a response."

    blocked = [
        "Thinking Process",
        "Reasoning",
        "Analysis",
        "Internal Notes",
        "Thought Process",
    ]

    lines = text.splitlines()

    cleaned = []

    for line in lines:

        if any(word.lower() in line.lower() for word in blocked):
            continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()
  
# ==========================================================
# Gemini Streaming Generator
# ==========================================================

def stream_gemini(prompt):

    full_reply = ""

    stream = client.models.generate_content_stream(
        model="gemini-flash-lite-latest",
        contents=prompt
    )

    for chunk in stream:

        text = getattr(chunk, "text", "")

        if text:

            full_reply += text

            yield text

    global conversation_history

    conversation_history.append(
        {
            "role": "assistant",
            "content": full_reply
        }
    )

    conversation_history[:] = conversation_history[-MAX_HISTORY:]

    save_chat()


# ==========================================================
# Home
# ==========================================================

@app.get("/")
def home(request: Request):
    ...
 # ==========================================================
# Generate Chat Title
# ==========================================================

def generate_chat_title(message):

    title = message.strip()

    if len(title) > 40:
        title = title[:40] + "..."

    return title

# ==========================================================
# Save Chat
# ==========================================================

def save_chat():

    global current_chat_id
    global conversation_history

    filepath = CHAT_FOLDER / f"{current_chat_id}.json"

    # Default title
    title = "New Chat"

    # If there is at least one user message,
    # use it as the chat title
    for message in conversation_history:

        if message["role"] == "user":

            title = generate_chat_title(message["content"])

            break

    chat_data = {
        "id": current_chat_id,
        "title": title,
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "messages": conversation_history
    }

    with open(filepath, "w", encoding="utf-8") as f:

        json.dump(
            chat_data,
            f,
            indent=4,
            ensure_ascii=False
        )

# ==========================================================
# Load Chat
# ==========================================================

def load_chat(chat_id):

    global current_chat_id
    global conversation_history

    filepath = CHAT_FOLDER / f"{chat_id}.json"

    if not filepath.exists():
        return False

    with open(filepath, "r", encoding="utf-8") as f:

        data = json.load(f)

    conversation_history = data.get("messages", [])

    current_chat_id = chat_id

    return True

    # ==========================================================
# Create Chat
# ==========================================================

def create_chat():

    global current_chat_id
    global conversation_history

    current_chat_id = str(uuid.uuid4())

    conversation_history = []

    save_chat()

    return current_chat_id


# ==========================================================
# Persistent Memory
# ==========================================================

MEMORY_FILE = "memory.json"


def load_memory():

    try:

        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except:

        return {}


def save_memory(memory):

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:

        json.dump(
            memory,
            f,
            indent=4,
            ensure_ascii=False
        )
        

@app.get("/", response_class=HTMLResponse)
def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request
        }
    )

# ==========================================================
# New Chat
# ==========================================================

@app.post("/new_chat")
async def new_chat():

    global conversation_history
    global current_chat_id

    # Create a brand-new chat ID
    current_chat_id = str(uuid.uuid4())

    # Clear conversation
    conversation_history = []

    # Create an empty chat file
    save_chat()

    return JSONResponse(
        {
            "status": "success",
            "chat_id": current_chat_id
        }
    )

    # ==========================================================
# List Chats
# ==========================================================

@app.get("/chats")
async def get_chats():

    chats = []

    for file in CHAT_FOLDER.glob("*.json"):

        try:

            with open(file, "r", encoding="utf-8") as f:

                data = json.load(f)

            chats.append(
                {
                    "id": data.get("id"),
                    "title": data.get("title", "New Chat"),
                    "updated": data.get("updated", "")
                }
            )

        except Exception:
            pass

    chats.sort(
        key=lambda x: x["updated"],
        reverse=True
    )

    return JSONResponse(chats)
    # ==========================================================
# Open Existing Chat
# ==========================================================

@app.get("/chat/{chat_id}")
async def open_chat(chat_id: str):

    if load_chat(chat_id):

        return JSONResponse(
            {
                "success": True,
                "messages": conversation_history
            }
        )

    return JSONResponse(
        {
            "success": False
        },
        status_code=404
    )
# ==========================================================
# Delete Chat
# ==========================================================

@app.delete("/chat/{chat_id}")
async def delete_chat(chat_id: str):

    filepath = CHAT_FOLDER / f"{chat_id}.json"

    if not filepath.exists():

        return JSONResponse(
            {
                "success": False
            },
            status_code=404
        )

    os.remove(filepath)

    return JSONResponse(
        {
            "success": True
        }
    )
    # ==========================================================
# Streaming Test
# ==========================================================

@app.get("/stream-test")
async def stream_test():

    def generate():

        stream = client.models.generate_content_stream(
            model="gemini-flash-lite-latest",
            contents="Write a short paragraph about artificial intelligence."
        )

        for chunk in stream:

            if chunk.text:

                yield chunk.text

    return StreamingResponse(generate(), media_type="text/plain")
    # ==========================================================
# Chat
# ==========================================================

@app.post("/chat")
async def chat(request: Request):

    global conversation_history

    try:

        data = await request.json()
        user_message = data.get("message", "").strip()

        if not user_message:

            return JSONResponse(
                {
                    "reply": "Please enter a message."
                },
                status_code=400
            )

        print("=" * 70)
        print("USER :", user_message)

        # ----------------------------------------
        # Save User Message
        # ----------------------------------------

        conversation_history.append(
            {
                "role": "user",
                "content": user_message
            }
        )
        save_chat()

        conversation_history = conversation_history[-MAX_HISTORY:]

        save_chat()

        # ----------------------------------------
        # Build Prompt
        # ----------------------------------------

        prompt = SYSTEM_PROMPT
        prompt += "\n\nConversation:\n\n"

        for msg in conversation_history:

            if msg["role"] == "user":

                prompt += f"User: {msg['content']}\n"

            else:

                prompt += f"Assistant: {msg['content']}\n"

        prompt += "\nAssistant:"


    # ----------------------------------------
    # Gemini Request
    # ----------------------------------------


    response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt
    )

    reply = ""

    if hasattr(response, "text") and response.text:

        reply = response.text.strip()

    else:

        reply = "Sorry, I couldn't generate a response."
        # ----------------------------------------
        # Remove unwanted reasoning if it appears
        # ----------------------------------------

        blocked_words = [
            "Thinking Process",
            "Reasoning",
            "Analysis",
            "Internal Notes",
            "Thought Process",
        ]

        for word in blocked_words:

            if word.lower() in reply.lower():

                lines = reply.splitlines()

                filtered = []

                for line in lines:

                    if all(b.lower() not in line.lower() for b in blocked_words):

                        filtered.append(line)

                reply = "\n".join(filtered).strip()

        # ----------------------------------------
        # Save Assistant Reply
        # ----------------------------------------

        conversation_history.append(
            {
                "role": "assistant",
                "content": reply
            }
        )
        save_chat()

        conversation_history = conversation_history[-MAX_HISTORY:]

        print("AI :", reply)
        print("=" * 70)

        return JSONResponse(
            {
                "reply": reply
            }
        )

    except Exception as e:

        print("=" * 70)
        print("ERROR :", e)
        print("=" * 70)

        return JSONResponse(
            {
                "reply": "Sorry, something went wrong while contacting Gemini."
            },
            status_code=500
        )