/* ==========================================================
   AYAN AI
   SCRIPT.JS
========================================================== */

let chats = [];
let currentChat = null;
let lastUserMessage = "";
let ayanOrb = null;


/* ==========================================================
   ORB
========================================================== */

function orbThinking() {
    if (!ayanOrb) return;

    ayanOrb.classList.remove("responding");
    ayanOrb.classList.add("thinking");
}


function orbResponding() {
    if (!ayanOrb) return;

    ayanOrb.classList.remove("thinking");
    ayanOrb.classList.add("responding");
}


function orbIdle() {
    if (!ayanOrb) return;

    ayanOrb.classList.remove(
        "thinking",
        "responding"
    );
}


/* ==========================================================
   SEND MESSAGE
========================================================== */

async function sendMessage() {

    const input =
        document.getElementById("message");

    const chatArea =
        document.getElementById("chatArea");

    if (!input || !chatArea) {
        console.error(
            "Ayan AI: chat elements not found."
        );
        return;
    }

    const message =
        input.value.trim();

    if (!message) {
        return;
    }

    lastUserMessage =
        message;


    /* ======================================================
       REMOVE WELCOME
    ======================================================= */

    const welcome =
        chatArea.querySelector(".welcome");

    if (welcome) {
        welcome.remove();
    }


    /* ======================================================
       USER MESSAGE
    ======================================================= */

    const userBubble =
        document.createElement("div");

    userBubble.className =
        "message user";

    const userTime =
        new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit"
        });

    userBubble.innerHTML = `
        <strong>You</strong>

        <span class="message-time">
            ${userTime}
        </span>

        <br>

        ${escapeHtml(message)}
    `;

    chatArea.appendChild(
        userBubble
    );

    input.value = "";


    /* ======================================================
       AI MESSAGE
    ======================================================= */

    const aiBubble =
        document.createElement("div");

    aiBubble.className =
        "message ai";

    const aiTime =
        new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit"
        });

    aiBubble.innerHTML = `
        <strong>Ayan AI</strong>

        <span class="message-time">
            ${aiTime}
        </span>

        <br>

        <div class="markdown-body">

            <span class="thinking-dots">
                <span></span>
                <span></span>
                <span></span>
            </span>

        </div>

        <div class="message-actions">

            <button
                type="button"
                class="copy-btn"
                title="Copy">
                📋
            </button>

            <button
                type="button"
                class="regenerate-btn"
                title="Regenerate">
                ↻
            </button>

            <button
                type="button"
                class="like-btn"
                title="Like">
                👍
            </button>

            <button
                type="button"
                class="dislike-btn"
                title="Dislike">
                👎
            </button>

        </div>
    `;

    chatArea.appendChild(
        aiBubble
    );


    const markdown =
        aiBubble.querySelector(
            ".markdown-body"
        );

    chatArea.scrollTop =
        chatArea.scrollHeight;


    /* ======================================================
       START THINKING
    ======================================================= */

    orbThinking();


    /* ======================================================
       MAKE SURE A CHAT EXISTS
    ======================================================= */

    try {

        if (!currentChat) {

            const newChatResponse =
                await fetch(
                    "/new_chat",
                    {
                        method: "POST"
                    }
                );

            if (!newChatResponse.ok) {

                throw new Error(
                    "Unable to create chat."
                );

            }

            const newChatData =
                await newChatResponse.json();

            currentChat =
                newChatData.chat_id;

            await loadChats();

        }


        /* ==================================================
           STREAM FROM BACKEND
        =================================================== */

        const response =
            await fetch(
                "/chat_stream",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        message: message,
                        chat_id: currentChat
                    })
                }
            );


        /* ==================================================
           STREAMING RESPONSE
        =================================================== */

        if (!response.ok) {

            throw new Error(
                `Chat request failed: ${response.status}`
            );

        }


        if (!response.body) {

            throw new Error(
                "Streaming is not supported."
            );

        }


        /* ==================================================
           READ STREAM
        =================================================== */

        const reader =
            response.body.getReader();

        const decoder =
            new TextDecoder("utf-8");

        let fullReply = "";


        while (true) {

            const {
                done,
                value
            } = await reader.read();


            if (done) {
                break;
            }


            if (!value) {
                continue;
            }


            const chunk =
                decoder.decode(
                    value,
                    {
                        stream: true
                    }
                );


            if (!chunk) {
                continue;
            }


            orbResponding();


            fullReply +=
                chunk;


            aiBubble.dataset.reply =
                fullReply;


            /* ==============================================
               LIVE MARKDOWN
            =============================================== */

            if (markdown) {

                markdown.innerHTML =
                    marked.parse(
                        fullReply
                    );

            }


            chatArea.scrollTop =
                chatArea.scrollHeight;

        }


        /* ==================================================
           FLUSH DECODER
        =================================================== */

        fullReply +=
            decoder.decode();


        aiBubble.dataset.reply =
            fullReply;


        /* ==================================================
           FINAL MARKDOWN
        =================================================== */

        if (
            markdown &&
            fullReply.trim()
        ) {

            markdown.innerHTML =
                marked.parse(
                    fullReply
                );

        }


        if (
            markdown &&
            !fullReply.trim()
        ) {

            markdown.innerHTML =
                "No response received from Ayan AI.";

        }


        /* ==================================================
           CODE HIGHLIGHT
        =================================================== */

        highlightCode(
            aiBubble
        );


        /* ==================================================
           MESSAGE ACTIONS
        =================================================== */

        addMessageActions(
            aiBubble
        );


        chatArea.scrollTop =
            chatArea.scrollHeight;


        orbIdle();


        /* ==================================================
           REFRESH CHAT SIDEBAR

           Sidebar failure must NOT turn a successful
           AI response into "Connection Error".
        =================================================== */

        try {

            await loadChats();

        }

        catch (sidebarError) {

            console.error(
                "Sidebar refresh error:",
                sidebarError
            );

        }

    }


    catch (error) {

        console.error(
            "Ayan AI streaming error:",
            error
        );


        orbIdle();


        if (markdown) {

            markdown.innerHTML = `
                <span>
                    ❌ Connection Error
                </span>
            `;

        }

    }

}
/* ==========================================================
   MESSAGE ACTIONS
========================================================== */

