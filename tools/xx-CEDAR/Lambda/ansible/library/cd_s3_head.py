#!/usr/bin/python
# (c) 2020, Robert Colvin <rcolvinemail@gmail.com>
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

from ansible.module_utils.ec2 import *
from ansible.module_utils.basic import *
import sys
import copy
import json
from hashlib import md5

try:
    import boto3
    from botocore.exceptions import ClientError, ParamValidationError, MissingParametersError
    HAS_BOTO3 = True
except ImportError:
    import boto              # seems to be needed for ansible.module_utils
    HAS_BOTO3 = False


DOCUMENTATION = '''
---
module: cd_s3_head
short_description: retrieves the head of an existing S3 object.
description:
    - This module allows the read of keys from S3 bucket.
version_added: "2.1"
author: Robert Colvin
options:
  bucket: bucket name
  key: key of object in bucket
requirements:
    - boto3
extends_documentation_fragment:
    - aws

'''

EXAMPLES = '''
---
# Simple example that retrieves headers of key on an S3 bucket
  - name: Lambda invoke from s3 for preview
    lambda_event:
      bucket: my-bucket-name
      key: path/to/somefile.pdf

'''

RETURN = '''
---
cd_s3_head:
    description: dict of object header for key found
    returned: success
    type: dict


'''

# ---------------------------------------------------------------------------------------------------
#
#   Helper Functions & classes
#
# ---------------------------------------------------------------------------------------------------


def cd_header(module, client, bucket, key):
    found = False
    try:
        head = client.head_object(Bucket='beto-dev-portal', Key='ssbean.gif')
    except ClientError as e:
        module.fail_json(msg='Lambda[%s] ENV update failed %s' % (key, e))

    return [head], False if found else True


# ---------------------------------------------------------------------------------------------------
#
#   MAIN
#
# ---------------------------------------------------------------------------------------------------


def main():
    """
    Main entry point.

    :return dict: ansible facts
    """
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(

        bucket=dict(required=True, default=None, type='str'),
        key=dict(required=True, default=None, type='str'),

    )
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        mutually_exclusive=[],
        required_together=[]
    )
    # validate dependencies
    if not HAS_BOTO3:
        module.fail_json(msg='boto3 is required for this module.')
    try:
        region, endpoint, aws_connect_kwargs = get_aws_connection_info(
            module, boto3=True)
        aws_connect_kwargs.update(dict(region=region,
                                       endpoint=endpoint,
                                       conn_type='client',
                                       resource='s3'
                                       ))

        # resource = None
        client = boto3_conn(module, **aws_connect_kwargs)
    except botocore.exceptions.ClientError as e:
        module.fail_json(msg="Can't authorize connection - {0}".format(e))
    except Exception as e:
        module.fail_json(msg="Connection Error - {0}".format(e))
# check if trust_policy is present -- it can be inline JSON or a file path to a JSON file

    bucket = module.params.get('bucket')
    key = module.params.get('key')

    header, has_changed = cd_header(module, client, bucket, key)

    module.exit_json(changed=has_changed, entities=header)


# ansible import module(s) kept at ~eof as recommended


if __name__ == '__main__':
    main()
