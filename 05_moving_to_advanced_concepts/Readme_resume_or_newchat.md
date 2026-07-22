# Resume Conversations and Start New Chats

This document explains how `streamlit_frontend_threading.py` evolved from `streamlit2.py`. The earlier file supports one fixed conversation. The threading version supports multiple conversations, lets the user start a new chat, and lets the user reopen an earlier chat.

The backend used by the threading frontend is `langgraph_backend_02.py`. It compiles the LangGraph with an `InMemorySaver` checkpointer. The checkpointer stores graph state separately for each `thread_id` while the Python process is running.

## 1. The starting point: one fixed thread

In `streamlit2.py`, the configuration is effectively fixed:

```python
CONFIG = {'configurable': {'thread_id': 'thread-1'}}
```

Every request uses the same LangGraph thread. Therefore, all messages belong to `thread-1`. The browser session also has only one `message_history` list, so there is no concept of another conversation.

The threading version changes this from a constant into a value stored in Streamlit session state:

```python
if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_thread_id()
```

The active thread can now change during the session.

## 2. Imports

The original file imports Streamlit, the LangGraph chatbot, and `HumanMessage`:

```python
import streamlit as st
from langgraph_backend_02 import chatbot
from langchain_core.messages import HumanMessage
```

The threading version adds:

```python
import uuid
```

`uuid.uuid4()` creates a practically unique identifier. Converting it with `str(...)` makes it suitable for Streamlit state, sidebar labels, and LangGraph configuration.

To use readable IDs instead, you could replace the generator with:

```python
def generate_thread_id():
    return f"chat-{len(st.session_state['chat_threads']) + 1}"
```

UUIDs are safer when IDs must remain unique. Human-readable IDs are easier to study and display, but need a uniqueness strategy.

## 3. `generate_thread_id`: creating an identity for a chat

```python
def generate_thread_id():
    thread_id = str(uuid.uuid4())
    return thread_id
```

This function has one responsibility: create a new ID. Keeping it separate makes the ID policy easy to change later.

The ID is not the conversation itself. It is a key. LangGraph uses that key to find the saved state belonging to one conversation.

## 4. `reset_chat`: starting a new conversation

```python
def reset_chat():
    thread_id = generate_thread_id()
    st.session_state['thread_id'] = thread_id
    add_thread(st.session_state['thread_id'])
    st.session_state['message_history'] = []
```

When `New Chat` is clicked, Streamlit reruns the script. This function then:

1. Generates a new thread ID.
2. Makes that ID the active thread.
3. Adds it to the list shown in the sidebar.
4. Clears the visible message list, so the screen starts empty.

Clearing `message_history` only clears the displayed frontend list. It does not delete the old LangGraph checkpoint. That is why the old conversation can still be reopened by its ID.

## 5. `add_thread`: maintaining the conversation index

```python
def add_thread(thread_id):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].append(thread_id)
```

`chat_threads` is a list of known thread IDs. The membership check prevents duplicate sidebar buttons.

The current thread is registered during setup:

```python
add_thread(st.session_state['thread_id'])
```

This is important because the first thread should appear in the conversation list even before the user sends a message.

## 6. `load_conversation`: reading a saved LangGraph state

```python
def load_conversation(thread_id):
    state = chatbot.get_state(
        config={'configurable': {'thread_id': thread_id}}
    )
    return state.values.get('messages', [])
```

The same `thread_id` used during `chatbot.stream(...)` is passed to `get_state(...)`. LangGraph then returns the checkpoint for that thread.

The safe lookup is intentional:

```python
state.values.get('messages', [])
```

Using `state.values['messages']` can raise a `KeyError` when a thread has no saved messages yet. `.get(..., [])` means “return an empty list if the key is absent.”

If your graph stores another state key, change `'messages'` to that key. If you replace `InMemorySaver` with a persistent checkpointer, the same lookup idea remains, but the data can survive application restarts depending on the checkpointer configuration.

## 7. Session-state initialization

Streamlit reruns the script from top to bottom after interactions. Values that must survive those reruns belong in `st.session_state`.

```python
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []

if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_thread_id()

if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = []

add_thread(st.session_state['thread_id'])
```

The order matters. `thread_id` must be initialized before it is used to build a configuration or added to `chat_threads`. Otherwise Streamlit raises:

```text
KeyError: st.session_state has no key "thread_id"
```

Do not create `CONFIG` at the top of the file using `st.session_state['thread_id']` before this setup block. Build it after initialization, or build it inside the message-submission block.

## 8. Sidebar controls

```python
st.sidebar.title("LangGraph Chatbot")

if st.sidebar.button('New Chat'):
    reset_chat()

st.sidebar.header('My Conversations')
for thread_id in st.session_state['chat_threads'][::-1]:
    if st.sidebar.button(str(thread_id)):
        ...
```

`st.sidebar` moves controls out of the main chat area. The slice `[::-1]` displays the newest thread first because new IDs are appended to the end of the list.

To show the oldest thread first, use:

```python
for thread_id in st.session_state['chat_threads']:
```

To show friendly names instead of UUIDs, maintain a second dictionary such as `thread_titles[thread_id]`. Keep using the UUID internally as the LangGraph key.

## 9. Selecting and reconstructing an old conversation

```python
if st.sidebar.button(str(thread_id)):
    st.session_state['thread_id'] = thread_id
    messages = load_conversation(thread_id)
    temp_messages = []

    for msg in messages:
        if isinstance(msg, HumanMessage):
            role = 'user'
        else:
            role = 'assistant'
        temp_messages.append({'role': role, 'content': msg.content})

    st.session_state['message_history'] = temp_messages
```

