#!/usr/bin/python


DOCUMENTATION = '''
---
module: ecd_ecr_migrate
short_description: migrate ecr image/repos between aws accounts.
description:
    - This module allows the user move ecr images between accounts (uses docker).
version_added: "1.1"
options:
  aws_access_key:
    description:
      - AWS access key id. If not set then the value of the AWS_ACCESS_KEY environment variable is used.
    required: false
    default: null
    aliases: [ 'ec2_access_key', 'access_key' ]
  aws_secret_key:
    description:
      - AWS secret key. If not set then the value of the AWS_SECRET_KEY environment variable is used.
    required: false
    default: null
    aliases: ['ec2_secret_key', 'secret_key']
  name:
    description:
      - name of ecr repository.
    required: true
    default: null
    aliases: []
  state:
    description:
      - Create or remove keys
    required: true
    default: present
    choices: [ 'present', 'absent' ]
  target_creds:
    description:
      - encrypt or decrypt, decrypt can only occur if key already exists and was used previously.
    required: true
    default: null

'''

EXAMPLES = '''
- name: Migrate ecr image
  ecd_ecr_migrate:
    name: "docker-ubuntu-newman"
    state: present
    target_creds: 
      eid: "..."
      roleid: "..."
  register: result

'''
import os
import base64
import docker
import sys
import boto3
import json

from collections import defaultdict


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
            print("[E] Docker not installed or not running")
            raise
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

try:
  import boto3
  from botocore.exceptions import ClientError, MissingParametersError, ParamValidationError
  HAS_BOTO3 = True

  from botocore.client import Config
except ImportError:
  import boto
  HAS_BOTO3 = False




def migration_exec(state, module, client, name, target_creds):
  # client = boto3.client('ecr' region_name=data['region'])
  erc_repo = name # "tf-pp-ms-vindecoding"
  
  iam = IAM_SESSION(s_origin['account'], s_origin['eID'], s_origin['role_definer'], region)
  # r1_from = Repository(aconnect, "ecr_repo_name", "us-west-2", "629xxxxxxxx", specific_tag="v1.1", profile="ccc-prod")
  r1_from = Repository(iam.aconnect, erc_repo, region, s_origin['account'])
  iam2 = IAM_SESSION(target_acct['account'], target_acct['eID'], target_acct['role'], region)
  # r2_to = Repository(aconnect2, "ecr_repo_name", "us-west-1", "804xxxxxxxxx", specific_tag="v1.1", profile="ccc-uat")
  r2_to = Repository(iam2.aconnect, erc_repo, region, target_acct['account'])
  print("...start migration")
  migration = MigrationECR(r1_from, r2_to, verbose=True)
  print("...migrating")
  migration.migrate()
  
  found = False
  return [path], False if found else True




def main():
  argument_spec = ec2_argument_spec()
  argument_spec.update(dict(
      state=dict(default='present', required=False, choices=['present', 'absent']),
      name=dict(required=True, default=None),
      target_creds=dict(type='dict',required=True,  default=None, aliases=['api_id']),
      
      )
  )


  module = AnsibleModule(
      argument_spec=argument_spec,
      supports_check_mode=True,
  )

  # validate dependencies
  if not HAS_BOTO3:
      module.fail_json(msg='boto3 is required for this module.')


  try:
      region, endpoint, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
      aws_connect_kwargs.update(dict(region=region,
                                     endpoint=endpoint,
                                     conn_type='client',
                                     resource='ecr'
                                     ))

      client = boto3_conn(module, **aws_connect_kwargs)
      boto3_conn(module,)
  except (ClientError, e):
      module.fail_json(msg="Can't authorize connection - {0}".format(e))
  except (Exception, e):
      module.fail_json(msg="Connection Error - {0}".format(e))


  typeList, changed = migration_exec(state, module, client, name, target_creds)


  module.exit_json(changed=has_changed, meta=result)


# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()

