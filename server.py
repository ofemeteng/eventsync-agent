from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from agent import initialize_agent  # Import initialize_agent function

app = FastAPI()

# Serve the static files (HTML, CSS, JS) from the "static" directory
app.mount("/static", StaticFiles(directory="static"), name="static")

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
