import os
import yaml
import shutil
import httpx
import uvicorn
import asyncio
from utils import Utils
from pathlib import Path
from loguru import logger
from pydantic import BaseModel
from fastapi_cache import FastAPICache
from fastapi.templating import Jinja2Templates
from fastapi_cache.decorator import cache
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi_cache.backends.inmemory import InMemoryBackend
from whatsapp_chatbot_python import GreenAPIBot, Notification
from fastapi import FastAPI, Request, HTTPException, Depends, Header, UploadFile, File, Form


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize the in-memory cache.
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")
    yield
    # Shutdown: perform any cleanup if required (none needed here).
  

# Configuration
utils = Utils()
utils.create_application_folders()
utils.load_config()

bot = GreenAPIBot(os.getenv("GREEN_API_INSTANCE"), os.getenv("GREEN_API_TOKEN"))
app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

# Rekognition classes


class ErrorResponse(BaseModel):
    detail: str
    status: str = "error"


@bot.router.message()
def message_handler(notification: Notification) -> None:
    try:
        if utils.message_type is not None:
            vault_path = utils.get_vault_path()
            if vault_path is not None:
                if utils.download_image(vault_path=vault_path):
                    logger.info("Content saved")
    except Exception as e:
        logger.error(f"Error saving files: {str(e)}")


@app.get("/chats")
@cache(expire=60)
async def get_contacts():
    """
    Fetch data from an external API and return the JSON response.

    Returns:
        dict: A dictionary containing the JSON data from the external API.

    Raises:
        HTTPException: If the external API returns a non-200 status code.
    """
    # Use an asynchronous HTTP client to make the external GET request.
    async with httpx.AsyncClient() as client:
        try:
            url = f"https://api.greenapi.com/waInstance{os.getenv('GREEN_API_INSTANCE')}/getContacts/{os.getenv('GREEN_API_TOKEN')}"
            response = await client.get(url)
            response.raise_for_status()  # Raise an exception for HTTP errors.
        except httpx.RequestError as exc:
            logger.error(str(exc))
            # This block handles network-related errors.
            raise HTTPException(status_code=500, detail=f"An error occurred while requesting data: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(str(exc))
            # This block handles responses with a non-success status code.
            raise HTTPException(status_code=exc.response.status_code, detail="Failed to fetch data from external API") from exc

    # Return the JSON content received from the external API.
    return response.json()    

@app.get("/contacts", response_class=HTMLResponse)
async def read_root(request: Request):
    # Render the HTML page using the "index.html" template
    return templates.TemplateResponse("index.html", {"request": request})


# Asynchronous wrapper to run the FastAPI server
async def start_fastapi():
    logger.debug("Starting Web Server")
    config = uvicorn.Config(app, host="0.0.0.0", port=7021, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

# Asynchronous wrapper to run the WhatsApp bot in a thread.
# If bot.run_forever() is a blocking call, wrapping it with asyncio.to_thread
# allows it to run concurrently with the FastAPI server.
async def start_whatsapp_bot():
    logger.debug("Startting Whatsapp Bot")
    await asyncio.to_thread(bot.run_forever)

# Main entry point to run both services concurrently
async def main():
    await asyncio.gather(
        start_fastapi(),
        start_whatsapp_bot()
    )

if __name__=="__main__":
    asyncio.run(main())
