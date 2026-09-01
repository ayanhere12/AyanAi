import os
import json
import uuid
import requests
from pathlib import Path
from datetime import datetime
import copy
import time
from dotenv import load_dotenv
from google import genai
from groq import Groq
from openai import OpenAI
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ==========================================================
# Load Environment
# ==========================================================

load_dotenv()

openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

groq_client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# ==========================================================
# FastAPI App
# ==========================================================

app = FastAPI(
    title="Ayan AI",
    version="2.0",
)
app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)
# ==========================================================
# Static Files
# ==========================================================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)

templates = Jinja2Templates(directory="templates")

# ==========================================================
# Gemini Client
# ==========================================================

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY not found in .env")

client = genai.Client(api_key=API_KEY)

MODEL_NAME = "gemini-flash-lite-latest"
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

openrouter_client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"
    }
)
# ==========================================================
# Project Folders
# ==========================================================

BASE_DIR = Path(__file__).parent
COMFYUI_URL = "http://127.0.0.1:8188"
COMFYUI_WORKFLOW = BASE_DIR / "ayan_image_workflow.json"

def load_comfyui_workflow():
    workflow_file = Path(__file__).parent / "ayan_image_workflow.json"

    with open(workflow_file, "r", encoding="utf-8") as f:
        return json.load(f)

CHAT_FOLDER = BASE_DIR / "chats"
CHAT_FOLDER.mkdir(exist_ok=True)

MEMORY_FILE = BASE_DIR / "memory.json"

if not MEMORY_FILE.exists():
    MEMORY_FILE.write_text("{}", encoding="utf-8")

def queue_comfyui_workflow(prompt):
    workflow = load_comfyui_workflow()

    # Node 2 = positive prompt
    workflow["2"]["inputs"]["text"] = prompt

    response = requests.post(
        f"{COMFYUI_URL}/prompt",
        json={
            "prompt": workflow
        },
        timeout=30
    )

    response.raise_for_status()

    return response.json()

def get_comfyui_history(prompt_id):
    response = requests.get(
        f"{COMFYUI_URL}/history/{prompt_id}",
        timeout=30
    )

    response.raise_for_status()

    return response.json()

def get_comfyui_image_info(prompt_id):
    history = get_comfyui_history(prompt_id)

    if prompt_id not in history:
        return None

    outputs = history[prompt_id].get("outputs", {})

    # Node 6 = Save Image
    node_output = outputs.get("6")

    if not node_output:
        return None

    images = node_output.get("images", [])

    if not images:
        return None

    image = images[0]

    return {
        "filename": image.get("filename"),
        "subfolder": image.get("subfolder", ""),
        "type": image.get("type", "output")
    }

def wait_for_comfyui_image(prompt_id, timeout=600):
    start_time = time.time()

    while time.time() - start_time < timeout:
        image_info = get_comfyui_image_info(prompt_id)

        if image_info:
            return image_info

        time.sleep(2)

    raise TimeoutError("ComfyUI image generation timed out.")
# ==========================================================
# Runtime Variables
# ==========================================================

conversation_history = []

current_chat_id = None

MAX_HISTORY = 1000000

# ==========================================================
# System Prompt
# ==========================================================

SYSTEM_PROMPT = """
You are Ayan AI.

You are a professional AI assistant similar to ChatGPT.

Rules:

- Be intelligent.
- Be friendly.
- Be concise.
- Never reveal hidden reasoning.
- Never output internal thoughts.
- Never invent facts.
- Use Markdown.
- Use proper code blocks.
- If unsure, say you don't know.
"""

# ==========================================================
# Helper Functions
# ==========================================================

def create_chat():

    global current_chat_id
    global conversation_history

    current_chat_id = str(uuid.uuid4())

    conversation_history = []

    return current_chat_id


def ensure_chat():

    global current_chat_id

    if current_chat_id is None:
        create_chat()


def current_time():

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # ==========================================================
# Memory Functions
# ==========================================================

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


