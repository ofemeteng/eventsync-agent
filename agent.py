import os
import sys
import time
from typing import Optional
import requests

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from cdp_langchain.agent_toolkits import CdpToolkit
from cdp_langchain.utils import CdpAgentkitWrapper
from cdp_langchain.tools import CdpTool
from langgraph.prebuilt import create_react_agent

import logging

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
eventbrite_auth_token = os.getenv("EVENTBRITE_OAUTH_TOKEN")

MINT_POAP_PROMPT = """
This tool mints a POAP to an attendee using the POAP API. It requires the attendee's address (Ethereum address, ENS, or email), the claim code (qr_hash), and the claim secret.
Always make sure to get valid claim code and claim secret before trying to mint the POAP.
Questions that can trigger this tool include:
- "Mint a POAP to attendee@example.com using claim code xyz123 and secret abc456."
- "I want to mint a POAP to attendee@example.com with qr_hash abc123 and secret xyz789."
"""


class MintPoapInput(BaseModel):
    """Input argument schema for minting a POAP."""

    address: str = Field(
        ...,
        description="The attendee's email address. Example: 'attendee@example.com'.",
        example="attendee@example.com",
    )
    qr_hash: str = Field(
        ...,
        description="The QR hash (claim code) for the POAP. Example: 'abc123def456'.",
        example="abc123def456",
    )
    secret: str = Field(
        ...,
        description="The claim secret for the POAP. Example: '1997efc56b68f5725e6737a3452d5da0c0dea497a5adff70c92f89755f266fa5'.",
        example="1997efc56b68f5725e6737a3452d5da0c0dea497a5adff70c92f89755f266fa5",
    )


