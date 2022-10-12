
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
ECR_URI = "{}.dkr.ecr.{}.amazonaws.com/{}"
TAG_URI = "{}:{}"

class IAM_SESSION:
    aconnect = None

    def __init__(self, accID, eID, role, region="us-east-1"):
        awsconnect.stsClient_init()
        sts_client = awsconnect.stsClient
        print(accID)
        print(role)
        print(eID)
        print("*********SSSSSS")
        self.aconnect = awsConnect(accID, eID, role, sts_client, region)
        self.aconnect.connect()
        
    def get_account_id(self):
        return self.account_id


class Repository:
    def __init__(self, aconnect, repository_name, region, account_id, specific_tag='latest', profile="default"):
        self.aconnect = aconnect
        self.repository_name = repository_name
        self.region = region
        self.account_id = account_id
        self.specific_tag = specific_tag
        self.profile = profile

    def get_uri(self):
        base = ECR_URI.format(self.account_id, self.region, self.repository_name)

        return TAG_URI.format(base, self.specific_tag) if self.specific_tag else base

    def __str__(self):
        return f"{self.account_id}, {self.region}, {self.repository_name}"
        # return json.dumps(self.__dict__)

class MigrationECR:
    client = None
    def __init__(self, ecr_from, ecr_to, verbose = False):
        self.ecr_from = ecr_from
        self.ecr_to = ecr_to
        purge = False
        try:
            self.docker_client = docker.from_env()
            self.ta = docker.APIClient
            if purge:
                # pruned = self.docker_client.images.prune()
                pruned = self.docker_client.images.prune(filters={'dangling': False})
                print("pruned: {}".format(pruned))
        except Exception as e:
            msg = "[E] Docker not installed or not running...please run docker first"
            cmd = ["open", "--background", "-a", "Docker"]
            # subprocess.call(cmd)
            # open --background -a Docker &&
            #     while ! docker system info > /dev/null 2>&1; do sleep 1; done &&
            #     docker run busybox

            print(msg)
            # raise Exception(msg)
        self.verbose = verbose

    def ecr_token_login(self, ecr: Repository):
        aconnect = ecr.aconnect
        ecr_client = aconnect.__get_client__("ecr")
        token = ecr_client.get_authorization_token()
        username, password = base64.b64decode(token['authorizationData'][0]['authorizationToken']).decode().split(':')
        registry = token['authorizationData'][0]['proxyEndpoint']
        self.docker_client.login(username, password, registry=registry)
        return token

    def ecr_reps_exists(self, target_name, ecr: Repository):
        aconnect = ecr.aconnect
        ecr_client = aconnect.__get_client__("ecr")
        reps = ecr_client.describe_repositories()['repositories']
        found = False
        print(".....registry setup....")
        for rep in reps:
            if rep['repositoryName'] == target_name:
                found = True
                return rep
        if not found:
            response = ecr_client.create_repository(repositoryName=target_name, imageScanningConfiguration={'scanOnPush':True}
                    # ,encryptionConfiguration={'encryptionType': 'KMS'}
                )
            return response['repository']

    @staticmethod
    def get_images(ecr: Repository, limit=123):
        aconnect = ecr.aconnect
        ecr_client = aconnect.__get_client__("ecr")
        response = ecr_client.list_images(repositoryName=ecr.repository_name, maxResults=limit)
        if ecr.specific_tag:
            return list(
                filter(lambda img: img.get("imageTag", None) == ecr.specific_tag, response.get("imageIds", None)))
        return response.get("imageIds", None)

    def push_images(self, ecr: Repository):
        print("____001 Pushing....")
        if ecr.specific_tag:
            target_name = ecr.repository_name
            app_name = os.path.basename(target_name).lower()
            self.ecr_reps_exists(app_name, ecr)
            token = self.ecr_token_login(ecr)
            print(self.ecr_from.get_uri())
            imgs = self.docker_client.images.list()
            print(" imgs: {}".format(imgs))
            push_details = self.docker_client.images.push(ecr.get_uri(), tag='latest')
            if self.verbose:
                print("PUSH: {}".format(push_details))
        else:
            raise Exception("Tag not found! ({})".format(ecr.specific_tag))

    def pull_and_tag(self, ecr: Repository):
        print("____001 Pulling.....")
        try:
            print("***********")
            print("****001")
            print(ecr.aconnect._botocore_session)
            # boto3.setup_default_session(profile_name=self.ecr_from.profile)
            # boto3.setup_default_session(botocore_session=ecr.aconnect._botocore_session)
            token = self.ecr_token_login(ecr)
            print(self.ecr_from.get_uri())
            image_from = self.docker_client.images.pull(self.ecr_from.get_uri())
            print(self.ecr_to.get_uri())
            image_from.tag(self.ecr_to.get_uri())
            imgs = self.docker_client.images.list()
            print(" imgs: {}".format(imgs))
            if self.verbose:
                print("PULL: {}".format(image_from))
        except docker.errors.APIError as e:
            print("""Error: {} \n\nMake sure you are authenticated with AWS ECR: \n$(aws ecr get-login --region REGIN --no-include-email --profile PROFILE)
            """.format(e))
            sys.exit(1)

    def ecs_get_clusters(self):
        aconnect = self.ecr_to.aconnect
        ecs_client = aconnect.__get_client__("ecs")
        clusters = ecs_client.list_clusters()
        return clusters
    
    def ecs_all_services(self, clusters):
        services_in = {}
        for cluster in clusters['clusterArns']:
            cluster_name = cluster.split('/')[-1]
            services = self.ecs_get_running_services(cluster_name)
            for svc in services:
                service_name = svc.split('/')[-1]
                services_in[service_name] = cluster_name
        return services_in

    def ecs_get_running_services(self, cluster_name):
        aconnect = self.ecr_to.aconnect
        ecs_client = aconnect.__get_client__("ecs")
        response = ecs_client.list_services(cluster=cluster_name)
        services = response['serviceArns']
        return services

    def ecs_all_stop(self, cluster_name):
        aconnect = self.ecr_to.aconnect
        ecs_client = aconnect.__get_client__("ecs")
        services = self.ecs_get_running_services(cluster_name)
        for service in services:
            service_name = service.split('/')[-1]
            self.ecs_service_stop(cluster_name, service_name)
            # self.ecs_task_stop(cluster_name, service_name)


    def ecs_service_stop(self, cluster_name, service_name):
        aconnect = self.ecr_to.aconnect
        ecs_client = aconnect.__get_client__("ecs")
        response = ecs_client.update_service(cluster=cluster_name, service=service_name,forceNewDeployment=True)
        print("..............forceNewDeployment on service: {}".format(service_name))
        # print("Stopping service response: {}".format(response))

    def ecr_get_reps(self):
        aconnect = self.ecr_from.aconnect
        ecr_client = aconnect.__get_client__("ecr")
        reps = ecr_client.describe_repositories()['repositories']
        return [ rr['repositoryName'] for rr in reps ]
    
    def name_matches(self, name, tomatch, wildcard=False):
        if wildcard:
            return name.startswith(tomatch)
        return name == tomatch

    def migrate(self):
        if self.ecr_from and self.ecr_to:
            list_images_from = self.get_images(self.ecr_from)
            for image in list_images_from:
                print("image to pushed: {}".format(json.dumps(image)))
                self.ecr_from.specific_tag = image.get("imageTag")
                self.ecr_to.specific_tag = image.get("imageTag")
                print("FROM: {}".format(self.ecr_from))
                print("TO: {}".format(self.ecr_to))
                self.pull_and_tag(self.ecr_from)
                self.push_images(self.ecr_to)
        else:
            raise Exception("Missing variables: {} or {}".format("ecr_from", "ecr_to"))


#python py2Migration_ecr.py dev "test" "tf-pp-*" true ENVR.yaml -onlyreset

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
    for k,v in s_global_accts.items():
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
                r1_from.repository_name=img
                r2_to.repository_name=img
                print("...start migration :%s" % img)
                print("...migrating")
                migration.migrate()
    else:
        print("...reset only")
    clusters = migration.ecs_get_clusters()
    all_svcs = migration.ecs_all_services(clusters)
    for svc, cluster in all_svcs.items():
        found = migration.name_matches(svc, target, wildcard)
        if found:
            print("...resetting cluster:%s service: %s" % (cluster, svc))
            migration.ecs_service_stop(cluster, svc)


    





