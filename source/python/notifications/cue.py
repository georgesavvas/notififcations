import fnmatch
import datetime
from uuid import uuid4
from pathlib import Path

from . import slack
from .tools import get_logger, get_collection, get_slackbot_collection



LOGGER = get_logger(__name__)

rules_coll = get_collection("notification_rules")
farm_coll = get_slackbot_collection("store_farm")
renders_coll = get_slackbot_collection("store_renders")
renders_submitted_coll = get_collection("renders_submitted")
renders_failing_coll = get_collection("renders_failing")
renders_finished_coll = get_collection("renders_finished")
messages_coll = get_collection("notification_messages")
notification_times_coll = get_collection("notification_times")


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


def get_vri(job):
    for layer in job.get("layers", []):
        paths = layer.get("outputPaths", [])
        for path in paths:
            if not path or not path.startswith("/jobs"):
                return ""
            path = Path(path)
            asset_dir = path.parent
            vri_path = asset_dir / ".vri"
            vri = ""
            if vri_path.is_file():
                return vri_path.read_text()
    return ""


def run():
    farm_data = farm_coll.find_one(sort=[("_id", -1)])
    if not farm_data:
        LOGGER.error("No farm data found, aborting...")
        return
    for job in farm_data["data"]["jobs"]:
        process_submitted(job)
        process_failing(job)
        process_finished(job)


def run_summary():
    # rules = rules_coll.find({"notified_for": "farm_summary"})
    "theom, georgeg, alexga, yousef, tri"
    rules = [{
        "notified_for": "farm_summary",
        "user": "dorianne",
        "times": [0, 0]
    }]
    now = datetime.datetime.now()
    yesterday_date = now - datetime.timedelta(days=3)
    for rule in rules:
        user = rule["user"]
        times = rule.get("times")
        if not times:
            times = notification_times_coll.find_one({"user": user})
        if not times:
            LOGGER.error(f"No times found for user {user}, aborting...")
            continue
        specific_time = datetime.datetime.strptime("21:00", "%H:%M").time()
        yesterday_specific_time = datetime.datetime.combine(yesterday_date, specific_time)
        logoff_ts = yesterday_specific_time.timestamp()
        print(user, "time:", yesterday_specific_time)
        finished_renders = list(renders_coll.find({"user": user, "startTime": {"$gt": logoff_ts}}))
        farm_data = farm_coll.find_one(sort=[("_id", -1)])
        if not farm_data:
            farm_data = []
        running_renders = [render for render in farm_data["data"]["jobs"] if render["user"] == user and render["startTime"] > logoff_ts]
        if not running_renders and not finished_renders:
            LOGGER.warning(f"User {user} had no renders since {yesterday_specific_time}, skipping...")
            continue
        shows = {}
        if running_renders and finished_renders:
            for state, renders in [["running", running_renders], ["finished", finished_renders]]:
                for render in renders:
                    if not render.get("show") or not render.get("shot"):
                        continue
                    if render["shot"].startswith("none_"):
                        continue
                    if not shows.get(render["show"]):
                        shows[render["show"]] = {"finished": [], "running": []}
                    if render["shot"] in shows[render["show"]]["running"]:
                        continue
                    if render["shot"] in shows[render["show"]][state]:
                        continue
                    shows[render["show"]][state].append(render["shot"])
        blocks = get_summary_blocks(finished_renders, running_renders, shows)
        slack.send_message(
            service="cue", text="Your Farm Summary", blocks=blocks, user="george"
        )


def get_running_time(job):
        start = job["startTime"]
        stop = job["stopTime"]
        td = stop - start
        return td


def format_time(sec):
        sec = int(sec)
        hours = sec // 3600
        mins = (sec % 3600) // 60
        secs = (sec % 3600) % 60

        if hours:
            final = "{}h {}m {}s".format(hours, mins, secs)
        elif mins:
            final = "{}m {}s".format(mins, secs)
        else:
            final = "{}s".format(secs)
        return final


