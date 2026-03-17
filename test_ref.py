import streamlit as st

# Simulate streamlit session state
class MockState(dict):
    def __getattr__(self, item): return self[item]
    def __setattr__(self, k, v): self[k] = v

state = MockState(messages=["msg1"])

def run():
    messages = state.messages
    messages.append("msg2")
    print(f"Append works: {state.messages}")

    # Re-assignment
    state.messages = []
    messages = []
    messages.append("welcome")
    print(f"Re-assignment fails state: {state.messages}")
    print(f"Re-assignment local: {messages}")

run()
