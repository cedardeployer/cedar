import logging

import os
import sys
import re
import datetime
from time import sleep
import time
import random
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from tools.gentools import awsconnect
from tools.gentools.microMolder import LambdaMolder
from tools.gentools.microFront import CloudFrontMolder
from tools.gentools.microGateway import ApiGatewayMolder
from tools.gentools.microDynamo import DynamoMolder
from tools.gentools.microCode import CodeMolder
from tools.gentools.microUtils import loadConfig, roleCleaner, config_updateRestricted
from tools.gentools.MMAnsibleDeployAll import deployStart
# TESTERS...
from tools.gentools.microGateway_test import ApiGatewayTester

from tools.gentools.awsconnect import awsConnect

try:
    import log_config
except Exception:
    print("colors not loaded...")

# sudo ansible-playbook -i windows-servers API_Name.yaml -vvvv
# dir_path = os.path.dirname(__file__)
dir_path = os.path.dirname(os.path.realpath(__file__))
# directory='/path/to/Ansible_Deployer/ansible'
logger = logging.getLogger('main_Deployer')

# python Main_DEPLOYER.py -DY dev "test,stage,prod,tpp"  "xx_tablename" ENVR.yaml API_Name true


class TemporalDeployer():
    root = None
    bucket = None
    target_path = None

    def __init__(self, directory=None, bucket=None, target_path=None):
        if directory:
            self.root = directory
        if bucket:
            self.bucket = bucket
            self.target_path = target_path

# CREATE DEFINITIONS

    def Define(self, type_in, svc_in, origin, global_accts, sendto, config, triggers=None, targetAPI=None, fullUpdate=None):
        accID = accPlus = origin['account']
        region = origin['region']
        suffix = ''
        if 'sharedas' in origin:
            accPlus = accID + origin['sharedas']
        accountRole = global_accts[accPlus]['role']
        logger.debug(f'Using ({type_in}, {svc_in}), role: {accountRole}, aod: {accID}, and config {config} -> copy ansible to {sendto}')
        logger.debug("To assume <cross_acct_role> ROLE make sure you set 'assume_role' in 'ENVR.yaml' to True or False as needed")
        awsconnect.stsClient_init()
        sts_client = awsconnect.stsClient
        print(f'   ------------------------')
        print(f'    Account: {accID}')
        print(f"    Account: {origin['eID']}'")
        print(f"    Account: {origin['role_definer']}")
        print(f'   ------------------------')
        aconnect = awsConnect(accID, origin['eID'], origin['role_definer'], sts_client, region)
        aconnect.connect()
        results = None
        output_dir = None
        if type_in == "-CF":
            cm = CloudFrontMolder("ansible", self.root)
            acctID, target, acctTitle, ready = cm.cfront_describe(
                svc_in, aconnect, origin, global_accts, sendto)
            output_dir = cm.finalDir_output
        elif type_in == "-L":
            lm = LambdaMolder("ansible", self.root)
            acctID, target, acctTitle, ready = lm.lambda_describe(
                svc_in, aconnect, origin, global_accts, triggers, sendto, targetAPI, fullUpdate)
            output_dir = lm.finalDir_output
        elif type_in == "-G":
            gm = ApiGatewayMolder("ansible", self.root)
            if targetAPI == svc_in:
                acctID, target, acctTitle, ready = gm.describe_GatewayALL(
                    svc_in, aconnect, origin, global_accts, triggers, sendto, targetAPI, fullUpdate, True)
            else:
                acctID, target, acctTitle, ready = gm.describe_GwResource(
                    svc_in, aconnect, origin, global_accts, triggers, sendto, targetAPI, fullUpdate, True)
            output_dir = gm.finalDir_output
        elif type_in == "-DY":
            dy = DynamoMolder("ansible", self.root)
            acctID, target, acctTitle, ready = dy.define(
                svc_in, aconnect, origin, global_accts, sendto)
            output_dir = dy.finalDir_output
        elif type_in == "-CB":
            cb = CodeMolder("ansible", self.root)
            acctID, target, acctTitle, ready = cb.define(
                svc_in, aconnect, origin, global_accts, sendto)
            output_dir = cb.finalDir_output
        return acctID, target, acctTitle, ready, output_dir