def get_shots_text(shots, show=None):
    text = f"\n`{show}` shot" if show else "Shot"
    finished = shots.get("finished")
    running = shots.get("running")
    finished_amount = len(finished)
    running_amount = len(running)
    if finished and running:
        if finished_amount > 1:
            text += "s "
            text += ", ".join([f"`{shot}`" for shot in finished[:-1]]) + f" and `{finished[-1]}`"
            text += " are done while "
        else:
            text += f" `{finished[0]}` is done while "
        if running_amount > 1:
            text += ", ".join([f"`{shot}`" for shot in running[:-1]]) + f" and `{running[-1]}` are still running."
        else:
            text += f"`{running[0]}` is still running."
    elif finished:
        if not show:
            return "All shots are done."
        if finished_amount > 1:
            text += "shots "
        text += "are all done."
    elif running:
        if not show:
            return "All shots are still running."
        if running_amount > 1:
            text += "shots "
        text += "are all still running."
    print(text)
    return text


def get_render_cores(job):
    cores = 0
    for layer in job.get("layers", []):
        cores += layer.get("currentCores", 0)
    return cores


def get_render_progress(job):
    layers = job.get("layers", [])
    total_percent = sum(layer.get("percentCompleted", 100) for layer in layers)
    return round(total_percent / len(layers))


def get_summary_blocks(finished, running, shows):
    running_amount = len(running)
    finished_amount = len(finished)
    renders_amount = running_amount + finished_amount
    finished_text = "all" if finished_amount == renders_amount else f"{finished_amount}"
    renders_text = "render" if renders_amount == 1 else "renders"
    shows_amount = len(shows)
    shows_text = ""
    if shows_amount == 1:
        show = list(shows.keys())[0]
        shows_text = " " + get_shots_text(shows[show])
    elif shows_amount > 1:
        shows_text = " " + "\n".join([get_shots_text(shots, show) for show, shots in shows.items()])
    if renders_amount == 0:
        return [{
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": ":sunny: Morning! You had no renders on the farm last night.",
        }
    }]
    else:
        intro_text = f"You had {renders_amount} {renders_text} on the farm, {finished_text} of which are finished.{shows_text}"
    finished_pattern = ">_{name}_\n>`{vri}`\n>Start-to-finish: {render_time}\n\n"
    running_pattern = ">`{name}`\n>Progress: {progress}%\n>Current power: {cores_text}\n\n"
    finished_text = ""
    running_text = ""
    for render in finished[:10]:
        finished_text += finished_pattern.format(
            name=render["name"],
            vri=get_vri(render) or "Couldn't get VRI",
            render_time=format_time(get_running_time(render)),
        )
    if finished_amount > 10:
        finished_text += f"and {finished_amount - 10} more..."
    for render in running[:10]:
        cores_text = f"{get_render_cores(render)} cores"
        running_text += running_pattern.format(
            name=render["name"],
            progress=get_render_progress(render),
            cores_text=cores_text,
        )
    if running_amount > 10:
        running_text += f"and {running_amount - 10} more..."
    # spacer_block = {
    #     "type": "section",
    #     "text": {
    #         "type": "plain_text",
    #         "text": " ",
    #     }
    # }
    spacer_block = {
        "type": "divider"
    }
    # morning_block = {
    #     "type": "section",
    #     "text": {
    #         "type": "mrkdwn",
    #         "text": ":sunny: Morning! Here's your farm summary since yesterday",
    #     },
    #     "accessory": {
    #         "type": "timepicker",
    #         "initial_time": "21:00",
    #         "placeholder": {
    #             "type": "plain_text",
    #             "text": "Select time",
    #             "emoji": True
    #         },
    #         "action_id": "timepicker-action",
    #     }
    # }
    morning_block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": ":sunny: Morning! Here's your farm summary since yesterday 21:00.",
        }
    }
    intro_block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": intro_text,
        }
    }
    finished_header_text = ":white_check_mark: Here's what's finished:"
    if running_amount:
        if finished_amount == 1:
            finished_header_text = ":white_check_mark: Here it is:"
        else:
            finished_header_text = ":white_check_mark: Here they are:"
    finished_header_block = {
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": finished_header_text,
			}
		}
    finished_block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": finished_text,
        }
    }
    running_header_text = ":woman_in_lotus_position: Here's what you're waiting for:"
    if finished_amount:
        if running_amount == 1:
            running_header_text = ":woman_in_lotus_position: The remaining one is:"
        else:
            running_header_text = ":woman_in_lotus_position: The remaining ones are:"
    running_header_block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": running_header_text,
        }
    }
    running_block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": running_text,
        }
    }
    final = [
        morning_block,
        intro_block,
    ]
    if finished_text:
        final += [spacer_block, finished_header_block, finished_block]
    if running_text:
        final += [spacer_block, running_header_block, running_block]
    return final
