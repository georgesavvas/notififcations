from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import os
import sys
import shutil
from os.path import dirname, basename, join, exists
from subprocess import check_output

try:
    from invoke import ctask as task
except ImportError:
    # on centos 7 the latest version of invoke ctask are removed.
    # the default task is now a ctask
    from invoke import task


if sys.version_info > (3, 0):

    def execfile(filename, globals=None, locals=None):
        # based on these 2 threads
        # https://stackoverflow.com/questions/436198/what-is-an-alternative-to-execfile-in-python-3
        # https://stackoverflow.com/questions/6357361/alternative-to-execfile-in-python-3/6357418#6357418
        if globals is None:
            globals = {}
        globals.update({"__file__": filename, "__name__": "__main__"})
        with open(filename, "rb") as source_file:
            exec(compile(source_file.read(), filename, "exec"), globals, locals)


# name of the project
NAME = basename(dirname(__file__))
# execute packages package.py, this will set `version` and `name` variables
execfile(join(dirname(__file__), "package.py"), globals())


@task
def clean(ctx):
    """Remove the build directory."""
    local_path = check_output(
        "rez config local_packages_path", shell=True, universal_newlines=True,
    )
    local_path = local_path.strip()
    ctx.run("rm -rfv build {0}/{1}/{2}".format(local_path, NAME, version))


@task(pre=[clean])
def cbuild(ctx):
    """Perform a clean build of the package and place in ~/packages"""
    ctx.run("rez-build -i")


@task(default=True)
def build(ctx):
    """Perform a build of the package and place in ~/packages"""
    ctx.run("rez-build -i")


@task(pre=[clean, build])
def devbuild(ctx):
    """Perform a build of the package and place in ~/packages"""
    source_dir = os.getcwd()
    local_path = check_output(
        "rez config local_packages_path", shell=True, universal_newlines=True,
    )
    local_path = local_path.strip()
    location = "{0}/{1}/{2}".format(local_path, NAME, version)
    location_paths = os.listdir(location)
    paths = os.listdir("source")
    to_link = set(paths).intersection(set(location_paths))
    for link in to_link:
        src = os.path.join(source_dir, 'source', link)
        target = os.path.join(location, link)
        if os.path.islink(target):
            os.remove(target)
        else:
            shutil.rmtree(target)
        os.symlink(src, target)


@task
def meld(ctx):
    local_path = check_output(
        "rez config local_packages_path", shell=True, universal_newlines=True,
    )
    local_path = local_path.strip()
    ctx.run("meld {0}/{1}/{2} source".format(local_path, NAME, version))


@task
def flake(ctx):
    ctx.run("flake8 --ignore=F401 --exclude tasks.py,package.py,docs")


@task
def test(ctx, coverage='', path='', tests=''):
    path = path or 'test'
    local_path = check_output(
        "rez config local_packages_path", shell=True, universal_newlines=True,
    )
    local_path = local_path.strip()
    coverage = coverage or '{0}/{1}'.format(local_path, NAME)
    tests = " -k {} ".format(tests) if tests else ""

    ctx.run(
        "rez env {0}-{1} pytest pytest_cov mock-1.0.1 "
        "-- py.test --cov-report term-missing --cov {2} {3} {4}".format(
            NAME, version, coverage, path, tests
        )
    )


@task(pre=[clean])
def release(ctx, extra='--skip-repo-errors', force=False):
    location = '/software/rez/packages/int/{0}/{1}/package.py'.format(name, version)
    if exists(location) and not force:
        print('Trying to release again, Skipping')
    else:
        location = '/software/rez/packages/int/{0}/{1}'.format(name, version)
        if exists(location):
            print('Re-release previously failed release', name, version)

            tname = '/software/rez/packages/int/{0}/.BAK_{1}'.format(name, version)
            if exists(tname):
                ctx.run('sudo rm -rf {0}'.format(tname))

            run = ctx.run('sudo mv -fv "{0}" {1}'.format(location, tname), warn=True)
            if run.exited:
                failure = True
            else:
                print('releasing')
                failure = rel_wrapper(ctx, extra)

            if failure:
                print('Failure! restoring!')
                ctx.run('sudo rm -rf {0}'.format(location))
                ctx.run('sudo mv -fv {0} "{1}"'.format(tname, location))
                sys.exit(1)
            else:
                print('All OK removing stash')
                ctx.run('sudo rm -rf {0}'.format(tname))
        else:
            print('new release', name, version)
            failure = rel_wrapper(ctx, extra)
            if failure:
                print('Failure!')
                sys.exit(1)


def rel_wrapper(ctx, extra):
    run = ctx.run('sudo /software/bin/rez-release-wrapper {0}'.format(extra), warn=True)
    if not run.exited:
        print("Electron/react building")
        # print("Building & packaging electron...")
        # package(ctx)
    return run.exited


@task
def package(ctx):
    location = '/software/rez/packages/int/{0}/{1}'.format(name, version)
    ctx.run(
        "cd {}/frontend && npm run package".format(location)
    )
