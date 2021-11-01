#!/usr/bin/python


DOCUMENTATION = '''
---
module: lambda_update
short_description: create/update api gateway as needed.
description:
    - This module allows the user to update a Lambda. This module has a dependency on python-boto.
version_added: "1.1"
options:
  function_name:
    description:
      - AWS Lambda name.
    required: true
    default: null
  file_config:
    description:
      - AWS lambda file configuration for mounting EFS.
    required: false
    default: null
    aliases: ['ec2_secret_key', 'secret_key']
  image_config:
    description:
      - docker image needed to load into lambda.
    required: false
    default: null
    aliases: []
  layers:
    description:
      - layers used for lambda function.
    required: false


'''

EXAMPLES = '''
- name: delete Model
  lambda_update:
    function_name: X
    layers: [fdafdsa,fdasfdsafd]
    restApiId: 0000000000
    aws_access_key: "{{ access }}"
    aws_secret_key: "{{ secret }}"
    security_token: "{{ token }}"
    region: "{{project.region}}"
- name: add/update Model
  lambda_update:
    function_name: X
    apiName: xx
    restApiId: 0000000000
    schema: '{\n  "type" : "string",\n  "enum" : [ "dog", "cat", "fish", "bird", "gecko" ]\n}'
    contentType: application/json
    aws_access_key: "{{ access }}"
    aws_secret_key: "{{ secret }}"
    security_token: "{{ token }}"
    region: "{{project.region}}"
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

#


def our_lambda_update(module, client, function_name, layers=None, file_config=None, image_config=None):
    pName = function_name
    found = True
    if layers:
        response = client.update_function_configuration(FunctionName=function_name, Layers=layers)
    elif layers:
        response = client.update_function_configuration(FunctionName=function_name, FileSystemConfigs=file_config)
    elif layers:
        response = client.update_function_configuration(FunctionName=function_name, ImageConfig=image_config)
    return [pName], False if found else True


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        function_name=dict(required=True, default=None),  # name of the API
        layers=dict(required=False, default=None, type='list'),
        file_config=dict(required=False, default=None, type='list'),
        image_config=dict(required=False, default=None, type='dict')
    )
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True, mutually_exclusive=[], required_together=[])

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
        # ecr = boto3_conn(module, conn_type='client', resource='ecr', region=region, endpoint=endpoint, **aws_connect_kwargs)
        # module.fail_json(msg=" LOL cr_iam_profileo - {0}".format('iprofile'))
        client = boto3_conn(module, **aws_connect_kwargs)
        # resource=None
        # module.fail_json(msg=" LOL cr_iam_profileo - {0}".format('iprofile'))
    except botocore.exceptions.ClientError as e:
        module.fail_json(msg="Can't authorize connection - {0}".format(e))
    except Exception as e:
        module.fail_json(msg="Connection Error - {0}".format(e))
        # check if trust_policy is present -- it can be inline JSON or a file path to a JSON file

    function_name = module.params.get('function_name')
    layers = module.params.get('layers')
    file_config = module.params.get('file_config')
    image_config = module.params.get('image_config')

    typeList, changed = our_lambda_update(module, client, function_name, layers, file_config, image_config)

    # has_changed, result = choice_map.get(module.params['state'])(module.params)
    has_changed = changed

    module.exit_json(changed=has_changed, entities=typeList)


# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()