# ==========================================================
# Chat Title
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

    ensure_chat()

    title = "New Chat"

    for msg in conversation_history:

        if msg["role"] == "user":

            title = generate_chat_title(msg["content"])

            break

    data = {

        "id": current_chat_id,

        "title": title,

        "updated": current_time(),

        "messages": conversation_history

    }

    filepath = CHAT_FOLDER / f"{current_chat_id}.json"

    with open(filepath, "w", encoding="utf-8") as f:

        json.dump(
            data,
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

    current_chat_id = chat_id

    conversation_history = data.get("messages", [])

    return True


# ==========================================================
# Delete Chat
# ==========================================================

def delete_chat_file(chat_id):

    filepath = CHAT_FOLDER / f"{chat_id}.json"

    if filepath.exists():

        filepath.unlink()

        return True

    return False


# ==========================================================
# Build Prompt
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
# ==========================================================
# MEMORY FUNCTIONS
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
# ==========================================================
# MEMORY EXTRACTION
# ==========================================================

def update_memory(user_message):

    memory = load_memory()

    text = user_message.lower()

    if "my name is" in text:

        name = user_message.split("my name is", 1)[1].strip()

        if name:
            memory["name"] = name

    elif "i am" in text:

        value = user_message.split("I am", 1)[1].strip()

        if value:
            memory["about_me"] = value

    elif "i like" in text:

        value = user_message.split("I like", 1)[1].strip()

        if value:
            memory["likes"] = value

    elif "my favorite language is" in text:

        value = user_message.split("my favorite language is", 1)[1].strip()

        if value:
            memory["favorite_language"] = value

    save_memory(memory)

# ==========================================================
# Clean Response
# ==========================================================

def clean_response(text):

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

def stream_gemini(prompt):

    response = client.models.generate_content_stream(
        model="gemini-flash-lite-latest",
        contents=prompt
    )

    for chunk in response:

        text = getattr(chunk, "text", "")

        if text:
            yield text

def ask_groq(prompt):

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return clean_response(
        response.choices[0].message.content
    )


def stream_groq(prompt):

    print("DEBUG: Starting Groq stream")

    stream = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        stream=True
    )

    for chunk in stream:

        print("DEBUG CHUNK:", chunk)

        if (
            chunk.choices
            and chunk.choices[0].delta.content
        ):

            yield chunk.choices[0].delta.content
def stream_openrouter(prompt):

    response = openrouter_client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        stream=True
    )

    for chunk in response:

        if (
            chunk.choices
            and chunk.choices[0].delta
            and chunk.choices[0].delta.content
        ):

            yield chunk.choices[0].delta.content

def ask_openrouter(prompt):

    api_key = os.getenv("OPENROUTER_API_KEY")

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "openai/gpt-oss-20b:free",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        },
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    return clean_response(
        data["choices"][0]["message"]["content"]
    )
    # ==========================================================
# AI PROVIDER FAILOVER
# Gemini → Groq → OpenRouter
# ==========================================================

PROVIDERS = ["gemini", "groq", "openrouter"]

active_provider = 0

# Provider cooldown times
provider_cooldown = {
    "gemini": 0,
    "groq": 0,
    "openrouter": 0
}

PROVIDER_COOLDOWN_SECONDS = 60


def ask_ai(prompt):

    global active_provider

    import time

    # Try every provider once
    for _ in range(len(PROVIDERS)):

        provider = PROVIDERS[active_provider]

        # Skip provider if it is temporarily unavailable
        if time.time() < provider_cooldown[provider]:

            print(
                f"⏳ Skipping {provider.upper()} "
                f"(cooldown active)"
            )

            active_provider = (
                active_provider + 1
            ) % len(PROVIDERS)

            continue

        try:

            # ==============================
            # Gemini
            # ==============================

            if provider == "gemini":

                response = client.models.generate_content(
                    model="gemini-flash-lite-latest",
                    contents=prompt
                )

                reply = clean_response(
                    getattr(response, "text", "")
                )

                if not reply:
                    raise Exception(
                        "Gemini returned empty response"
                    )

                print("✅ AI Provider: Gemini")

                return reply

            # ==============================
            # Groq
            # ==============================

            elif provider == "groq":

                reply = ask_groq(prompt)

                if not reply:
                    raise Exception(
                        "Groq returned empty response"
                    )

                print("✅ AI Provider: Groq")

                return reply

            # ==============================
            # OpenRouter
            # ==============================

            elif provider == "openrouter":

                reply = ask_openrouter(prompt)

                if not reply:
                    raise Exception(
                        "OpenRouter returned empty response"
                    )

                print("✅ AI Provider: OpenRouter")

                return reply

        except Exception as e:

            print(
                f"❌ {provider.upper()} failed: {e}"
            )

            # Put failed provider on cooldown
            provider_cooldown[provider] = (
                time.time()
                + PROVIDER_COOLDOWN_SECONDS
            )

            # Move to next provider
            active_provider = (
                active_provider + 1
            ) % len(PROVIDERS)

    return (
        "❌ All AI providers are currently "
        "unavailable. Please try again shortly."
    )
    # ==========================================================
# OpenRouter Test
# ==========================================================

@app.get("/test-openrouter")
async def test_openrouter():

    try:

        reply = ask_openrouter(
            "Say hello in one short sentence."
        )

        return {
            "success": True,
            "reply": reply
        }

    except Exception as e:

        print("OpenRouter Test Error:", e)

        return {
            "success": False,
            "error": str(e)
        }