function addMessageActions(aiBubble) {

    if (!aiBubble) return;


    const copyBtn =
        aiBubble.querySelector(
            ".copy-btn"
        );


    const regenBtn =
        aiBubble.querySelector(
            ".regenerate-btn"
        );


    const likeBtn =
        aiBubble.querySelector(
            ".like-btn"
        );


    const dislikeBtn =
        aiBubble.querySelector(
            ".dislike-btn"
        );


    /* ======================================================
       COPY
    ======================================================= */

    if (copyBtn) {

        copyBtn.onclick =
            async () => {

                try {

                    const reply =
                        aiBubble.dataset.reply ||
                        "";


                    if (!reply.trim()) {
                        return;
                    }


                    await navigator.clipboard.writeText(
                        reply
                    );


                    copyBtn.textContent =
                        "✓";


                    setTimeout(() => {

                        copyBtn.textContent =
                            "📋";

                    }, 1000);

                }

                catch (error) {

                    console.error(
                        "Copy error:",
                        error
                    );

                }

            };

    }


    /* ======================================================
       LIKE
    ======================================================= */

    if (likeBtn) {

        likeBtn.onclick =
            () => {

                likeBtn.classList.toggle(
                    "active"
                );


                if (dislikeBtn) {

                    dislikeBtn.classList.remove(
                        "active"
                    );

                }

            };

    }


    /* ======================================================
       DISLIKE
    ======================================================= */

    if (dislikeBtn) {

        dislikeBtn.onclick =
            () => {

                dislikeBtn.classList.toggle(
                    "active"
                );


                if (likeBtn) {

                    likeBtn.classList.remove(
                        "active"
                    );

                }

            };

    }


    /* ======================================================
       REGENERATE
    ======================================================= */

    if (regenBtn) {

        regenBtn.onclick =
            async () => {

                regenBtn.disabled =
                    true;

                regenBtn.textContent =
                    "⏳";

                orbThinking();


                try {

                    const response =
                        await fetch(
                            "/regenerate",
                            {
                                method:
                                    "POST"
                            }
                        );


                    /* ======================================
                       /regenerate ALSO returns a STREAM.

                       DO NOT use response.json().
                    ======================================= */

                    if (!response.ok) {

                        throw new Error(
                            `Server Error: ${response.status}`
                        );

                    }


                    if (!response.body) {

                        throw new Error(
                            "No streaming response."
                        );

                    }


                    const reader =
                        response.body.getReader();


                    const decoder =
                        new TextDecoder(
                            "utf-8"
                        );


                    let newReply =
                        "";


                    const markdown =
                        aiBubble.querySelector(
                            ".markdown-body"
                        );


                    /* ======================================
                       STREAM REGENERATED RESPONSE
                    ======================================= */

                    while (true) {

                        const {
                            done,
                            value
                        } =
                            await reader.read();


                        if (done) {
                            break;
                        }


                        if (!value) {
                            continue;
                        }


                        const chunk =
                            decoder.decode(
                                value,
                                {
                                    stream: true
                                }
                            );


                        if (!chunk) {
                            continue;
                        }


                        orbResponding();


                        newReply +=
                            chunk;


                        /* ==================================
                           UPDATE CURRENT REPLY
                        =================================== */

                        aiBubble.dataset.reply =
                            newReply;


                        if (markdown) {

                            markdown.innerHTML =
                                marked.parse(
                                    newReply
                                );

                        }


                        const chatArea =
                            document.getElementById(
                                "chatArea"
                            );


                        if (chatArea) {

                            chatArea.scrollTop =
                                chatArea.scrollHeight;

                        }

                    }


                    /* ======================================
                       FLUSH DECODER
                    ======================================= */

                    newReply +=
                        decoder.decode();


                    aiBubble.dataset.reply =
                        newReply;


                    /* ======================================
                       FINAL RESPONSE
                    ======================================= */

                    if (markdown) {

                        if (
                            newReply.trim()
                        ) {

                            markdown.innerHTML =
                                marked.parse(
                                    newReply
                                );

                        }

                        else {

                            markdown.innerHTML =
                                "No response received.";

                        }

                    }


                    highlightCode(
                        aiBubble
                    );


                    regenBtn.textContent =
                        "↻";


                    orbIdle();


                    await loadChats();

                }


                catch (error) {

                    console.error(
                        "Regenerate error:",
                        error
                    );


                    regenBtn.textContent =
                        "❌";


                    orbIdle();

                }


                finally {

                    regenBtn.disabled =
                        false;

                }

            };

    }

}


