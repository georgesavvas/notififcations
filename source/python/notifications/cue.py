import fnmatch
import datetime
from uuid import uuid4

from .tools import get_logger, get_collection, get_slackbot_collection


LOGGER = get_logger(__name__)

rules_coll = get_collection("notification_rules")
farm_coll = get_slackbot_collection("store_farm")
renders_submitted_coll = get_collection("renders_submitted")
renders_failing_coll = get_collection("renders_failing")
renders_finished_coll = get_collection("renders_finished")
messages_coll = get_collection("notification_messages")


def is_rule_relevant(rule, job):
    rule_match = False
    job_name = job["name"]
    for target in rule["targets"]:
        if fnmatch.fnmatch(job_name, target):
            rule_match = True
            break
    if not rule_match:
        return False
    filters = rule.get("filters", {})
    users_filter = filters.get("users", [])
    if users_filter and job["user"] not in users_filter:
        return False
    return True


def process_submitted(job):
    name = job["name"]
    rules = rules_coll.find({"notified_for": "render_submitted"})
    existing_data = renders_submitted_coll.find_one({"name": name})
    for rule in rules:
        if not is_rule_relevant(rule, job):
            continue
        if existing_data:
            if rule["user"] in existing_data["users"]:
                # Already notified
                continue
        now = datetime.datetime.now()
        now_ts = datetime.datetime.timestamp(now)
        finished_ts = job["startTime"]
        mins = abs(now_ts - finished_ts) / 60
        if mins > 10:
            # Too old, ignore
            continue
        user_formatted = "you" if rule["user"] == job["user"] else job["user"]
        existing_query = {
            "rule_type": rule["notified_for"],
            "user": rule["user"],
            "delivery": rule["delivery"],
        }
        existing_message = messages_coll.find_one(existing_query)
        if existing_message:
            updated_message = (
                existing_message["message"].replace(
                    "*Farm job submitted*", "*Farm jobs submitted*"
                )
                + f"\n`{name}` by {user_formatted}"
            )
            messages_coll.update_one(
                existing_query, {"$set": {"message": updated_message}}
            )
        else:
            messages_coll.insert_one(
                {
                    "id": str(uuid4()),
                    "rule_type": rule["notified_for"],
                    "asset": name,
                    "user": rule["user"],
                    "message": f"*Farm job submitted*\n`{name}` by {user_formatted}",
                    "timestamp": now_ts,
                    "delivery": rule["delivery"],
                    "service": "cue",
                }
            )
        renders_submitted_coll.update_one(
            {"name": name}, {"$push": {"users": rule["user"]}}, upsert=True
        )


def process_failing(job):
    name = job["name"]
    if job["deadFrames"] == 0:
        # Is not failing, remove existing failing locks
        renders_failing_coll.delete_many({"name": name})
        return
    rules = rules_coll.find({"notified_for": "render_failing"})
    existing_data = renders_failing_coll.find_one({"name": name})
    for rule in rules:
        if not is_rule_relevant(rule, job):
            continue
        if existing_data:
            if rule["user"] in existing_data["users"]:
                # Already notified
                continue
        now = datetime.datetime.now()
        now_ts = datetime.datetime.timestamp(now)
        user_formatted = "you" if rule["user"] == job["user"] else job["user"]
        existing_query = {
            "rule_type": rule["notified_for"],
            "user": rule["user"],
            "delivery": rule["delivery"],
        }
        existing_message = messages_coll.find_one(existing_query)
        if existing_message:
            updated_message = (
                existing_message["message"].replace(
                    "*Farm job failing*", "*Farm jobs failing*"
                )
                + f"\n`{name}` by {user_formatted}"
            )
            messages_coll.update_one(
                existing_query, {"$set": {"message": updated_message}}
            )
        else:
            messages_coll.insert_one(
                {
                    "id": str(uuid4()),
                    "rule_type": rule["notified_for"],
                    "asset": name,
                    "user": rule["user"],
                    "message": f"*Farm job failing*\n`{name}` by {user_formatted}",
                    "timestamp": now_ts,
                    "delivery": rule["delivery"],
                    "service": "cue",
                }
            )
        renders_failing_coll.update_one(
            {"name": name}, {"$push": {"users": rule["user"]}}, upsert=True
        )


def process_finished(job):
    name = job["name"]
    if job["state"] == "0":
        # Is not finished, remove existing finished locks
        existing_data = renders_finished_coll.delete_many({"name": name})
        return
    if job["state"] != "1":
        return
    rules = rules_coll.find({"notified_for": "render_finished"})
    existing_data = renders_finished_coll.find_one({"name": name})
    for rule in rules:
        if not is_rule_relevant(rule, job):
            continue
        if existing_data:
            if rule["user"] in existing_data["users"]:
                # Already notified
                continue
        now = datetime.datetime.now()
        now_ts = datetime.datetime.timestamp(now)
        finished_ts = job["stopTime"]
        secs = abs(now_ts - finished_ts)
        if secs > 30:
            # Too old, ignore
            print(rule["id"], name, f"was submitted {secs} seconds ago, ignoring...")
            continue
        user_formatted = "you" if rule["user"] == job["user"] else job["user"]
        existing_query = {
            "rule_type": rule["notified_for"],
            "user": rule["user"],
            "delivery": rule["delivery"],
        }
        existing_message = messages_coll.find_one(existing_query)
        if existing_message:
            updated_message = (
                existing_message["message"].replace(
                    "*Farm job finished*", "*Farm jobs finished*"
                )
                + f"\n`{name}` by {user_formatted}"
            )
            messages_coll.update_one(
                existing_query, {"$set": {"message": updated_message}}
            )
        else:
            messages_coll.insert_one(
                {
                    "id": str(uuid4()),
                    "rule_type": rule["notified_for"],
                    "user": rule["user"],
                    "message": f"*Farm job finished*\n`{name}` by {user_formatted}.",
                    "timestamp": now_ts,
                    "delivery": rule["delivery"],
                    "service": "cue",
                }
            )
        renders_finished_coll.update_one(
            {"name": name}, {"$push": {"users": rule["user"]}}, upsert=True
        )


def run():
    farm_data = farm_coll.find_one(sort=[("_id", -1)])
    if not farm_data:
        LOGGER.error("No farm data found, aborting...")
        return
    for job in farm_data["data"]["jobs"]:
        process_submitted(job)
        process_failing(job)
        process_finished(job)