@app.get("/test_failover")
async def test_failover():

    try:
        reply = ask_ai("Say hello in one short sentence.")

        return {
            "success": True,
            "active_provider_index": active_provider,
            "active_provider": PROVIDERS[active_provider],
            "reply": reply
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


@app.get("/test-comfy")
async def test_comfy():

    try:
        result = queue_comfyui_workflow(
            "a robot sitting on top of a building and dancing"
        )

        prompt_id = result["prompt_id"]

        print("COMFYUI PROMPT ID:", prompt_id)

        image_info = wait_for_comfyui_image(prompt_id)

        return {
            "success": True,
            "prompt_id": prompt_id,
            "image": image_info
        }

    except Exception as e:

        print("COMFYUI TEST ERROR:", e)

        return {
            "success": False,
            "error": str(e)
        }

async def comfy_image(filename: str):

    image_path = (
        BASE_DIR
        / "ComfyUI_windows_portable_intel"
        / "ComfyUI_windows_portable"
        / "output"
        / filename
    )

    if not image_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Generated image not found."
        )

    return FileResponse(image_path)
@app.get("/comfy-image/{filename}")
async def comfy_image(filename: str):

    output_folder = Path(
        r"C:\Users\AZ Traders\Downloads\ComfyUI_windows_portable_intel\ComfyUI_windows_portable\ComfyUI\output"
    )

    image_path = output_folder / filename

    print("COMFY OUTPUT FOLDER:", output_folder)
    print("REQUESTED IMAGE:", filename)
    print("FULL IMAGE PATH:", image_path)
    print("FILE EXISTS:", image_path.exists())

    if not image_path.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Generated image not found.",
                "path": str(image_path),
                "exists": image_path.exists()
            }
        )

    return FileResponse(image_path)
# ==========================================================
# Chat List
# ==========================================================

def get_chat_list():

    chats = []

    for file in CHAT_FOLDER.glob("*.json"):

        try:

            with open(file, "r", encoding="utf-8") as f:

                data = json.load(f)

            chats.append({

                "id": data.get("id"),

                "title": data.get("title", "New Chat"),

                "updated": data.get("updated", "")

            })

        except:

            pass

    chats.sort(

        key=lambda x: x["updated"],

        reverse=True

    )

    return chats
    # ==========================================================
# Home
# ==========================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):

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

    create_chat()

    save_chat()

    return JSONResponse(
        {
            "success": True,
            "chat_id": current_chat_id
        }
    )


# ==========================================================
# List Chats
# ==========================================================

@app.get("/chats")
async def chats():

    return JSONResponse(get_chat_list())


# ==========================================================
# Open Chat
# ==========================================================

@app.get("/chat/{chat_id}")
async def open_chat(chat_id: str):

    if not load_chat(chat_id):

        raise HTTPException(
            status_code=404,
            detail="Chat not found"
        )

    return JSONResponse(
        {
            "success": True,
            "messages": conversation_history
        }
    )


# ==========================================================
# Delete Chat
# ==========================================================

@app.delete("/chat/{chat_id}")
async def delete_chat(chat_id: str):

    if not delete_chat_file(chat_id):

        raise HTTPException(
            status_code=404,
            detail="Chat not found"
        )

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
            model=MODEL_NAME,
            contents="Write a short paragraph about artificial intelligence."
        )

        for chunk in stream:

            text = getattr(chunk, "text", "")

            if text:

                yield text

    return StreamingResponse(
        generate(),
        media_type="text/plain"
    )
@app.get("/gemini-stream-test")
def gemini_stream_test():

    def generate():

        try:

            for text in stream_gemini(
                "Say hello in one short sentence."
            ):
                print("GEMINI STREAM:", repr(text))
                yield text

        except Exception as e:

            print("GEMINI STREAM ERROR:", e)
            yield "Gemini streaming test failed."

    return StreamingResponse(
        generate(),
        media_type="text/plain"
    )
    # ==========================================================
# Chat Streaming
# ==========================================================

