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

from tools.gentools.microMolder import LambdaMolder
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


def ansibleInvoke(account, config, role, static_path=None):
    msg=''
    roleFile = '%s.yaml' % (role)
    # roleFile = '%s_%s.yaml' % (account, role)
    target = config['all']
    local_dev = True
    if not static_path:
        newPath = ansibleResetDefinition(role, target, static_path)
    else:
        local_dev = False
    prevPath = dir_path
    logger.info(f'Definition role file: {roleFile}')
    print(f"\n    [DEPLOY] {account}::{target}")
    if not local_dev:
        import ansible_runner
        import ansible
        if 'bucket' in os.environ:
            ansible.constants.DEFAULT_REMOTE_TMP = '/tmp/ansible'
        # TODO: Fix playbook path
        print('Available path: ', dir_path)
        r = ansible_runner.run(inventory='/tmp/ansible/windows-servers',
                               private_data_dir='/tmp/ansible',
                               playbook='/tmp/ansible/734407909462_test_123.yaml')
        # print("{}: {}".format(r.status, r.rc))
        # successful: 0
        # for each_host_event in r.events:
        #     print(each_host_event['event'])
        # print("Final status:")
        print(r.stats)
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


def deployStart(target_name, accounts, targets, role, static_path=None, HardStop=False):
    outputs = {}
    for target in targets:
        for k, v in accounts.items():
            if target in v['all']:

                # SENTRY: Put Sentry back if it was in target (Taken out at lambda describe)
                try:
                    sts_client = awsconnect.stsClient
                    aconnect2 = awsConnect(k, v['eID'], v['role'], sts_client, 'us-east-1')
                    aconnect2.connect()
                    client = aconnect2.__get_client__('lambda')
                    lmda = client.get_function(FunctionName=target_name)

                    with open(f"../../ansible/roles/{role}/defaults/main_sb-{target}.yaml", "r") as stream:
                        try:
                            ydata = yaml.safe_load(stream)
                        except yaml.YAMLError as exc:
                            print(exc)
                    if ydata[f'A{role}'.replace('-', '_')]['lambdas'][0]['handler'] != lmda['Configuration']['Handler']:
                        ydata[f'A{role}'.replace('-', '_')]['lambdas'][0]['handler'] = lmda['Configuration']['Handler']
                    if 'Environment' in lmda['Configuration']:
                        if 'Variables' in lmda['Configuration']['Environment']:
                            if 'SENTRY_ENVIRONMENT' in lmda['Configuration']['Environment']['Variables']:
                                if 'SENTRY_ENVIRONMENT' in ydata[f'A{role}'.replace('-', '_')]['lambdas'][0]['environment_variables']:
                                    del ydata[f'A{role}'.replace('-', '_')]['lambdas'][0]['environment_variables']['SENTRY_ENVIRONMENT']
                            for nvar, nvarv in lmda['Configuration']['Environment']['Variables'].items():
                                if 'SENTRY' in nvar:
                                    ydata[f'A{role}'.replace('-', '_')]['lambdas'][0]['environment_variables'][nvar] = nvarv
                        # if lmda['Configuration']['Environment']['Variables']:
                        #     ydata[f'A{role}'.replace('-', '_')]['lambdas'][0]['environment_variables'].update(lmda['Configuration']['Environment']['Variables'])
                    if 'Layers' in lmda['Configuration']:
                        if lmda['Configuration']['Layers']:
                            for lay in lmda['Configuration']['Layers']:
                                if 'Sentry' in lay:
                                    # if 'sentry_sdk.integrations.init_serverless_sdk.sentry_lambda_handler' in ydata[f'A{role}'.replace('-', '_')]['lambdas'][0]['handler']:
                                    ydata[f'A{role}'.replace('-', '_')]['lambda_updates'][0]['layers'].extend(lmda['Configuration']['Layers'])
                                    # Add layer to main

                    with open(f"../../ansible/roles/{role}/defaults/main_sb-{target}.yaml", 'w', encoding='utf8') as outfile:
                        outfile.write('---\n')
                        yaml.dump(ydata, outfile, default_flow_style=False, allow_unicode=True)

                except client.exceptions.ResourceNotFoundException:
                    print("Does not yet exist in target env...")
                    # pass
                # SENTRY: END

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