/* ==========================================================
   LOAD CHATS
========================================================== */

async function loadChats() {

    const chatList =
        document.getElementById(
            "chatList"
        );


    if (!chatList) {
        return;
    }


    try {

        const response =
            await fetch(
                "/chats"
            );


        if (!response.ok) {

            throw new Error(
                `Server Error: ${response.status}`
            );

        }


        const chatData =
            await response.json();


        /* ==============================================
           IMPORTANT

           Keep global chat array updated.
        =============================================== */

        chats =
            Array.isArray(chatData)
                ? chatData
                : [];


        chatList.innerHTML =
            "";


        chats.forEach(
            chat => {

                const item =
                    document.createElement(
                        "div"
                    );


                item.className =
                    "chat-item";


                item.innerHTML = `
                    <span>
                        💬 ${escapeHtml(
                            chat.title
                        )}
                    </span>

                    <button
                        type="button"
                        class="delete-chat"
                        data-id="${escapeHtml(
                            chat.id
                        )}">
                        🗑️
                    </button>
                `;


                item.onclick =
                    () => openChat(
                        chat.id
                    );


                const deleteBtn =
                    item.querySelector(
                        ".delete-chat"
                    );


                if (deleteBtn) {

                    deleteBtn.onclick =
                        async event => {

                            event.stopPropagation();


                            if (
                                !confirm(
                                    "Delete chat?"
                                )
                            ) {

                                return;

                            }


                            try {

                                const response =
                                    await fetch(
                                        `/chat/${chat.id}`,
                                        {
                                            method:
                                                "DELETE"
                                        }
                                    );


                                if (!response.ok) {

                                    throw new Error(
                                        "Delete failed"
                                    );

                                }


                                if (
                                    currentChat ===
                                    chat.id
                                ) {

                                    currentChat =
                                        null;

                                }


                                await loadChats();

                            }

                            catch (error) {

                                console.error(
                                    "Delete chat error:",
                                    error
                                );

                            }

                        };

                }


                chatList.appendChild(
                    item
                );

            }
        );

    }

    catch (error) {

        console.error(
            "Load chats error:",
            error
        );

    }

}