def mint_poap(address: str, qr_hash: str, secret: str) -> str:
    """
    Mint a POAP to an attendee using the POAP API.

    Args:
        address (str): The attendee's email address.
        qr_hash (str): The QR hash (claim code) for the POAP.
        secret (str): The claim secret for the POAP.

    Returns:
        str: A response string with minting details or an error message.
    """

    # Load credentials from environment variables
    poap_api_key = os.getenv("POAP_API_KEY")
    poap_access_token = os.getenv("POAP_ACCESS_TOKEN")

    # Endpoint and headers
    url = "https://api.poap.tech/actions/claim-qr"
    headers = {
        "Authorization": f"Bearer {poap_access_token}",
        "X-API-Key": poap_api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Request payload
    payload = {
        "sendEmail": True,
        "address": address,
        "qr_hash": qr_hash,
        "secret": secret,
    }

    # Make the API call
    response = requests.post(url, headers=headers, json=payload)

    # Process the response
    if response.status_code == 200:
        return f"POAP minted successfully: {response.json()}"
    else:
        return f"Failed to mint POAP. Status Code: {response.status_code}. Error: {response.json()}"


GET_CLAIM_SECRET_PROMPT = """
This tool retrieves the claim secret for a POAP QR hash using the POAP API.
Always make sure to get valid claim code ie qr_hash.
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
Always make sure to get POAP event ID and the claim secret.
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
Always make sure to get Eventbrite event ID.
You can ask questions like:
- "Get the the event details for the event with event ID 1246643."
- "What is the event for ID 12345."
- "Retrieve the event details for ID 12342."
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
        str: A formatted response string with event details or an error message.
    """
    url = f"https://www.eventbriteapi.com/v3/events/{event_id}/"
    headers = {
        "Authorization": f"Bearer {eventbrite_auth_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        event_data = response.json()
        # Extract relevant details
        event_name = event_data.get("name", {}).get("text", "No name available")
        event_description = event_data.get("description", {}).get(
            "text", "No description available"
        )
        event_url = event_data.get("url", "No URL available")
        start_time = event_data.get("start", {}).get("local", "No start time available")
        end_time = event_data.get("end", {}).get("local", "No end time available")

        # Format the message
        return (
            f"Here are the details of the event:\n"
            f"Name: {event_name}\n"
            f"Description: {event_description}\n"
            f"URL: {event_url}\n"
            f"Start Time (Local): {start_time}\n"
            f"End Time (Local): {end_time}\n"
        )
    else:
        error_message = response.json().get("error_description", "Unknown error")
        return f"Failed to retrieve event. Status Code: {response.status_code}. Error: {error_message}"


LIST_ATTENDEES_PROMPT = """
This tool retrieves a list of attendees for an Eventbrite event using the Eventbrite API.
Always make sure to get Eventbrite event ID.
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


CREATE_EVENT_PROMPT = """
This tool creates a new Eventbrite event for a specified organization. It can create either a single event or 
set up a series parent for recurring events. You must provide the organization ID, event name, start and end times,
and other event details.
You can make requests like:
- "Create an event for organization 12345 called 'Tech Summit'"
- "Set up a virtual conference for org 67890"
- "Create an in-person workshop event for organization 112233"
Always make sure to provide the organization ID and all required event details.
"""


class CreateEventInput(BaseModel):
    """Input argument schema for creating an Eventbrite event.
    - organization_id is required
    - name is required
    - start_time is required
    - end_time is required
    - timezone is required
    """

    organization_id: str = Field(
        ..., description="ID of the Organization that owns the Event", example="12345"
    )
    name: str = Field(
        ..., description="The name/title of the event", example="Tech Conference 2025"
    )
    start_time: str = Field(
        ...,
        description="Event start time in ISO format (YYYY-MM-DDTHH:MM:SS)",
        example="2025-06-01T09:00:00",
    )
    end_time: str = Field(
        ...,
        description="Event end time in ISO format (YYYY-MM-DDTHH:MM:SS)",
        example="2025-06-01T17:00:00",
    )
    timezone: str = Field(
        ..., description="Timezone for the event", example="America/Los_Angeles"
    )


def create_event(
    organization_id: str,
    name: str,
    start_time: str,
    end_time: str,
    timezone: str,
) -> str:
    """
    Creates a new Eventbrite event using the Eventbrite API.

    Args:
        organization_id (str): ID of the Organization that owns the Event
        name (str): The name/title of the event
        start_time (str): Event start time in ISO format
        end_time (str): Event end time in ISO format
        timezone (str): Timezone for the event

    Returns:
        str: A message containing the created event details or error message

    Raises:
        ValueError: If incompatible options are provided
    """

    # Construct the API endpoint URL
    url = f"https://www.eventbriteapi.com/v3/organizations/{organization_id}/events/"

    # Set up the headers
    headers = {
        "Authorization": f"Bearer {eventbrite_auth_token}",
        "Content-Type": "application/json",
    }

    # Construct the event data payload
    event_data = {
        "event": {
            "name": {"html": name},
            "start": {"timezone": timezone, "utc": start_time},
            "end": {"timezone": timezone, "utc": end_time},
            "currency": "USD",  # Default currency
        }
    }

    try:
        # Make the API call
        response = requests.post(url, headers=headers, json=event_data)

        # Handle the response
        if response.status_code == 200:
            event_data = response.json()
            event_id = event_data.get("id")
            event_url = event_data.get("url")
            return (
                f"Successfully created event "
                f"with ID {event_id} for organization {organization_id}.\n"
                f"Event '{name}' scheduled from {start_time} to {end_time} ({timezone}).\n"
                f"Event URL: {event_url}"
            )
        else:
            error_detail = response.json().get("error_detail", "Unknown error")
            return f"Failed to create event. Status Code: {response.status_code}. Error: {error_detail}"

    except requests.exceptions.RequestException as e:
        return f"Error making API request: {str(e)}"
    except ValueError as e:
        return f"Error with event data: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


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

    listAttendeesTool = CdpTool(
        name="list_attendees",
        description=LIST_ATTENDEES_PROMPT,
        cdp_agentkit_wrapper=agentkit,
        args_schema=ListAttendeesInput,
        func=list_attendees,
    )

    getClaimCodesTool = CdpTool(
        name="get_claim_codes",
        description=GET_CLAIM_CODES_PROMPT,
        cdp_agentkit_wrapper=agentkit,
        args_schema=GetClaimCodesInput,
        func=get_claim_codes,
    )

    getClaimSecretTool = CdpTool(
        name="get_claim_secret",
        description=GET_CLAIM_SECRET_PROMPT,
        cdp_agentkit_wrapper=agentkit,
        args_schema=GetClaimSecretInput,
        func=get_claim_secret,
    )

    mintPoapTool = CdpTool(
        name="mint_poap",
        description=MINT_POAP_PROMPT,
        cdp_agentkit_wrapper=agentkit,
        args_schema=MintPoapInput,
        func=mint_poap,
    )

    createEventbriteTool = CdpTool(
        name="create_eventbrite_event",
        description=CREATE_EVENT_PROMPT,
        cdp_agentkit_wrapper=agentkit,
        args_schema=CreateEventInput,
        func=create_event,
    )

    # Add the tool to the list of available tools.
    tools.append(createEventbriteTool)
    tools.append(retrieveEventTool)
    tools.append(listAttendeesTool)
    tools.append(getClaimCodesTool)
    tools.append(getClaimSecretTool)
    tools.append(mintPoapTool)

    # Store buffered conversation history in memory.
    memory = MemorySaver()
    config = {"configurable": {"thread_id": "CDP Agentkit Chatbot Example!"}}

    return (
        create_react_agent(
            llm,
            tools=tools,
            checkpointer=memory,
            state_modifier="You are a helpful agent that can manage eventbrite events using eventbrite APIs. You rely on the Coinbase Developer Platform Agentkit to help you perform your tasks. You can also interact with the POAP API and send POAPs which are NFTs to verified attendees of Eventbrite events through the associated email addresses of all verified event attendees. You are empowered to interact with these external APIs using your tools. If someone asks you to do something you can't do with your currently available tools, you must say so, and encourage them to implement it themselves using the CDP SDK + Agentkit, recommend they go to docs.cdp.coinbase.com for more informaton. Be concise and helpful with your responses. Refrain from restating your tools' descriptions unless it is explicitly requested.",
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
