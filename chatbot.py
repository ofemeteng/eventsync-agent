import json
import os
import sys
import time
import requests

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from cdp_langchain.agent_toolkits import CdpToolkit
from cdp_langchain.utils import CdpAgentkitWrapper
from cdp_langchain.tools import CdpTool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from cdp import *

# Load environment variables from .env file
load_dotenv()

# Configure a file to persist the agent's CDP MPC Wallet Data.
wallet_data_file = "wallet_data_sepolia.txt"

# Load credentials from environment variables
poap_api_key = os.getenv("POAP_API_KEY")
poap_access_token = os.getenv("POAP_ACCESS_TOKEN")
eventbrite_auth_token = os.getenv("EVENTBRITE_API_KEY")

GET_CLAIM_SECRET_PROMPT = """
This tool retrieves the claim secret for a POAP QR hash using the POAP API.
Questions that can trigger this tool include:
- "Get the claim secret for the QR hash abc123def456."
- "Retrieve the claim secret for the hash xyz789abc012."
- "Fetch the claim secret using the QR hash 112233445566."
"""


class GetClaimSecretInput(BaseModel):
    """Input argument schema for retrieving the claim secret for a POAP QR hash."""

    qr_hash: str = Field(
        ...,
        description="The QR hash (claim code) to retrieve the claim secret for. Example: 'abc123def456'.",
        example="abc123def456",
    )


