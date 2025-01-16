import os
import requests
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from agent import initialize_agent  # Import initialize_agent function

# Load environment variables
ENV_FILE = ".env"
load_dotenv(ENV_FILE)

# POAP Constants loaded from the .env file
POAP_CLIENT_ID = os.getenv("POAP_CLIENT_ID")
POAP_CLIENT_SECRET = os.getenv("POAP_CLIENT_SECRET")


def update_poap_access_token():
    """
    Fetches a new POAP access token from the POAP API and updates the .env file.
    """
    try:
        if not POAP_CLIENT_ID or not POAP_CLIENT_SECRET:
            raise ValueError(
                "POAP_CLIENT_ID and POAP_CLIENT_SECRET must be set in the .env file."
            )

        # POAP OAUTH API endpoint and payload
        auth_url = "https://auth.accounts.poap.xyz/oauth/token"
        payload = {
            "audience": "https://api.poap.tech",
            "grant_type": "client_credentials",
            "client_id": POAP_CLIENT_ID,
            "client_secret": POAP_CLIENT_SECRET,
        }
        headers = {"Content-Type": "application/json"}

        response = requests.post(auth_url, json=payload, headers=headers)
        response.raise_for_status()  # Raise an error if the request fails
        new_token = response.json().get("access_token")

        if not new_token:
            raise ValueError("No access token found in the response.")

        # Update the .env file
        updated_lines = []
        with open(ENV_FILE, "r") as file:
            for line in file:
                if line.startswith("POAP_ACCESS_TOKEN="):
                    updated_lines.append(f"POAP_ACCESS_TOKEN={new_token}\n")
                else:
                    updated_lines.append(line)

        with open(ENV_FILE, "w") as file:
            file.writelines(updated_lines)

        # Reload the updated token into the environment
        os.environ["POAP_ACCESS_TOKEN"] = new_token

        print("POAP access token updated successfully!")

    except Exception as e:
        print(f"Failed to update POAP access token: {e}")


app = FastAPI()

# Initialize the APScheduler
scheduler = BackgroundScheduler()

# Schedule the token update function to run daily at midnight
scheduler.add_job(
    update_poap_access_token,
    trigger=CronTrigger(hour=0, minute=0),
    id="update_poap_token",  # Unique ID for the job
    replace_existing=True,
)

# Start the scheduler
scheduler.start()


@app.on_event("shutdown")
def shutdown_event():
    # Shut down the scheduler when the app stops
    scheduler.shutdown()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Query(BaseModel):
    message: str


# Initialize the agent
agent_executor, config = initialize_agent()


# Redirect root URL to the GitHub repo
@app.get("/")
async def serve_index():
    return RedirectResponse(url="https://github.com/ofemeteng/eventsync-agent")


@app.post("/chat")
async def chat(query: Query):
    user_message = query.message
    response = ""
    for chunk in agent_executor.stream(
        {"messages": [HumanMessage(content=user_message)]}, config
    ):
        if "agent" in chunk:
            response += chunk["agent"]["messages"][0].content
    return {"response": response}
