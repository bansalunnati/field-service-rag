import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../..")
    )
)
import os
from app.ingestion.ingest_documents import ingest_documents
import streamlit as st
from app.bots.policy_bot import policy_bot

st.set_page_config(
    page_title="Field Service Policy Assistant",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Field Service Policy Assistant")
st.write("Ask questions about SOPs, PPE rules, safety guidelines, and compliance policies.")
# ----------------------------
# Sidebar - Document Upload
# ----------------------------

st.sidebar.header("📄 Document Management")

uploaded_files = st.sidebar.file_uploader(
    "Upload PDF Documents",
    type=["pdf"],
    accept_multiple_files=True
)

if st.sidebar.button("Process Documents"):

    if uploaded_files:

        save_path = "data/policies"

        os.makedirs(save_path, exist_ok=True)

        for uploaded_file in uploaded_files:

            file_path = os.path.join(
                save_path,
                uploaded_file.name
            )

            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

        with st.spinner("Processing documents..."):

            docs, chunks = ingest_documents()

        st.sidebar.success(
            f"Processed {docs} pages into {chunks} chunks."
        )

    else:
        st.sidebar.warning("Please upload at least one PDF.")
# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display old messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
if prompt := st.chat_input("Ask a policy question..."):

    # Show user message
    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response
    with st.chat_message("assistant"):

        with st.spinner("Searching policies..."):

            response = policy_bot(prompt)

            st.markdown(response)

    st.session_state.messages.append(
        {"role": "assistant", "content": response}
    )