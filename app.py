"""Evaluator-facing Streamlit chat with visible tool routing."""

from __future__ import annotations

import asyncio

import streamlit as st

from emporio.agent import AgentDependencies, ToolCallTrace, build_agent, run_turn
from emporio.config import MissingConfigurationError, get_settings
from emporio.ingest_policies import OpenAIEmbedder
from emporio.retrieval import PolicyRetriever

st.set_page_config(page_title="Empório da Música", page_icon="🎸", layout="centered")
st.title("🎸 Empório da Música")
st.caption("Sua música começa aqui — atendimento virtual com dados e políticas da loja.")


def _initialize_session() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "model_history" not in st.session_state:
        st.session_state.model_history = []
    if "agent" in st.session_state:
        return

    settings = get_settings()
    api_key = settings.require_openai_api_key()
    retriever = PolicyRetriever(
        settings.chroma_path,
        OpenAIEmbedder(api_key, settings.embedding_model),
    )
    st.session_state.agent = build_agent(settings, retriever)
    st.session_state.dependencies = AgentDependencies(settings, retriever)


try:
    _initialize_session()
except MissingConfigurationError as error:
    st.error(str(error))
    st.stop()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("tool_calls"):
            with st.expander("🔧 Consultas realizadas"):
                for tool_call in message["tool_calls"]:
                    st.code(
                        f"{tool_call['name']}({tool_call['arguments']})",
                        language="python",
                    )

if prompt := st.chat_input("Como posso ajudar com seu instrumento ou pedido?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        streamed: list[str] = []
        visible_calls: list[ToolCallTrace] = []

        def on_text(delta: str) -> None:
            streamed.append(delta)
            placeholder.markdown("".join(streamed) + "▌")

        def on_tool_call(trace: ToolCallTrace) -> None:
            visible_calls.append(trace)

        try:
            result = asyncio.run(
                run_turn(
                    st.session_state.agent,
                    st.session_state.dependencies,
                    prompt,
                    st.session_state.model_history,
                    on_text=on_text,
                    on_tool_call=on_tool_call,
                )
            )
        except Exception as error:
            placeholder.empty()
            st.error(f"Não foi possível concluir o atendimento: {error}")
        else:
            placeholder.markdown(result.output)
            st.session_state.model_history = result.history
            serialized_calls = [
                {"name": trace.name, "arguments": trace.arguments} for trace in visible_calls
            ]
            if serialized_calls:
                with st.expander("🔧 Consultas realizadas"):
                    for tool_call in serialized_calls:
                        st.code(
                            f"{tool_call['name']}({tool_call['arguments']})",
                            language="python",
                        )
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": result.output,
                    "tool_calls": serialized_calls,
                }
            )
