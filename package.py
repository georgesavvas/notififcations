# -*- coding: utf-8 -*-

name = "notifications"

version = open("VERSION").read().strip()

uuid = "5d233adb-3f04-4abd-9d91-3b3df1b5c3ad"

description = ""

requires = []

build_command = "{root}/build.sh"


def commands():
    global env
    env.PATH.append("{root}/bin")
    env.PYTHONPATH.append("{root}/python")
