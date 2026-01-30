import gradio as gr
import requests
from loguru import logger

BASE_URL = "http://localhost:8000"
PAGE_SIZE = 10

def get_list_sessions():
    try:
        res = requests.get(
            f"{BASE_URL}/sessions",
            params={"page": 1, "page_size": PAGE_SIZE},
            timeout=5
        )
        res.raise_for_status()
        data = res.json()

        return [
            (f"{s['name']} ({s['message_count']} msgs)", s["session_id"])
            for s in data.get("sessions", [])
        ]
    except Exception as e:
        logger.error(e)
        return []


def create_session(chat_name: str):
    if not chat_name or not chat_name.strip():
        chat_name = "New Chat"

    res = requests.post(
        f"{BASE_URL}/sessions",
        json={"name": chat_name},
        timeout=5
    )
    res.raise_for_status()
    return res.json()


def fetch_session_messages(session_id: str, page: int):
    res = requests.get(
        f"{BASE_URL}/sessions/{session_id}/messages",
        params={"page": page, "page_size": PAGE_SIZE},
        timeout=5
    )
    res.raise_for_status()
    return res.json()


def new_chat(chat_name):
    data = create_session(chat_name)

    sessions = get_list_sessions()

    return (
        gr.update(choices=sessions, value=data["session_id"]),
        data["session_id"],
        [],
        0,
        True,
        ""
    )


def select_session(session_id):
    if not session_id:
        return [], None, 0, False

    data = fetch_session_messages(session_id, page=0)

    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in data["messages"]
        if m["role"] in ("user", "assistant")
    ]

    return (
        messages,
        session_id,
        1,
        data["has_more"]
    )

def delete_session(session_id):
    if not session_id:
        return (
            gr.update(),
            None,
            [],
            0,
            False
        )

    try:
        requests.delete(
            f"{BASE_URL}/sessions/{session_id}",
            timeout=5
        ).raise_for_status()

        sessions = get_list_sessions()

        return (
            gr.update(choices=sessions, value=None),
            None,
            [],
            0,
            False
        )
    except Exception as e:
        logger.error(e)
        return gr.update(), session_id, [], 0, False



def load_more_messages(session_id, history, page):
    if not session_id:
        return history, page, False

    data = fetch_session_messages(session_id, page)

    older = [
        {"role": m["role"], "content": m["content"]}
        for m in data["messages"]
        if m["role"] in ("user", "assistant")
    ]

    return (
        older + history,
        page + 1,
        data["has_more"]
    )


def chat_fn(message, history, session_id):
    if not message or not session_id:
        yield history
        return

    try:
        with requests.post(
            f"{BASE_URL}/sessions/{session_id}/messages/stream",
            json={"message": message},
            stream=True,
            timeout=60
        ) as r:
            r.raise_for_status()

            partial = ""
            for chunk in r.iter_lines():
                if not chunk:
                    continue

                line = chunk.decode()
                if line.startswith("data: "):
                    partial += line[6:]
                    yield history + [
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": partial}
                    ]

    except Exception as e:
        yield history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": f"Error: {e}"}
        ]


with gr.Blocks(title="Chat with Session Memory") as demo:

    current_chat_id = gr.State(None)
    current_page = gr.State(0)
    has_more_state = gr.State(True)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## 💬 Chat Sessions")

            chat_name_input = gr.Textbox(
                label="New Chat Name",
                placeholder="Enter chat name..."
            )
            new_btn = gr.Button("➕ New Chat", variant="primary")

            session_list = gr.Radio(
                label="Your Chats",
                choices=get_list_sessions()
            )

            delete_btn = gr.Button("🗑️ Delete Chat", variant="stop")

        with gr.Column(scale=4):
            gr.Markdown("## 🤖 Chat")

            chatbot = gr.Chatbot(height=750)

            load_more_btn = gr.Button("⬆️ Load more messages")
            no_more_text = gr.Markdown("✅ No more messages", visible=False)

            msg_input = gr.Textbox(
                placeholder="Type your message...",
                show_label=False
            )


    new_btn.click(
        new_chat,
        inputs=[chat_name_input],
        outputs=[
            session_list,
            current_chat_id,
            chatbot,
            current_page,
            has_more_state,
            chat_name_input
        ]
    )


    session_list.change(
        select_session,
        inputs=[session_list],
        outputs=[
            chatbot,
            current_chat_id,
            current_page,
            has_more_state
        ]
    ).then(
        lambda has_more: (
            gr.update(visible=has_more),
            gr.update(visible=not has_more)
        ),
        inputs=[has_more_state],
        outputs=[load_more_btn, no_more_text]
    )

    delete_btn.click(
        delete_session,
        inputs=[session_list],
        outputs=[
            session_list,
            current_chat_id,
            chatbot,
            current_page,
            has_more_state
        ]
    ).then(
        lambda has_more: (
            gr.update(visible=has_more),
            gr.update(visible=not has_more)
        ),
        inputs=[has_more_state],
        outputs=[load_more_btn, no_more_text]
    )

    load_more_btn.click(
        load_more_messages,
        inputs=[session_list, chatbot, current_page],
        outputs=[chatbot, current_page, has_more_state]
    ).then(
        lambda has_more: (
            gr.update(visible=has_more),
            gr.update(visible=not has_more)
        ),
        inputs=[has_more_state],
        outputs=[load_more_btn, no_more_text]
    )

    msg_input.submit(
        chat_fn,
        inputs=[msg_input, chatbot, current_chat_id],
        outputs=[chatbot]
    ).then(
        lambda: "",
        outputs=[msg_input]
    )

demo.launch(server_name="0.0.0.0", server_port=7860)