@app.post("/chat_stream")
async def chat_stream(request: Request):

    global conversation_history

    data = await request.json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return StreamingResponse(
            iter(["Please enter a message."]),
            media_type="text/plain"
        )

    # Save user message
    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    update_memory(user_message)

    conversation_history[:] = conversation_history[-MAX_HISTORY:]
    save_chat()

    prompt = build_prompt()

    def generate():

        print("🔥 GENERATE FUNCTION STARTED")

        full_reply = ""

        try:

            # Gemini
            print("AI Provider: Gemini")

            for text in stream_gemini(prompt):

                if text:
                    full_reply += text
                    print("GEMINI:", repr(text))
                    yield text

        except Exception as gemini_error:

            print("Gemini Streaming Error:", gemini_error)

            try:

                # Groq
                print("Switching to Groq...")

                for text in stream_groq(prompt):

                    if text:
                        full_reply += text
                        print("GROQ:", repr(text))
                        yield text

            except Exception as groq_error:

                print("Groq Streaming Error:", groq_error)

                try:

                    # OpenRouter
                    print("Switching to OpenRouter...")

                    for text in stream_openrouter(prompt):

                        if text:
                            full_reply += text
                            print("OPENROUTER:", repr(text))
                            yield text

                except Exception as openrouter_error:

                    print(
                        "OpenRouter Streaming Error:",
                        openrouter_error
                    )

                    yield "❌ AI providers are temporarily unavailable."
                    return

        # Save assistant reply
        if full_reply.strip():

            conversation_history.append({
                "role": "assistant",
                "content": clean_response(full_reply)
            })

            conversation_history[:] = conversation_history[-MAX_HISTORY:]
            save_chat()

            print("✅ Assistant reply saved")

    return StreamingResponse(
        generate(),
        media_type="text/plain"
    )
@app.post("/generate-image")
async def generate_image(request: Request):

    data = await request.json()
    prompt = data.get("prompt", "").strip()

    if not prompt:
        return JSONResponse({
            "success": False,
            "error": "Image prompt is empty."
        })

    try:
        # Send prompt to ComfyUI
        result = queue_comfyui_workflow(prompt)

        prompt_id = result["prompt_id"]

        print("🖼️ ComfyUI Prompt ID:", prompt_id)

        # Wait for image generation to finish
        image_info = wait_for_comfyui_image(prompt_id)

        # Build URL that Ayan AI can display
        image_url = (
            f"/comfy-image/{image_info['filename']}"
        )

        print("✅ Image generated:", image_url)

        return JSONResponse({
            "success": True,
            "image": image_url,
            "filename": image_info["filename"]
        })

    except Exception as e:

        print("❌ IMAGE GENERATION ERROR:", e)

        return JSONResponse({
            "success": False,
            "error": str(e)
        })
    # ==========================================================
# REGENERATE LAST AI RESPONSE
# ==========================================================

@app.post("/regenerate")
async def regenerate(request: Request):

    global conversation_history

    if not conversation_history:
        return StreamingResponse(
            iter(["Nothing to regenerate."]),
            media_type="text/plain"
        )

    # Remove previous AI response
    if conversation_history[-1]["role"] == "assistant":
        conversation_history.pop()

    # Make sure a user message exists
    if not conversation_history:
        return StreamingResponse(
            iter(["Nothing to regenerate."]),
            media_type="text/plain"
        )

    prompt = build_prompt()

    # Tell the model to produce a different answer
    prompt += """

Generate a new answer to the user's last message.
Do not copy the previous answer.
Use different wording, reasoning, examples, or structure.
"""

    def generate():

        full_reply = ""

        try:

            for text in stream_gemini(prompt):

                if text:
                    full_reply += text
                    yield text

        except Exception:

            try:

                for text in stream_groq(prompt):

                    if text:
                        full_reply += text
                        yield text

            except Exception:

                try:

                    for text in stream_openrouter(prompt):

                        if text:
                            full_reply += text
                            yield text

                except Exception:

                    yield "❌ Regeneration failed."
                    return

        if full_reply.strip():

            conversation_history.append({
                "role": "assistant",
                "content": clean_response(full_reply)
            })

            conversation_history[:] = conversation_history[-MAX_HISTORY:]

            save_chat()

    return StreamingResponse(
        generate(),
        media_type="text/plain"
    )
    # ==========================================================
# Chat
# ==========================================================

@app.post("/chat")
async def chat(request: Request):

    global conversation_history

    try:

        ensure_chat()

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

        conversation_history = conversation_history[-MAX_HISTORY:]

        save_chat()

        # ----------------------------------------
        # Build Prompt
        # ----------------------------------------
        prompt = build_prompt()

        print("DEBUG: chat_stream reached")
        print("DEBUG: prompt:", prompt[:200])

        print("=" * 70)
        print("PROMPT LENGTH:", len(prompt))
        print("HISTORY MESSAGES:", len(conversation_history))
        # ----------------------------------------
        # AI PROVIDER FALLBACK
        # Gemini → Groq → OpenRouter
        # ----------------------------------------

        try:

            reply = ask_ai(prompt)

            print(
                "AI Provider:",
                PROVIDERS[active_provider]
            )

        except Exception as e:

            print("AI Provider Error:", e)
            raise
        # ----------------------------------------
        # Save Assistant Reply
        # ----------------------------------------

        conversation_history.append(
            {
                "role": "assistant",
                "content": reply
            }
        )

        conversation_history = conversation_history[-MAX_HISTORY:]

        save_chat()

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


# ==========================================================
# Startup
# ==========================================================

if current_chat_id is None:
    create_chat()