LangGraph returns LangChain message objects. Streamlit chat rendering expects dictionaries with `role` and `content`, so this block converts one representation into the other.

`HumanMessage` becomes the `user` role. Other message types currently become `assistant`. That works for this simple graph, whose response is an AI message. If tools or system messages are added later, handle them explicitly:

```python
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

if isinstance(msg, HumanMessage):
    role = 'user'
elif isinstance(msg, AIMessage):
    role = 'assistant'
elif isinstance(msg, SystemMessage):
    continue
```

The temporary list avoids partially replacing the visible history while it is being reconstructed. The final assignment is essential:

```python
st.session_state['message_history'] = temp_messages
```

Without it, the sidebar selection would load data but the screen would continue displaying the previously active chat.

## 10. Rendering the active history

```python
for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.text(message['content'])
```

This block runs on every rerun. It redraws the currently selected conversation from session state. The allowed roles here are normally `user` and `assistant`.

## 11. Sending a message with the active thread

The earlier file sends every request with `thread-1`. The threading version creates configuration from the currently selected ID:

```python
if user_input:
    config = {
        'configurable': {
            'thread_id': st.session_state['thread_id']
        }
    }
```

This must happen after session initialization. It is placed inside `if user_input` because that is the only time the graph needs to be called.

The user message is added to the frontend immediately:

```python
st.session_state['message_history'].append(
    {'role': 'user', 'content': user_input}
)
```

The same message is passed to LangGraph:

```python
chatbot.stream(
    {'messages': [HumanMessage(content=user_input)]},
    config=config,
    stream_mode='messages'
)
```

The configuration connects this request to the selected checkpoint. If the user selected an old conversation, the new message continues that conversation. If the user clicked `New Chat`, it starts in the new thread.

## 12. Streaming the assistant response

`streamlit2.py` already introduced streaming compared with the older `streamlit.py`: it uses `chatbot.stream(...)` and `st.write_stream(...)` instead of `chatbot.invoke(...)` and `st.text(...)`.

The threading file keeps that streaming behavior:

```python
with st.chat_message('assistant'):
    ai_message = st.write_stream(
        message_chunk.content
        for message_chunk, metadata in chatbot.stream(
            {'messages': [HumanMessage(content=user_input)]},
            config=config,
            stream_mode='messages'
        )
    )
```

`chatbot.stream(...)` yields chunks as the model produces them. The generator extracts each chunk's text with `message_chunk.content`. `st.write_stream(...)` displays those pieces progressively and returns the combined text, which is saved for the next rerun:

```python
st.session_state['message_history'].append(
    {'role': 'assistant', 'content': ai_message}
)
```

If you want a non-streaming version, use `chatbot.invoke(...)`, take the final message, and display it with `st.text(...)`. Streaming changes the display timing, not the basic thread-selection idea.

## 13. Complete request flow

```text
First run
  -> initialize message_history, thread_id, and chat_threads
  -> register the current thread

New Chat
  -> generate a new ID
  -> make it active
  -> clear visible history

Send message
  -> create config from active thread_id
  -> stream response into the assistant bubble
  -> LangGraph checkpoint stores state under that ID

Select old conversation
  -> call get_state with its ID
  -> convert LangChain messages to Streamlit dictionaries
  -> replace message_history
  -> rerun renders the selected conversation
```

## 14. Important limitation: memory is in-process

`langgraph_backend_02.py` uses `InMemorySaver`. Its checkpoints are lost when the Streamlit process stops or restarts. The sidebar list is also stored in `st.session_state`, so it is tied to one browser session.

For durable conversations, replace the in-memory checkpointer with a persistent LangGraph checkpointer and store the thread index in a database. The frontend structure can remain mostly the same: generate an ID, pass it in `configurable.thread_id`, and call `get_state(...)` when loading.

## 15. Common mistakes and how to diagnose them

### Missing `thread_id`

Cause: reading `st.session_state['thread_id']` before initializing it.

Fix: initialize it near the top of the script before building any configuration.

### Missing `messages` key

Cause: loading a checkpoint that has no message state yet.

Fix: use `state.values.get('messages', [])`.

### Sidebar selection does not change the displayed chat

Cause: creating `temp_messages` but never assigning it to session state.

Fix:

```python
st.session_state['message_history'] = temp_messages
```

### Duplicate conversation buttons

Cause: appending the same ID repeatedly.

Fix: keep the membership check in `add_thread`.

### New messages appear in the wrong conversation

Cause: using a hard-coded thread ID or stale configuration.

Fix: create the configuration from `st.session_state['thread_id']` at submission time.

### Conversations disappear after restarting Streamlit

Cause: both `st.session_state` and `InMemorySaver` are temporary.

Fix: use persistent storage for checkpoints and the thread list.

## 16. A practical way to extend the app

When changing this program, keep these responsibilities separate:

1. ID generation decides how a conversation is named.
2. Session state decides which conversation is active and what the UI displays.
3. LangGraph configuration decides which checkpoint is read or updated.
4. Conversion code translates LangChain messages into Streamlit messages.
5. The sidebar decides how users navigate between conversations.

For example, adding delete-chat functionality would require removing the ID from `chat_threads`, clearing the active history if that ID is selected, and optionally deleting the corresponding persistent checkpoint. Keeping those responsibilities distinct makes the change easier to reason about.

## Files involved

- `streamlit2.py`: single fixed thread with streaming.
- `streamlit_frontend_threading.py`: multiple thread IDs, new-chat behavior, conversation loading, and streaming.
- `langgraph_backend_02.py`: LangGraph graph and in-memory checkpoint storage.
- `04_building_something_useful/Integrating_ui/streamlit.py`: earlier non-streaming baseline using `invoke`.