# CHECK GATEWAY FOR OPTIONS. LOOK TO SEE IF OPTIONS ARE THERE!!!

    def TEST(self, type_in, svc_in, acct, acctName, global_accts, config, targetAPI):
        accID = acct
        region = 'us-east-1'
        accountRole = global_accts[accID]['role']
        logger.debug(f'Using ({type_in}, {svc_in}), role: {accountRole}, aod: {accID}, and config {config} -> copy ansible to {sendto}')
        logger.debug("To assume <cross_acct_role> ROLE make sure you set 'assume_role' in 'ENVR.yaml' to True or False as needed")
        awsconnect.stsClient_init()
        sts_client = awsconnect.stsClient
        eID = 10000010001
        if 'eID' in global_accts[accID]:
            eID = global_accts[accID]['eID']
        aconnect = awsConnect(accID, eID, accountRole, sts_client, region)
        aconnect.connect()
        results = None
        if type_in == "-CF":
            cm = CloudFrontMolder("ansible")
            print("CF TEST here")
        elif type_in == "-L":
            lm = LambdaMolder("ansible")
            print("LAMBDA TEST here")
        elif type_in == "-G":
            gm = ApiGatewayTester("ansible")
            print("GATEWAY TEST here")
            if targetAPI == svc_in:
                errors = gm.test_GatewayALL(
                    svc_in, aconnect, acct, acctName, global_accts, targetAPI)
            else:
                errors = gm.test_GwResource(
                    svc_in, aconnect, acct, acctName, global_accts, targetAPI)
        elif type_in == "-DY":
            dy = DynamoMolder("ansible")
            print("DYNAMO TEST here")
        return errors


# EXECUTE AGAINST DEFINITIONS
#
#
# PRODUCE RESULTS PASS/FAIL
# python microMolder.py -L xx-LambdaName true ENVR.yaml API_Name true
# python Main_DEPLOYER.py -DY dev "test,stage" xx_tablename ENVR.yaml API_Name true
# python Main_DEPLOYER.py -G dev "stage" API_Name ENVR.yaml API_Name true
# . OR
# python Main_DEPLOYER.py "xx-stage,xx-test" xx_tablename ENVR.yaml
# python Main_Deployer.py "xx-test" xx_tablename ENVR.yaml
def print_help():
    print("""
    ************************************************************
    Try using the following PSUEDO after *CONFIG.yaml is correct :
    python Main_DEPLOYER.py -L dev "test,stage" * ENVR.yaml API_Name true
        -[NOTE]-->  the above will describe 'dev' and then deploy ALL * to 'test,stage'
        -[NOTE]-->  the above will describe 'dev' and then deploy to 'test,stage'
        -[NOTE]-->  the above can also deploy API only using -G , CloudFront using -CF, DynamoDB using -DY
    python Main_DEPLOYER.py -G dev "test,stage" activities[*] ENVR.yaml API_Name true
        -[NOTE]-->  the above will describe activities api with all methods *
    python Main_DEPLOYER.py -G dev "test,stage" *[*] ENVR.yaml API_Name true
    python Main_DEPLOYER.py -G dev "test,stage" API_Name ENVR.yaml API_Name true
        -[NOTE]-->  the above will deploy all API under API_Name... both rolename(API_Name) and targetAPI MUST be SAME
    OR to deploy without Defining
        -[NOTE]-->  the above will deploy to stage,test
    ************************************************************
    """)