/* ==========================================================
   OPEN CHAT
========================================================== */

async function openChat(chatId) {

    const chatArea =
        document.getElementById(
            "chatArea"
        );


    if (!chatArea) {
        return;
    }


    try {

        const response =
            await fetch(
                `/chat/${chatId}`
            );


        if (!response.ok) {

            throw new Error(
                "Unable to load chat."
            );

        }


        const data =
            await response.json();


        if (!data.success) {

            alert(
                "Unable to load chat."
            );

            return;

        }


        currentChat =
            chatId;


        chatArea.innerHTML =
            "";


        data.messages.forEach(
            msg => {

                const bubble =
                    document.createElement(
                        "div"
                    );


                /* =========================================
                   USER MESSAGE
                ========================================== */

                if (
                    msg.role === "user"
                ) {

                    bubble.className =
                        "message user";


                    bubble.innerHTML = `
                        <strong>You</strong>
                        <br>
                        ${escapeHtml(
                            msg.content
                        )}
                    `;

                }


                /* =========================================
                   AI MESSAGE
                ========================================== */

                else {

                    bubble.className =
                        "message ai";


                    bubble.innerHTML = `
                        <strong>Ayan AI</strong>

                        <br>

                        <div class="markdown-body">
                            ${marked.parse(
                                msg.content || ""
                            )}
                        </div>

                        <div class="message-actions">

                            <button
                                type="button"
                                class="copy-btn"
                                title="Copy">
                                📋
                            </button>

                            <button
                                type="button"
                                class="regenerate-btn"
                                title="Regenerate">
                                ↻
                            </button>

                            <button
                                type="button"
                                class="like-btn"
                                title="Like">
                                👍
                            </button>

                            <button
                                type="button"
                                class="dislike-btn"
                                title="Dislike">
                                👎
                            </button>

                        </div>
                    `;


                    bubble.dataset.reply =
                        msg.content || "";


                    addMessageActions(
                        bubble
                    );

                }


                chatArea.appendChild(
                    bubble
                );

            }
        );


        highlightCode(
            chatArea
        );


        chatArea.scrollTop =
            chatArea.scrollHeight;

    }


    catch (error) {

        console.error(
            "Open chat error:",
            error
        );

    }

}


/* ==========================================================
   NEW CHAT
========================================================== */

async function newChat() {

    try {

        const response =
            await fetch(
                "/new_chat",
                {
                    method:
                        "POST"
                }
            );


        if (!response.ok) {

            throw new Error(
                "Unable to create new chat."
            );

        }


        /* ==============================================
           IMPORTANT

           /new_chat DOES return JSON.
        =============================================== */

        const chatData =
            await response.json();


        currentChat =
            chatData.chat_id;


        await loadChats();


        const chatArea =
            document.getElementById(
                "chatArea"
            );


        if (!chatArea) {
            return;
        }


        chatArea.innerHTML = `
            <div class="welcome">

                <h1>
                    🤖 Welcome to Ayan AI
                </h1>

                <p>
                    Your intelligent AI assistant.
                </p>

                <div class="suggestions">

                    <button
                        type="button"
                        data-prompt="Help me write clean, efficient code for: ">
                        💻 Write Code
                    </button>

                    <button
                        type="button"
                        data-prompt="Summarize the following text clearly and briefly: ">
                        📄 Summarize
                    </button>

                    <button
                        type="button"
                        data-prompt="Explain the following concept in a simple, easy-to-understand way: ">
                        🧠 Explain
                    </button>

                    <button
                        type="button"
                        data-prompt="Research and give me a clear, structured explanation about: ">
                        🌐 Research
                    </button>

                </div>

            </div>
        `;


        /* ==============================================
           RECONNECT SUGGESTION BUTTONS

           The welcome HTML was recreated dynamically,
           so the original listeners no longer exist.
        =============================================== */

        setupSuggestionButtons();


        const input =
            document.getElementById(
                "message"
            );


        if (input) {

            input.value =
                "";

            input.focus();

        }


        orbIdle();

    }


    catch (error) {

        console.error(
            "New chat error:",
            error
        );

    }

}


