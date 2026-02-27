import streamlit as st
import os
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Initialize Mistral client
client = MistralClient(api_key=os.getenv("MISTRAL_API_KEY"))

# Define avatars and their personalities
AVATARS = {
    "Therapist": {
        "description": "A compassionate therapist who provides professional guidance and support",
        "system_prompt": """You are a compassionate and professional therapist. Your role is to:
        1. Provide empathetic support and guidance
        2. Help users develop coping strategies
        3. Encourage professional help when needed
        4. Maintain appropriate boundaries
        5. Focus on evidence-based therapeutic approaches"""
    },
    "Life Coach": {
        "description": "An energetic life coach focused on personal growth and achievement",
        "system_prompt": """You are an enthusiastic life coach. Your role is to:
        1. Help users set and achieve personal goals
        2. Provide motivation and accountability
        3. Share practical strategies for self-improvement
        4. Focus on building confidence and resilience
        5. Encourage positive thinking and action"""
    },
    "Friend": {
        "description": "A supportive friend who listens and offers understanding",
        "system_prompt": """You are a caring and understanding friend. Your role is to:
        1. Provide emotional support and validation
        2. Listen actively and show empathy
        3. Share personal experiences when relevant
        4. Offer practical advice from a friend's perspective
        5. Maintain a warm and casual conversation style"""
    }
}

# Crisis detection keywords
CRISIS_KEYWORDS = [
    "suicide", "kill myself", "end it all", "no reason to live",
    "want to die", "better off dead", "hurt myself"
]

def detect_crisis(message):
    """Detect if the message indicates a crisis situation."""
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in CRISIS_KEYWORDS)

def get_crisis_response():
    """Return emergency resources and crisis response."""
    return """
    I'm concerned about your safety. Please know that you're not alone, and help is available:
    
    1. National Suicide Prevention Lifeline: 988
    2. Crisis Text Line: Text HOME to 741741
    3. Emergency Services: 911
    
    These services are available 24/7 and are free and confidential.
    Would you like me to help you connect with any of these resources?
    """

def get_bot_response(messages, avatar):
    """Get response from Mistral AI model."""
    try:
        chat_response = client.chat(
            model="mistral-tiny",
            messages=messages
        )
        return chat_response.choices[0].message.content
    except Exception as e:
        return f"I apologize, but I'm having trouble connecting right now. Please try again later. Error: {str(e)}"

def main():
    st.title("Mental Health Ease Bot")
    st.write("Your AI companion for mental well-being and personal growth")

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "selected_avatar" not in st.session_state:
        st.session_state.selected_avatar = "Therapist"

    # Avatar selection
    st.sidebar.title("Choose Your Companion")
    selected_avatar = st.sidebar.selectbox(
        "Select an avatar",
        list(AVATARS.keys()),
        index=list(AVATARS.keys()).index(st.session_state.selected_avatar)
    )
    
    if selected_avatar != st.session_state.selected_avatar:
        st.session_state.selected_avatar = selected_avatar
        st.session_state.messages = []

    # Display avatar description
    st.sidebar.write(AVATARS[selected_avatar]["description"])

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # Chat input
    if prompt := st.chat_input("How are you feeling today?"):
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        # Check for crisis situation
        if detect_crisis(prompt):
            crisis_response = get_crisis_response()
            st.session_state.messages.append({"role": "assistant", "content": crisis_response})
            with st.chat_message("assistant"):
                st.write(crisis_response)
        else:
            # Prepare messages for the model
            messages = [
                ChatMessage(role="system", content=AVATARS[selected_avatar]["system_prompt"])
            ]
            for msg in st.session_state.messages:
                messages.append(ChatMessage(role=msg["role"], content=msg["content"]))

            # Get and display bot response
            with st.chat_message("assistant"):
                with st.spinner(f"{selected_avatar} is thinking..."):
                    response = get_bot_response(messages, selected_avatar)
                st.write(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

    # Display emergency resources
    st.sidebar.markdown("---")
    st.sidebar.subheader("Emergency Resources")
    st.sidebar.write("If you're in crisis, please contact:")
    st.sidebar.write("- National Suicide Prevention Lifeline: 988")
    st.sidebar.write("- Crisis Text Line: Text HOME to 741741")
    st.sidebar.write("- Emergency Services: 911")

if __name__ == "__main__":
    main() 