def main(tmp=None, bucket=None, target_path=None):
    # global directory
    directory = os.path.join('../../ansible')
    found = None
    length = 0
    tot = len(sys.argv) - 1
    SkipDefinition = False
    type_in = str(sys.argv[1]).strip()

    if 'help' in type_in:
        print_help()
        exit()

    targetAPI = fullUpdate = target_environments = None
    if tot < 6:
        missing = 6 - tot
        totTypeIn = len(type_in)
        msg = "[E] %s arguments missing... found:%s needs 6+ arguments" % (
            missing, tot)
        if "-" in type_in and totTypeIn < 4:
            example = "... for example: \n   python Main_DEPLOYER.py -L dev 'test,stage' Quickboks_temp ENVR.yaml"
            msg = "%s %s" % (msg, example)
            raise Exception(msg)
        elif totTypeIn > 4:
            SkipDefinition = True
    if not SkipDefinition:
        source_environment = str(sys.argv[2]).strip()
        target_environments = str(sys.argv[3]).strip().split(",")
        role = str(sys.argv[4]).strip()
        config = str(sys.argv[5]).strip()  # ENVR.yaml
        if '/' in str(sys.argv[6]):
            sendto = str(sys.argv[6]).strip()  # 'some path'
        else:
            sendto = os.path.join('../../ansible/roles')
            if tmp:
                sendto = "%s/%s" % (tmp, "ansible/roles")
                if not os.path.exists(sendto):
                    os.makedirs(sendto)
            sys.argv.append(sys.argv[7])
            sys.argv[7] = sys.argv[6]
        roleString = roleCleaner(role)

        # targetAPI = str(sys.argv[7]).strip()   ### API_Name
        if len(sys.argv) > 7:
            targetAPI = str(sys.argv[7]).strip()
            if targetAPI.lower() == "none" or targetAPI.lower() == "null" or targetAPI == "*":
                targetAPI = None
        # fullUpdate = str(sys.argv[8]).strip()   ### true
        if tot > 8:
            fullUpdate = str(sys.argv[8]).strip().lower()  # true
            if fullUpdate == "none" or fullUpdate == "null" or fullUpdate == "false":
                fullUpdate = False
            else:
                fullUpdate = True
    else:
        target_environments = type_in.split(",")
        role = str(sys.argv[2]).strip()
        config = str(sys.argv[3]).strip()

    start_time = time.time()

    fullpath = "%s/%s" % (dir_path, config)
    origin, global_accts = loadConfig(fullpath, source_environment)

    origin = config_updateRestricted(dir_path, origin)  # going to previous dir
    global_accts = config_updateRestricted(dir_path, global_accts)  # going to previous dir
    acctID = origin['account']
    static_path = None
    if sendto:
        roleString = "%s_%s" % (acctID, roleString)
        if tmp:
            sendto = "%s/%s/%s" % (tmp, sendto, roleString)
            static_path = "%s/%s" % (tmp, sendto)
        else:
            sendto = "%s/%s" % (sendto, roleString)
    triggers = origin['triggers']
    if triggers is None:
        raise ValueError(
            "[E] config file [ %s ] did not load correctly.. PLEASE check / fix and try again" % (fullpath))
    td = TemporalDeployer(tmp, bucket, target_path)
    ready = None

    if not SkipDefinition:
        acctID, target, acctTitle, ready, output_dir = td.Define(type_in, role, origin, global_accts, sendto, config, triggers, targetAPI, fullUpdate)
        logger.info(f'DEFINED in {time.time() - start_time} seconds')
        logger.info(f'...FILES can be found in ...{output_dir}')
        # BELOW to skip deployment
        # exit()

    if ready or SkipDefinition:
        deploy_time = time.time()
        print("   ########################################################")
        print("   ########### Ansible DEPLOYMENT START  ##################")
        print("   ########################################################")
        role = role
        results = deployStart(target, global_accts, target_environments, roleString, static_path)
        for k, v in results.items():
            msg = "%s Account: %s, %s" % (v['name'], k, v['value'])
            # print(msg)
            if "-G" in type_in:
                acct = v['value']
                acctName = v['name']
                logger.info('GATEWAY releasing; checking OPTIONS')
                # acctID, target, acctTitle, ready = td.TEST(type_in,role,acct,acctName,global_accts,config,targetAPI)

        logger.info(f'DEPLOYED in {time.time() - start_time} seconds')

    logger.info(f'FINISHED in {time.time() - start_time} seconds')


# def lambda_handler(event, context):
#     print('LAMBDAEVENT: ', event)
#
#     parsed_args = sys.argv
#     parsed_args.append(f"-{event['service']}")
#     parsed_args.append('dev')
#     parsed_args.append(event['env'])
#     parsed_args.append(event['component'])
#     parsed_args.append('ENVR.yaml')
#     parsed_args.append('null')
#     parsed_args.append('true')
#     bucket = "BUCKET-NAME"
#     epoch = int(datetime.datetime.utcnow().timestamp())
#     target_path = "data/lambdas/CD-CEDAR/%s" % (epoch)
#     tmp = "/tmp"
#     main(tmp, bucket, target_path)


if __name__ == "__main__":
    main()