def get_claim_secret(qr_hash: str) -> str:
    """
    Retrieve the claim secret for a POAP QR hash using the POAP API.

    Args:
        qr_hash (str): The QR hash (claim code) to retrieve the claim secret for.

    Returns:
        str: A response string with the claim secret or an error message.
    """

    # Endpoint and headers
    url = "https://api.poap.tech/actions/claim-qr"
    headers = {
        "Authorization": f"Bearer {poap_access_token}",
        "X-API-Key": poap_api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Query parameters
    params = {"qr_hash": qr_hash}

    # Make the API call
    response = requests.get(url, headers=headers, params=params)

    # Process the response
    if response.status_code == 200:
        return f"Claim secret retrieved successfully: {response.json()}"
    else:
        return f"Failed to retrieve claim secret. Status Code: {response.status_code}. Error: {response.json()}"


GET_CLAIM_CODES_PROMPT = """
This tool retrieves claim codes (QR hashes) for a POAP event using the POAP API.
Questions that can trigger this tool include:
- "Get the claim codes for POAP event ID 182857 with the secret code 517278."
- "Retrieve the QR hashes for event 12345 with the code 987654."
- "Fetch the claim codes for POAP event 67890 using the secret code 112233."
"""


class GetClaimCodesInput(BaseModel):
    """Input argument schema for retrieving claim codes for a POAP event."""

    event_id: str = Field(
        ...,
        description="The ID of the POAP event to retrieve claim codes for. Example: '182857'.",
        example="182857",
    )
    secret_code: str = Field(
        ...,
        description="The secret code associated with the POAP event. Example: '517278'.",
        example="517278",
    )


def get_claim_codes(event_id: str, secret_code: str) -> str:
    """
    Retrieve claim codes (QR hashes) for a POAP event using the POAP API.

    Args:
        event_id (str): The ID of the POAP event.
        secret_code (str): The secret code for the POAP event.

    Returns:
        str: A response string with claim codes or an error message.
    """

    # Endpoint and headers
    url = f"https://api.poap.tech/event/{event_id}/qr-codes"
    headers = {
        "Authorization": f"Bearer {poap_access_token}",
        "X-API-Key": poap_api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Payload
    payload = {"secret_code": secret_code}

    # Make the API call
    response = requests.post(url, headers=headers, json=payload)

    # Process the response
    if response.status_code == 200:
        return f"Claim codes retrieved successfully: {response.json()}"
    else:
        return f"Failed to retrieve claim codes. Status Code: {response.status_code}. Error: {response.json()}"


# Define a new tool for retrieving an Eventbrite event.
RETRIEVE_EVENT_PROMPT = """
This tool retrieves an Eventbrite event using the Eventbrite API.
So a question like, give me the event details for the event with event ID 1246643,
what is the event for ID 12345, get or retrieve the event details for ID 12342 etc.
"""


class RetrieveEventInput(BaseModel):
    """Input argument schema for the retrieving an event."""

    event_id: str = Field(
        ...,
        description="The ID of the event to retrieve. Example: '12345'.",
        example="12345",
    )


def retrieve_event(event_id: str) -> str:
    """
    Retrieve an Eventbrite event using the Eventbrite API.

    Args:
        event_id (str): The ID of the event to retrieve.

    Returns:
        str: A response string with event details or an error message.
    """
    url = f"https://www.eventbriteapi.com/v3/events/{event_id}/"
    headers = {
        "Authorization": f"Bearer {eventbrite_auth_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return f"Event retrieved successfully: {response.json()}"
    else:
        return f"Failed to retrieve event. Status Code: {response.status_code}. Error: {response.json()}"


LIST_ATTENDEES_PROMPT = """
This tool retrieves a list of attendees for an Eventbrite event using the Eventbrite API.
You can ask questions like:
- "Get the attendees for event ID 12345."
- "List all attendees for the event with ID 67890."
- "Retrieve the attendees for the event ID 112233."
"""


class ListAttendeesInput(BaseModel):
    """Input argument schema for listing attendees by event."""

    event_id: str = Field(
        ...,
        description="The ID of the event to retrieve attendees for. Example: '12345'.",
        example="12345",
    )


def list_attendees(event_id: str) -> str:
    """
    Retrieve a list of attendees for an Eventbrite event using the Eventbrite API.

    Args:
        event_id (str): The ID of the event to retrieve attendees for.

    Returns:
        str: A response string with attendees' details or an error message.
    """
    url = f"https://www.eventbriteapi.com/v3/events/{event_id}/attendees/"
    headers = {
        "Authorization": f"Bearer {eventbrite_auth_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return f"Attendees retrieved successfully: {response.json()}"
    else:
        return f"Failed to retrieve attendees. Status Code: {response.status_code}. Error: {response.json()}"


def initialize_agent():
    """Initialize the agent with CDP Agentkit."""
    # Initialize LLM.
    llm = ChatOpenAI(
        model="llama",
        api_key="GAIA",
        base_url="https://llamatool.us.gaianet.network/v1",
    )

    wallet_data = None

    if os.path.exists(wallet_data_file):
        with open(wallet_data_file) as f:
            wallet_data = f.read()

    # Configure CDP Agentkit Langchain Extension.
    values = {}
    if wallet_data is not None:
        # If there is a persisted agentic wallet, load it and pass to the CDP Agentkit Wrapper.
        values = {"cdp_wallet_data": wallet_data}

    agentkit = CdpAgentkitWrapper(**values)

    # persist the agent's CDP MPC Wallet Data.
    wallet_data = agentkit.export_wallet()
    with open(wallet_data_file, "w") as f:
        f.write(wallet_data)

    # Initialize CDP Agentkit Toolkit and get tools.
    cdp_toolkit = CdpToolkit.from_cdp_agentkit_wrapper(agentkit)
    tools = cdp_toolkit.get_tools()

    # Add new tools here

    retrieveEventTool = CdpTool(
        name="retrieve_event",
        description=RETRIEVE_EVENT_PROMPT,
        cdp_agentkit_wrapper=agentkit,
        args_schema=RetrieveEventInput,
        func=retrieve_event,
    )

    # Add the tool to the list of available tools.
    all_tools = tools.append(retrieveEventTool)

    listAttendeesTool = CdpTool(
        name="list_attendees",
        description=LIST_ATTENDEES_PROMPT,
        cdp_agentkit_wrapper=agentkit,
        args_schema=ListAttendeesInput,
        func=list_attendees,
    )

    all_tools = tools.append(listAttendeesTool)

    getClaimCodesTool = CdpTool(
        name="get_claim_codes",
        description=GET_CLAIM_CODES_PROMPT,
        cdp_agentkit_wrapper=agentkit,
        args_schema=GetClaimCodesInput,
        func=get_claim_codes,
    )

    all_tools = tools.append(getClaimCodesTool)

    getClaimSecretTool = CdpTool(
        name="get_claim_secret",
        description=GET_CLAIM_SECRET_PROMPT,
        cdp_agentkit_wrapper=agentkit,
        args_schema=GetClaimSecretInput,
        func=get_claim_secret,
    )

    all_tools = tools.append(getClaimSecretTool)

    # Store buffered conversation history in memory.
    memory = MemorySaver()
    config = {"configurable": {"thread_id": "CDP Agentkit Chatbot Example!"}}

    # Create ReAct Agent using the LLM and CDP Agentkit tools.
    return (
        create_react_agent(
            llm,
            tools=tools,
            checkpointer=memory,
            state_modifier="You are a helpful agent that can create eventbrite events and manage those events using eventbrite APIs. You rely on the Coinbase Developer Platform Agentkit to help you perform your tasks. You can also interact with the POAP API and send POAPs which are NFTs to verified attendees of Eventbrite events by sending a unique POAP mint link to the associated email addresses of all verified event attendees. You are empowered to interact with these external APIs using your tools. If someone asks you to do something you can't do with your currently available tools, you must say so, and encourage them to implement it themselves using the CDP SDK + Agentkit, recommend they go to docs.cdp.coinbase.com for more informaton. Be concise and helpful with your responses. Refrain from restating your tools' descriptions unless it is explicitly requested.",
        ),
        config,
    )


# Autonomous Mode
def run_autonomous_mode(agent_executor, config, interval=10):
    """Run the agent autonomously with specified intervals."""
    print("Starting autonomous mode...")
    while True:
        try:
            # Provide instructions autonomously
            thought = (
                "Be creative and do something interesting on the blockchain. "
                "Choose an action or set of actions and execute it that highlights your abilities."
            )

            # Run agent in autonomous mode
            for chunk in agent_executor.stream(
                {"messages": [HumanMessage(content=thought)]}, config
            ):
                if "agent" in chunk:
                    print(chunk["agent"]["messages"][0].content)
                elif "tools" in chunk:
                    print(chunk["tools"]["messages"][0].content)
                print("-------------------")

            # Wait before the next action
            time.sleep(interval)

        except KeyboardInterrupt:
            print("Goodbye Agent!")
            sys.exit(0)


# Chat Mode
def run_chat_mode(agent_executor, config):
    """Run the agent interactively based on user input."""
    print("Starting chat mode... Type 'exit' to end.")
    while True:
        try:
            user_input = input("\nUser: ")
            if user_input.lower() == "exit":
                break

            # Run agent with the user's input in chat mode
            for chunk in agent_executor.stream(
                {"messages": [HumanMessage(content=user_input)]}, config
            ):
                if "agent" in chunk:
                    print(chunk["agent"]["messages"][0].content)
                elif "tools" in chunk:
                    print(chunk["tools"]["messages"][0].content)
                print("-------------------")

        except KeyboardInterrupt:
            print("Goodbye Agent!")
            sys.exit(0)


# Mode Selection
def choose_mode():
    """Choose whether to run in autonomous or chat mode based on user input."""
    while True:
        print("\nAvailable modes:")
        print("1. chat    - Interactive chat mode")
        print("2. auto    - Autonomous action mode")

        choice = input("\nChoose a mode (enter number or name): ").lower().strip()
        if choice in ["1", "chat"]:
            return "chat"
        elif choice in ["2", "auto"]:
            return "auto"
        print("Invalid choice. Please try again.")


def main():
    """Start the chatbot agent."""
    agent_executor, config = initialize_agent()

    mode = choose_mode()
    if mode == "chat":
        run_chat_mode(agent_executor=agent_executor, config=config)
    elif mode == "auto":
        run_autonomous_mode(agent_executor=agent_executor, config=config)


if __name__ == "__main__":
    print("Starting Agent...")
    main()