/* ==========================================================
   STREAM TEST
========================================================== */

async function sendMessageStream() {

    try {

        const response =
            await fetch(
                "/stream-test"
            );


        if (!response.ok) {

            throw new Error(
                "Stream test failed."
            );

        }


        if (!response.body) {
            return;
        }


        const reader =
            response.body.getReader();


        const decoder =
            new TextDecoder();


        let result =
            "";


        while (true) {

            const {
                done,
                value
            } =
                await reader.read();


            if (done) {
                break;
            }


            result +=
                decoder.decode(
                    value,
                    {
                        stream: true
                    }
                );


            console.log(
                result
            );

        }

    }


    catch (error) {

        console.error(
            "Stream test error:",
            error
        );

    }

}


/* ==========================================================
   ENTER KEY
========================================================== */

document.addEventListener(
    "keydown",
    event => {

        const input =
            document.getElementById(
                "message"
            );


        if (
            document.activeElement === input &&
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            sendMessage();

        }

    }
);


/* ==========================================================
   ESCAPE HTML
========================================================== */

function escapeHtml(value) {

    const div =
        document.createElement(
            "div"
        );


    div.textContent =
        value ?? "";


    return div.innerHTML;

}


/* ==========================================================
   HIGHLIGHT CODE
========================================================== */

function highlightCode(container) {

    if (!container) {
        return;
    }


    container
        .querySelectorAll(
            "pre code"
        )
        .forEach(
            code => {

                try {

                    hljs.highlightElement(
                        code
                    );

                }

                catch (error) {

                    console.error(
                        "Highlight error:",
                        error
                    );

                }

            }
        );

}


/* ==========================================================
   SUGGESTION BUTTONS
========================================================== */

function setupSuggestionButtons() {

    const input =
        document.getElementById(
            "message"
        );


    const suggestionButtons =
        document.querySelectorAll(
            ".suggestions button"
        );


    suggestionButtons.forEach(
        button => {

            /* Avoid duplicate listeners */

            if (
                button.dataset.ayanBound ===
                "true"
            ) {

                return;

            }


            button.dataset.ayanBound =
                "true";


            button.addEventListener(
                "click",
                () => {

                    const prompt =
                        button.dataset.prompt ||
                        "";


                    if (!input) {
                        return;
                    }


                    input.value =
                        prompt;


                    input.focus();


                    input.setSelectionRange(
                        input.value.length,
                        input.value.length
                    );

                }
            );

        }
    );

}


/* ==========================================================
   PAGE LOAD
========================================================== */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        /* ==============================================
           ORB
        =============================================== */

        ayanOrb =
            document.getElementById(
                "ayanOrb"
            );


        /* ==============================================
           BUTTONS
        =============================================== */

        const sendBtn =
            document.getElementById(
                "sendBtn"
            );


        const input =
            document.getElementById(
                "message"
            );


        const newChatBtn =
            document.getElementById(
                "newChat"
            );


        /* ==============================================
           SEND BUTTON
        =============================================== */

        if (sendBtn) {

            sendBtn.addEventListener(
                "click",
                sendMessage
            );

        }


        /* ==============================================
           NEW CHAT BUTTON
        =============================================== */

        if (newChatBtn) {

            newChatBtn.addEventListener(
                "click",
                newChat
            );

        }


        /* ==============================================
           INPUT
        =============================================== */

        if (input) {

            input.focus();

        }


        /* ==============================================
           SUGGESTIONS
        =============================================== */

        setupSuggestionButtons();


        /* ==============================================
           LOAD CHATS
        =============================================== */

        loadChats()
            .then(
                async () => {

                    if (
                        !currentChat &&
                        chats.length > 0
                    ) {

                        await openChat(
                            chats[0].id
                        );

                    }

                    else if (
                        !currentChat &&
                        chats.length === 0
                    ) {

                        await newChat();

                    }

                }
            );

    }
);


