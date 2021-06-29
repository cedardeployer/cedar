# This code is used to create Ansible files for deploying Lambda's
# all that is needed is a target Lambda, tests, and it will do the rest.
# finds associate roles and policies
# creates Ansible modules based on those policies and roles
# defines the Lambdas and creates them with tests
# finds api-gateways or other events
# if api found defines the security needed. creates modules for deployment with templates
import re
from time import sleep
import os
import time
import random
import shutil
from datetime import datetime, date
import boto3
from botocore.exceptions import ClientError
import json
import sys
from shutil import copyfile
import fileinput
import logging
import urllib

import distutils
from distutils import dir_util

from . import awsconnect

from .awsconnect import awsConnect
from shutil import copyfile

#from context import FormatContext
#import pyaml
# pip install pyyaml
import yaml
import decimal
from tools.gentools.microUtils import writeYaml, writeJSON, account_replace, loadServicesMap, loadConfig, ansibleSetup
import subprocess
from subprocess import check_output
from subprocess import Popen, PIPE

logger = logging.getLogger(__name__)

local_dev = True
try:
    os.environ['bucket']
    import ansible.inventory
    import ansible.playbook
    # import ansible.runner
    import ansible.constants
    from ansible import utils
    # from ansible import callbacks
    local_dev = False
except Exception:
    logger.info('RUNNING AS LOCAL DEPLOYMENT')
# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
# dir_path = os.path.dirname(__file__)
dir_path = os.path.dirname(os.path.realpath(__file__))
# directory='/Users/bgarner/CR/Ansible_Deployer/ansible'
directory = os.path.join('../../ansible')


def ansibleResetDefinition(role, target, static_path=None):
    final_path = directory
    if static_path:
        final_path = f"{static_path}/ansible" if 'ansible' not in static_path else static_path
    rolePath = "%s/roles/%s/defaults" % (final_path, role)
    main = "%s/main.yaml" % rolePath
    logger.debug(f'Main file path: {main}')
    os.remove(main)  # only removing old destination
    copyfile("%s/main_%s.yaml" % (rolePath, target), main)
    return final_path


def ansibleDeleteCache(role, baseDir):
    rolePath = "%s/ansible/%s" % (baseDir, role)
    if os.path.exists(rolePath):
        print("[W] removing directory %s" % (rolePath))
        shutil.rmtree(rolePath)


def run_playbook(**kwargs):
    stats = callbacks.AggregateStats()
    playbook_cb = callbacks.PlaybookCallbacks(verbose=utils.VERBOSITY)
    runner_cb = callbacks.PlaybookRunnerCallbacks(stats, verbose=utils.VERBOSITY)

    # use /tmp instead of $HOME
    if 'bucket' in os.environ:
        ansible.constants.DEFAULT_REMOTE_TMP = '/tmp/ansible'
    else:
        ansible.constants.DEFAULT_REMOTE_TMP = '/tmp/ansible'

    out = ansible.playbook.PlayBook(
        callbacks=playbook_cb,
        runner_callbacks=runner_cb,
        stats=stats,
        **kwargs
    ).run()

    return out


def ansibleInvoke(account, config, role, static_path=None):
    roleFile = '%s.yaml' % (role)
    # roleFile = '%s_%s.yaml' % (account, role)
    target = config['all']
    if not static_path:
        newPath = ansibleResetDefinition(role, target, static_path)
    else:
        local_dev = False
    prevPath = dir_path
    logger.info(f'Definition role file: {roleFile}')
    print(f"\n    [DEPLOY] {account}::{target}")
    if not local_dev:
        pass
        #############
        # add own ansible command here...
        ###########
        # ansibleDeleteCache(role, "/tmp/tools/gentools")
        # rawOut = run_playbook(
        #     playbook=roleFile,
        #     inventory=ansible.inventory.Inventory(['localhost'])
        # )
    else:
        os.chdir(newPath)
        quotedRole = '"%s"' % (roleFile)
        args = ['ansible-playbook', '-i', 'windows-servers', quotedRole, '-vvvv']
        msg = ""
        commandIn = " ".join(args)
        try:
            print('        ', commandIn)
            rawOut = check_output(commandIn, stderr=PIPE, shell=True).decode()
            # rawOut = check_output(args, stderr=PIPE).decode()
            # rawOut = check_output(args, stderr=PIPE, shell=True).decode()
            if isinstance(rawOut, str):
                output = rawOut
            else:
                output = rawOut.decode("utf-8")
            msg = output
        except Exception as e:
            msg = "[E] error occured target:%s  file:%s error:%s" % (target, roleFile, e)
            logger.error(msg)
        # process = Popen(args, stdout=PIPE, stderr=PIPE)#, timeout=timeout)
        # stdout, stderr = process.communicate()  #will wait without deadlocking
        #print (stdout)
        os.chdir(prevPath)
       # print (stderr)
    print(f"    [COMPLETE] {account}::{target}")

    return account, target, msg


def deployStart(accounts, targets, role, static_path=None, HardStop=False):
    outputs = {}
    for target in targets:
        for k, v in accounts.items():
            if target in v['all']:
                account, target, result = ansibleInvoke(k, v, role, static_path)
                outputs.update({account: {"name": target, "value": result}})
                if HardStop:
                    if '[E]' in result:
                        return outputs
                break
    return outputs
# cp -R /usr/local/src/venvs/vdocx3/lib/python3.6/site-packages/slacker /path/to/Lambda
# ansible-playbook -i windows-servers xx_tablename.yaml -vvvv

    # python MMAnsibleDeployAll.py "xx-stage,xx-test" xx_tablename ENVR.yaml
    #
    # python MMAnsibleDeployAll.py "stage,prod" API_Name ENVR.yaml


# OR call it manually in /ansible folder
    #  ansible-playbook -i windows-servers xx-LambdaName -vvvv


if __name__ == "__main__":
    found = None
    length = 0
    target_environments = str(sys.argv[1]).strip().split(",")
    role = str(sys.argv[2]).strip()
    config = str(sys.argv[3]).strip()
    start_time = time.time()

    fullpath = "%s/%s" % (dir_path, config)
    origin, global_accts = loadConfig(fullpath, "dev")
    results = deployStart(global_accts, target_environments, role)
    for k, v in results.items():
        msg = "%s Account: %s, %s" % (v['name'], k, v['value'])
        print(msg)

    # print(global_accts)

    #print (target_environments)
    #//logger.info("Finished")

    print("--- %s seconds ---" % (time.time() - start_time))