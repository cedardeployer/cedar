#!/usr/bin/python
# from collections import defaultdict
import os
import datetime
import re
from datetime import datetime as dtime
# import time

DOCUMENTATION = '''
---
module: cd_lambda_permit
short_description: adds permissions for lambda that will be invoked by other services .
description:
    - This module allows the management of AWS Lambda function or other event source mappings such as S3 bucket
      events, DynamoDB and Kinesis streaming events via the Ansible framework.
      It is idempotent and supports "Check" mode.  Use module M(lambda) to manage the lambda
      function itself and M(lambda_alias) to manage function aliases.
version_added: "2.1"
author: Robert Colvin (@rcolvin)
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
    lambda_function_arn:
        description:
          - The name or ARN of the lambda function.
        required: true
        aliases: ['function_name', 'function_arn']
    state:
        description:
          - Describes the desired state and defaults to "present".
        required: true
        default: "present"
        choices: ["present", "absent"]
    alias:
        description:
          - Name of the function alias. Mutually exclusive with C(version).
        required: true
        version:
        description:
          -  Version of the Lambda function. Mutually exclusive with C(alias).
        required: false
    event_source:
        description:
          -  Source of the event that triggers the lambda function.
        required: true
        choices: ['s3', 'Kinesis', 'DynamoDB', 'SNS']
    requirements:
        - boto3
    extends_documentation_fragment:
        - aws

'''

EXAMPLES = '''
- name: update/EXISTS [Lambda permission] 
    cd_lambda_permit:
        name: "{{ item.name }}"                 ##name of the APIv
        state: "{{ item.state }}"
        account: "{{ item.account }}"
        event_source: 
            - type: "s3"
              name: "mybucket"

    with_items: "{{ project.api_gw }}"

'''

from collections import defaultdict

try:
  import boto3
  from botocore.exceptions import ClientError, MissingParametersError, ParamValidationError
  HAS_BOTO3 = True

  from botocore.client import Config
except ImportError:
  import boto
  HAS_BOTO3 = False


def cd_permit_lambda(  module, client, name, event_source, account ):
  found=True
  id = "%s_%s" % (name, event_source['name'])
  # replace all non-alphanumeric characters with underscore
  id = re.sub('[^0-9a-zA-Z]+', '_', id)
  principle = 's3.amazonaws.com'
  s_arn = "arn:aws:s3:::%s" % event_source['name']
  cd_destroy( module, client, name, event_source, True)
  try:
    # content=
    response = client.add_permission(FunctionName=name,  StatementId=id,  Action='lambda:InvokeFunction',  
                    Principal=principle,  SourceArn=s_arn,  SourceAccount=account)
    found=False
  except ClientError as e:
    msg=e.response['Error']['Message']
    module.fail_json(msg="[E] add_permission [{1}] update_layer failed - {0}".format(msg,name))

  return [name], False if found else True

def cd_destroy( module, client, name, event_source, quite=False ):
  found = True
  id = "%s_%s" % (name, event_source['name'])
  id = re.sub('[^0-9a-zA-Z]+', '_', id)
  try:
    response=client.remove_permission(FunctionName=name, StatementId=id)
  except ClientError as e: 
    found=True
    name="%s, delete not possible "%name
    if quite:
        return True
  return [name], False if found else True





def main():
  argument_spec = ec2_argument_spec()
  argument_spec.update(dict(
    name =dict(required=True, default=None),  
    account = dict(required=True, default=None),     
    state =dict(required=True,  choices=['present','absent']),
    event_source =dict(required=True, default=None, type='dict'),
   
    )
  )


  module = AnsibleModule(  argument_spec=argument_spec,
                            supports_check_mode=True,
                            mutually_exclusive=[],  required_together=[]
  )

  # validate dependencies
  if not HAS_BOTO3:
    module.fail_json(msg='boto3 is required for this module.')
  try:
    region, endpoint, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
    aws_connect_kwargs.update(dict(region=region,
                                   endpoint=endpoint,
                                   conn_type='client',
                                   resource='lambda'
                              ))


    resource = None
    #ecr = boto3_conn(module, conn_type='client', resource='ecr', region=region, endpoint=endpoint, **aws_connect_kwargs)
    #module.fail_json(msg=" LOL cr_iam_profileo - {0}".format('iprofile'))
    client = boto3_conn(module, **aws_connect_kwargs)
    #resource=None
    #module.fail_json(msg=" LOL cr_iam_profileo - {0}".format('iprofile'))
  except botocore.exceptions.ClientError as e:
    module.fail_json(msg="Can't authorize connection - {0}".format(e))
  except Exception as e:
    module.fail_json(msg="Connection Error - {0}".format(e))
# check if trust_policy is present -- it can be inline JSON or a file path to a JSON file

  name = module.params.get('name')
  event_source = module.params.get('event_source')
  account = module.params.get('account')
  state = module.params.get('state')


  if 'absent' in state:
    typeList, changed=cd_destroy(module, client,name, event_source)
  else:
    typeList, changed= cd_permit_lambda( module, client, name, event_source, account )

  #has_changed, result = choice_map.get(module.params['state'])(module.params)
  has_changed=changed

  module.exit_json(changed=has_changed, entities=typeList)


# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()