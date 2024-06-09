import os
import logging

import colorlog
import pymongo


ENV = os.environ
MONGO_URL = ENV["MONGO_URL"]

logFormatter = colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s - %(name)-8s - %(levelname)-8s - %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
LOGGER = colorlog.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
ch = colorlog.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(logFormatter)
LOGGER.handlers = []
LOGGER.addHandler(ch)
LOGGER.propagate = False


def new_mongo_client(address=f"mongodb://{MONGO_URL}"):
    return pymongo.MongoClient(address)


MONGODB_SLACKBOT = new_mongo_client("mongodb://slackbot:27117")
MONGODB = new_mongo_client()


def get_logger(name):
    logger = colorlog.getLogger(name)
    logger.setLevel(logging.DEBUG)
    ch = colorlog.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(logFormatter)
    logger.handlers = []
    logger.addHandler(ch)
    logger.propagate = False
    return logger


def get_db():
    DB = MONGODB["hub"]
    return DB


def get_collection(name):
    DB = get_db()
    coll = DB[name]
    return coll


def get_slackbot_db():
    DB = MONGODB_SLACKBOT["et_hub"]
    return DB


def get_slackbot_collection(name):
    DB = get_slackbot_db()
    coll = DB[name]
    return coll


def get_mongo_client():
    return MONGODB