/* ==========================================================
   AYAN AI VOICE INPUT
========================================================== */

let recognition = null;
let isListening = false;
let finalTranscript = "";


document.addEventListener(
    "DOMContentLoaded",
    () => {

        const voiceBtn =
            document.getElementById(
                "voiceBtn"
            );


        const messageInput =
            document.getElementById(
                "message"
            );


        const SpeechRecognition =
            window.SpeechRecognition ||
            window.webkitSpeechRecognition;


        if (
            !SpeechRecognition ||
            !voiceBtn ||
            !messageInput
        ) {

            console.log(
                "Speech recognition is not supported by this browser."
            );


            if (voiceBtn) {

                voiceBtn.disabled =
                    true;

                voiceBtn.title =
                    "Voice input is not supported in this browser";

            }

            return;

        }


        recognition =
            new SpeechRecognition();


        recognition.continuous =
            true;


        recognition.interimResults =
            true;


        recognition.lang =
            "en-US";


        /* ==================================================
           START / STOP BUTTON
        =================================================== */

        voiceBtn.addEventListener(
            "click",
            () => {

                if (isListening) {

                    stopVoice();

                }

                else {

                    startVoice();

                }

            }
        );


        /* ==================================================
           START
        =================================================== */

        function startVoice() {

            try {

                finalTranscript =
                    "";

                recognition.start();

            }

            catch (error) {

                console.log(
                    "Voice already running:",
                    error
                );

            }

        }


        /* ==================================================
           SPEECH STARTED
        =================================================== */

        recognition.onstart =
            () => {

                isListening =
                    true;


                voiceBtn.classList.add(
                    "listening"
                );


                voiceBtn.textContent =
                    "🔴";


                voiceBtn.title =
                    "Stop voice input";

            };


        /* ==================================================
           SPEECH RESULT
        =================================================== */

        recognition.onresult =
            event => {

                let interimTranscript =
                    "";


                for (
                    let i = event.resultIndex;
                    i < event.results.length;
                    i++
                ) {

                    const transcript =
                        event.results[i][0]
                            .transcript;


                    if (
                        event.results[i]
                            .isFinal
                    ) {

                        finalTranscript +=
                            transcript + " ";

                    }

                    else {

                        interimTranscript +=
                            transcript;

                    }

                }


                messageInput.value =
                    finalTranscript +
                    interimTranscript;

            };


        /* ==================================================
           SPEECH END
        =================================================== */

        recognition.onend =
            () => {

                if (isListening) {

                    setTimeout(
                        () => {

                            try {

                                recognition.start();

                            }

                            catch (error) {

                                console.log(
                                    "Voice restart:",
                                    error
                                );

                            }

                        },
                        150
                    );

                }

            };


        /* ==================================================
           ERROR
        =================================================== */

        recognition.onerror =
            event => {

                console.log(
                    "Voice recognition:",
                    event.error
                );


                if (
                    event.error ===
                        "no-speech" ||
                    event.error ===
                        "audio-capture"
                ) {

                    return;

                }

            };


        /* ==================================================
           STOP
        =================================================== */

        function stopVoice() {

            isListening =
                false;


            try {

                recognition.stop();

            }

            catch (error) {

                console.log(
                    "Voice stop:",
                    error
                );

            }


            voiceBtn.classList.remove(
                "listening"
            );


            voiceBtn.textContent =
                "🎙️";


            voiceBtn.title =
                "Voice input";

        }
    }
);