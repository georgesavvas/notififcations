import time
import asyncio

from . import cue, volt, slack
from .tools import get_logger, get_collection


LOGGER = get_logger(__name__)

messages_coll = get_collection("notification_messages")


async def cue_summary():
    while True:
        start_time = time.time()
        cue.run_summary()
        end_time = time.time()
        elapsed_time = end_time - start_time
        LOGGER.debug(f"Cue summary for {round(elapsed_time, 1)} seconds")
        break
        # await asyncio.sleep(60)


async def cue_():
    while True:
        start_time = time.time()
        cue.run()
        end_time = time.time()
        elapsed_time = end_time - start_time
        LOGGER.debug(f"Cue run for {round(elapsed_time, 1)} seconds")
        await asyncio.sleep(10)


async def volt_():
    pass
    # while True:
    #     start_time = time.time()
    #     end_time = time.time()
    #     elapsed_time = end_time - start_time
    #     LOGGER.debug(f"Volt run for {round(elapsed_time, 1)} seconds")
    #     await asyncio.sleep(10)


def send_slack_message(msg):
    slack.send_message(
        service=msg.get("service", "hub"), text=msg["message"], user=msg["user"]
    )
    return True


send_functions = {
    "slack": send_slack_message,
}


async def main():
    # asyncio.gather(*[cue_(), volt_()])
    asyncio.gather(*[cue_summary()])
    # while True:
    #     LOGGER.debug("Sending slack messages")
    #     messages = messages_coll.find()
    #     for msg in messages:
    #         success = send_functions[msg.get("delivery", "slack")](msg)
    #         if success:
    #             messages_coll.delete_one({"id": msg["id"]})
    #     await asyncio.sleep(20)


asyncio.run(main())
