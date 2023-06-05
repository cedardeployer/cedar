
# from atexit import register
from asyncio import subprocess
import os
import base64
import subprocess
import docker
import sys
import boto3
import json
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from tools.gentools import awsconnect
from tools.gentools.awsconnect import awsConnect
from tools.gentools.microUtils import loadConfig
from tools.gentools.microUtils import config_updateRestricted

# AWS_PROFILE=staging aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin ****.dkr.ecr.eu-west-1.amazonaws.com

dir_path = os.path.dirname(os.path.realpath(__file__))




class Repository:
    def __init__(self, aconnect, repository_name, region, account_id, specific_tag='latest', profile="default"):
        self.aconnect = aconnect
        self.repository_name = repository_name
        self.region = region
        self.account_id = account_id
        self.specific_tag = specific_tag
        self.profile = profile

    def loop_lambdas(self, source, targets, name, apis):
        if name.endswith("*"):
            print("no")
            



# python py2Migration_ecr.py dev "test" "tf-pp-*" true ENVR.yaml -onlyreset
### USE main_DeployBatcher.py INstead...
### USE main_DeployBatcher.py INstead...
### USE main_DeployBatcher.py INstead...
### USE main_DeployBatcher.py INstead...
### USE main_DeployBatcher.py INstead...
# python main_DeployBatcher.py -L dev2 "uat2" 'PP-*' ENVR.yaml pp_core true

if __name__ == '__main__':
    if "help" in sys.argv or "-help" in sys.argv or "--help" in sys.argv:
        print("Usage: python py2Migration_ecr.py <from_profile> <to_profile> <repository_name> <only_reset> <envr_file> [-onlyreset]")
        print('Example: python py2Migrage_ecr.py dev2 "uat2" "qq-ss-ms-claims" true ENVR.yaml')
        print("   OR  ***the below uses '*' as wildcard to match, starting with, all repositories/services**")
        print("Example: python py2Migration_ecr.py dev test qq-ss-* true ENVR.yaml -onlyreset")
        print("   (** use -onlyreset to -ONLY- reset the services, -NOT- migrate the images)")
        sys.exit(0)
    if len(sys.argv) < 5:
        print("Usage requires more arguments")
        sys.exit(1)
    CMD_STRING = sys.argv
    source_environment = sys.argv[1]
    target_environments = str(CMD_STRING[2]).strip().split(",")
    target = sys.argv[3]
    wildcard = False
    if '*' in target:
        wildcard = True
        target = target.replace('*', '')
    config = sys.argv[5]
    reset_only = False
    if len(sys.argv) > 6:
        reset_only = "-onlyreset" in sys.argv[6]

    fullpath = "%s/%s" % (dir_path, config)
    s_origin, s_global_accts = loadConfig(fullpath, source_environment)
    s_origin = config_updateRestricted(dir_path, s_origin)  # going to previous dir
    s_global_accts = config_updateRestricted(dir_path, s_global_accts)  # going to previous dir
    target_acct = None
    for k, v in s_global_accts.items():
        if target_environments[0] in v['all']:
            target_acct = v
            target_acct.update({"account": k})
            break

    print("...loading configs")
    region = 'us-east-1'

    erc_repo = None
    iam = IAM_SESSION(s_origin['account'], s_origin['eID'], s_origin['role_definer'], region)
    # r1_from = Repository(aconnect, "ecr_repo_name", "us-west-2", "629xxxxxxxx", specific_tag="v1.1", profile="ccc-prod")
    r1_from = Repository(iam.aconnect, erc_repo, region, s_origin['account'])
    iam2 = IAM_SESSION(target_acct['account'], target_acct['eID'], target_acct['role'], region)
    # r2_to = Repository(aconnect2, "ecr_repo_name", "us-west-1", "804xxxxxxxxx", specific_tag="v1.1", profile="ccc-uat")
    r2_to = Repository(iam2.aconnect, erc_repo, region, target_acct['account'])

    migration = MigrationECR(r1_from, r2_to, verbose=True)
    images = migration.ecr_get_reps()
    if not reset_only:
        for img in images:
            found = migration.name_matches(img, target, wildcard)
            if found:
                r1_from.repository_name = img
                r2_to.repository_name = img
                print("...start migration :%s" % img)
                print("...migrating")
                migration.migrate()
        print(images)
    else:
        print("...reset only")
    clusters = migration.ecs_get_clusters()
    print(clusters)
    all_svcs = migration.ecs_all_services(clusters)
    print(all_svcs)
    for svc, cluster in all_svcs.items():
        found = migration.name_matches(svc, target, wildcard)
        print(found)
        if found:
            print("...resetting cluster:%s service: %s" % (cluster, svc))
            migration.ecs_service_stop(cluster, svc)
