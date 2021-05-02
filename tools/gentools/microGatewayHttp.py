
import logging
import os

from botocore.exceptions import ClientError


# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
# dir_path = os.path.dirname(__file__)
dir_path = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger(__name__)

class HttpGatewayMolder():
    origin = None

    temp = None

    def __init__(self, directory, islambda=False):
        pass



    def getALL_http_apis(self, client, position=None):
        rlist = []
        if position is None:
            response = client.get_rest_apis(MaxResults=500)
        else:
            response = client.get_rest_apis(NextToken=position, MaxResults=500)
        baseList = response['Items']
        if "position" in response:
            rlist = self.getALL_http_apis(client, response['NextToken'])
        final = baseList + rlist
        return final



        