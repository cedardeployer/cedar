import boto3
import logging
import os
import sys
import time
from subprocess import PIPE
from subprocess import check_output

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from tools.gentools import awsconnect
from tools.gentools.awsconnect import awsConnect
from tools.gentools.microUtils import loadConfig
from tools.gentools.microUtils import config_updateRestricted

try:
    import log_config
except Exception:
    print("colors not loaded...")

logger = logging.getLogger(__name__)


class BatchDeployer():
    root = None
    bucket = None
    target_path = None
    svc_type = None
    __client = None
    __resource = None

    def __init__(self, aconnect, type_in):
        self.svc_type = type_in
        if type_in == "-CK" or type_in == "-CS":  # Containers for K8 --> cluster name
            raise Exception("[E] Containers not supported yet")
        elif type_in == "-S3" or type_in == "-S3C" or type_in == "-S3M":  # S3 and copy configs
            raise Exception("[E] S3 not supported yet")
        elif type_in == "-CF":
            raise Exception("[E] CloudFront not supported yet")
        elif type_in == "-L":
            self.__client = aconnect.__get_client__('lambda') if aconnect else boto3.client('lambda')
            # self.__resource = aconnect.__get_resource__('lambda') if aconnect else boto3.resource('lambda')
        elif type_in == "-G":
            self.__client = aconnect.__get_client__('apigateway') if aconnect else boto3.client('apigateway')
            # self.__resource = aconnect.__get_resource__('apigateway') if aconnect else boto3.resource('apigateway')
        elif type_in == "-DY":
            raise Exception("[E] DynamoDB not supported yet")
        else:
            raise Exception("[E] OTHER not supported yet")

    # CREATE DEFINITIONS

    def deploy_loop(self, svc_type, source, target_env, target, config_file, api_name):
        reset = 'true'
        if isinstance(target_env, list):
            target_env = ",".join(target_env)
        args = ['python', 'main_Deployer.py', svc_type, source, target_env, target, config_file, api_name, reset]
        msg = ""
        print(args)
        commandIn = " ".join(args)
        try:
            print('        ', commandIn)
            rawOut = check_output(commandIn, stderr=PIPE, shell=True).decode()
            if isinstance(rawOut, str):
                output = rawOut
            else:
                output = rawOut.decode("utf-8")
            msg = output
        except Exception as e:
            msg = "[E] error occured target:%s  target:%s error:%s" % (target_env, target, e)
            logger.error(msg)
        print(f"    [COMPLETE] {target_env}::{target}")

    def get_lambdas(self, Marker=None):
        args = {"MaxItems": 500}
        if Marker:
            args['Marker'] = Marker
        ll = self.__client.list_functions(**args)
        items = ll['Functions']
        if 'NextMarker' in ll:
            items = items + self.get_lambdas(ll['NextMarker'])
        return items

    def get_services(self, role_prefix, api_name_prefix):
        services = []
        # get all Services that need to be deployed
        if "L" in self.svc_type:
            lambdas = self.get_lambdas()
            for lm in lambdas:
                if lm['FunctionName'].startswith(role_prefix):
                    services.append(lm['FunctionName'])
        elif "G" in self.svc_type:
            ll = self.__client.get_rest_apis(limit=500)
            print(ll)
            for lm in ll['items']:
                if lm['name'].startswith(api_name_prefix):
                    services.append(lm['name'])
        else:
            raise Exception("[E] role not supported yet")
        return services


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
    python main_Deployer.py -S3C dev2 "uat2" "pp-portal-dev2/data/config/policies.env.dev" ENVR.yaml pp_core true
    python main_Deployer.py -S3C dev2 "uat2" "pp-portal-dev2/data/config/" ENVR.yaml pp_core true
    python Main_DEPLOYER.py -G dev "test,stage" *[*] ENVR.yaml API_Name true
    python Main_DEPLOYER.py -G dev "test,stage" API_Name ENVR.yaml API_Name true
    python Main_DEPLOYER.py -CK dev "test,stage" Cluster_Name ENVR.yaml API_Name true
        -[NOTE]-->  the above will deploy all API under API_Name... both rolename(API_Name) and targetAPI MUST be SAME
    OR to deploy without Defining
        -[NOTE]-->  the above will deploy to stage,test
    python Main_DEPLOYER.py -L dev "test,stage" API_Name ENVR.yaml API_Name true -o terraform
    ************************************************************
    """)


def main(tmp=None, bucket=None, target_path=None):
    # global directory
    print(sys.version)
    if '3.7' in sys.version:
        print("Python 3.7 is not supported, please upgrade")
        exit()
    directory = os.path.join('../../ansible')
    found = None
    length = 0
    CMD_STRING = sys.argv
    tot = len(CMD_STRING) - 1
    SkipDefinition = False
    type_in = str(CMD_STRING[1]).strip()
    argv_str = " ".join(CMD_STRING)

    if 'help' in type_in:
        print_help()
        exit()
    render_to = None
    if "-o terraform" in argv_str:
        render_to = "terraform"
        argv_str = argv_str.replace("-o terraform", "")
        CMD_STRING = argv_str.split(" ")
        tot = tot - 1

    targetAPI = fullUpdate = target_environments = None

    if not SkipDefinition:
        source_environment = str(CMD_STRING[2]).strip()
        target_environments = str(CMD_STRING[3]).strip().split(",")
        role = str(CMD_STRING[4]).strip()
        config = str(CMD_STRING[5]).strip()  # ENVR.yaml
        if '/' in str(CMD_STRING[6]):
            sendto = str(CMD_STRING[6]).strip()  # 'some path'
        else:
            sendto = os.path.join('../../ansible/roles')
            if tmp:
                sendto = "%s/%s" % (tmp, "ansible/roles")
                if not os.path.exists(sendto):
                    os.makedirs(sendto)
            CMD_STRING.append(CMD_STRING[7])
            CMD_STRING[7] = CMD_STRING[6]

        # targetAPI = str(CMD_STRING[7]).strip()   ### API_Name
        if len(CMD_STRING) > 7:
            targetAPI = str(CMD_STRING[7]).strip()
            if targetAPI.lower() == "none" or targetAPI.lower() == "null" or targetAPI == "*":
                targetAPI = None
        # fullUpdate = str(CMD_STRING[8]).strip()   ### true
        if tot > 8:
            fullUpdate = str(CMD_STRING[8]).strip().lower()  # true
            if fullUpdate == "none" or fullUpdate == "null" or fullUpdate == "false":
                fullUpdate = False
            else:
                fullUpdate = True
    else:
        target_environments = type_in.split(",")
        role = str(CMD_STRING[2]).strip()
        config = str(CMD_STRING[3]).strip()

    start_time = time.time()

    awsconnect.stsClient_init()
    sts_client = awsconnect.stsClient
    fullpath = "%s/%s" % (dir_path, config)
    origin, global_accts = loadConfig(fullpath, source_environment)
    origin = config_updateRestricted(dir_path, origin)
    global_accts = config_updateRestricted(dir_path, global_accts)
    accID = origin['account']
    region = origin['region']
    aconnect = awsConnect(accID, origin['eID'], origin['role_definer'], sts_client, region)
    aconnect.connect()

    bd = BatchDeployer(aconnect, type_in)
    role_prefix = None
    api_name_prefix = None
    if '*' in role:
        role_prefix = role.replace('*', '')
    if '*' in targetAPI:
        api_name_prefix = targetAPI.replace('*', '')
    if role_prefix is None and api_name_prefix is None:
        raise Exception(" '*' not found in role_prefix or api_name_prefix")
    services = bd.get_services(role_prefix, api_name_prefix)
    for svc_name in services:
        print("orchestrating....svc_name: %s" % svc_name)
        if '-L' in type_in:
            bd.deploy_loop(type_in, source_environment, target_environments, svc_name, config, targetAPI)
        elif '-G' in type_in:
            targetAPI = svc_name
            bd.deploy_loop(type_in, source_environment, target_environments, '*', config, targetAPI)

    logger.info(f'FINISHED in {time.time() - start_time} seconds')


# def lambda_handler(event, context):
#     print('LAMBDAEVENT: ', event)
#
#     parsed_args = CMD_STRING
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
