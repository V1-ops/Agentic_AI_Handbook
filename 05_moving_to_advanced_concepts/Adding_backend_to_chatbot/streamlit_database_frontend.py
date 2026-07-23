import streamlit as st
from langgraph_database_backend import chatbot, llm, get_all_threads
from langchain_core.messages import HumanMessage
import uuid

#*********** utility function*********

def generate_thread_id():
    thread_id = str(uuid.uuid4())
    return thread_id


def reset_chat():
    thread_id = generate_thread_id()
    st.session_state['thread_id'] = thread_id
    add_thread(st.session_state['thread_id'])
    st.session_state['message_history'] = []


def add_thread(thread_id):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].append(thread_id)


def load_conversation(thread_id):
    state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
    return state.values.get('messages', [])


def conversation_title(first_message: str) -> str:
    prompt = (
        "Generate a short chat title, max 6 words, for this first user message. "
        "Return only the title.\n\n"
        f"Message: {first_message}"
    )
    try:
        response = llm.invoke(prompt)
        title = response.content.strip()
        if title:
            return title
    except Exception:
        pass

    words = first_message.strip().split()
    return " ".join(words[:6]) if words else "New conversation"


def load_thread_titles():
    for thread_id in st.session_state['chat_threads']:
        if thread_id not in st.session_state['thread_titles']:
            messages = load_conversation(thread_id)
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    st.session_state['thread_titles'][thread_id] = conversation_title(msg.content)
                    break



#*******************Session setup********************
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []

if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_thread_id()

if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = get_all_threads()

if 'thread_titles' not in st.session_state:
    st.session_state['thread_titles'] = {}

add_thread(st.session_state['thread_id'])
load_thread_titles()

#********************sidebar_ui*******************
st.sidebar.title("LangGraph Chatbot")

if st.sidebar.button('New Chat'):
    reset_chat()


st.sidebar.header('My Conversations')
for thread_id in st.session_state['chat_threads'][::-1]:
    title = st.session_state['thread_titles'].get(thread_id, thread_id[:8])

    if st.sidebar.button(title, key=f"thread-{thread_id}"):
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

# loading the conversation history
for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.text(message['content'])

#{'role': 'user', 'content': 'Hi'}
#{'role': 'assistant', 'content': 'Hi=ello'}

user_input = st.chat_input('Type here')

if user_input:
    config = {'configurable': {'thread_id': st.session_state['thread_id']}}
    is_first_message = len(st.session_state['message_history']) == 0

    if is_first_message:
        st.session_state['thread_titles'][st.session_state['thread_id']] = conversation_title(user_input)

    # first add the message to message_history
    st.session_state['message_history'].append({'role': 'user', 'content': user_input})
    with st.chat_message('user'):
        st.text(user_input)

    # first add the message to message_history
    with st.chat_message('assistant'):

        ai_message = st.write_stream(
            message_chunk.content for message_chunk, metadata in chatbot.stream(
                {'messages': [HumanMessage(content=user_input)]},
                config=config,
                stream_mode= 'messages'
            )
        )

    st.session_state['message_history'].append({'role': 'assistant', 'content': ai_message})
