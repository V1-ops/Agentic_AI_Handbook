# Streamlit Streaming Upgrade

This folder contains `streamlit2.py`, an upgraded version of the earlier Streamlit chat UI from:

`../04_building_something_useful/Integrating_ui/streamlit.py`

The main improvement is that the assistant response is now streamed live instead of appearing only after the full response is generated.

## What Changed

### 1. Backend import changed

Old file:

```python
from langgraph_backend import chatbot
```

New file:

```python
from langgraph_backend_02 import chatbot
```

`streamlit2.py` uses the newer backend module for the advanced concept example.

### 2. Response generation changed from `invoke` to `stream`

Old `streamlit.py` waits for the full response:

```python
response = chatbot.invoke(
    {'messages': [HumanMessage(content=user_input)]},
    config=CONFIG
)
ai_message = response['messages'][-1].content
```

New `streamlit2.py` streams message chunks:

```python
ai_message = st.write_stream(
    message_chunk.content for message_chunk, metadata in chatbot.stream(
        {'messages': [HumanMessage(content=user_input)]},
        config={'configurable': {'thread_id': 'thread-1'}},
        stream_mode='messages'
    )
)
```
.stream() method (from the LangChain ecosystem). When you call .stream() on a LangGraph workflow using stream_mode="messages", it yields a tuple exactly containing those two elements: (message_chunk, metadata)


This means the user can see the assistant response being generated token by token or chunk by chunk.

### 3. Streamlit now renders the assistant response while it is being produced

The new code wraps the streaming logic inside:

```python
with st.chat_message('assistant'):
```

Then `st.write_stream()` writes chunks directly into the assistant chat bubble.

In the older version, the app first generated the whole response and only then displayed it using:

```python
st.text(ai_message)
```

### 4. Assistant message history is stored correctly

In `streamlit2.py`, after streaming finishes, the final assistant message returned by `st.write_stream()` is saved:

```python
st.session_state['message_history'].append({
    'role': 'assistant',
    'content': ai_message
})
```

This allows previous assistant messages to appear again when Streamlit reruns the script.

In the older file, the assistant response was appended using the `user` role:

```python
st.session_state['message_history'].append({
    'role': 'user',
    'content': ai_message
})
```

That made the assistant response appear as if it came from the user. The new file fixes this by saving it with the `assistant` role.

## Why Streaming Is Better

Without streaming:

1. User sends a message.
2. App waits silently while the model generates the full answer.
3. Full answer appears at once.

With streaming:

1. User sends a message.
2. Assistant chat bubble appears immediately.
3. Response text is displayed progressively as chunks arrive.
4. Final streamed text is saved into session history.

This creates a smoother chat experience and makes the app feel more responsive.

## Key Code Pattern

The important streaming pattern is:

```python
with st.chat_message('assistant'):
    ai_message = st.write_stream(
        message_chunk.content for message_chunk, metadata in chatbot.stream(
            {'messages': [HumanMessage(content=user_input)]},
            config=CONFIG,
            stream_mode='messages'
        )
    )
```

Use `chatbot.stream()` when you want incremental output from LangGraph, and use `st.write_stream()` when you want Streamlit to display that incremental output in the UI.
