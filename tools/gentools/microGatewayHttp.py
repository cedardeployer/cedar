
import logging
import os
import boto3
from botocore.exceptions import ClientError


# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
# dir_path = os.path.dirname(__file__)
dir_path = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger(__name__)

class HttpGatewayMolder():
    origin = None

    temp = None

    def __init__(self):
        pass

    def getAuthorizations(self, client, api, position=None):
        rlist = []
        if position is None:
            response = client.get_authorizers(ApiId=api, MaxResults='100')
        else:
            response = client.get_authorizers(ApiId=api, NextToken=position, MaxResults='100')
        baseList = response['Items']
        if "position" in response:
            rlist = self.getAuthorizations(client, api, response['NextToken'])
        final = baseList + rlist
        return final

    def getIntegrations(self, client, api, position=None):
        rlist = []
        if position is None:
            response = client.get_integrations(ApiId=api, MaxResults='100')
        else:
            response = client.get_integrations(ApiId=api, NextToken=position, MaxResults='100')
        baseList = response['Items']
        if "position" in response:
            rlist = self.getIntegrations(client, api, response['NextToken'])
        final = baseList + rlist
        return final

    def getIntegration(self, client, apID, id):
        response = client.get_integration(ApiId=apID,  IntegrationId=id )
        return response
    # def integration_response(self, client, api, )

    def getRoutes(self, client, api, position=None):
        rlist = []
        if position is None:
            response = client.get_routes(ApiId=api, MaxResults='100')
        else:
            response = client.get_routes(ApiId=api, NextToken=position, MaxResults='100')
        baseList = response['Items']
        if "position" in response:
            rlist = self.getRoutes(client, api, response['NextToken'])
        final = baseList + rlist
        return final

    def getALL_http_apis(self, client, position=None):
        rlist = []
        if position is None:
            response = client.get_apis(MaxResults='100')
        else:
            response = client.get_apis(NextToken=position, MaxResults='100')
        baseList = response['Items']
        if "position" in response:
            rlist = self.getALL_http_apis(client, response['NextToken'])
        final = baseList + rlist
        return final

    def describe_gateway(self, resourceNname, resourceType, aconnect, resourceRole=None, targetAPI=None):
        pass

if __name__ == "__main__":
    client = boto3.client('apigatewayv2')
    api = "xmgihcfiag"

    hp = HttpGatewayMolder()
    result = hp.getIntegrations(client, api)
    print(" -- integrations -BEGIN-")
    # print(result)
    for intg in result:
        resultIn = hp.getIntegration(client, api, intg['IntegrationId'])
        print(resultIn)
    print(" -- integrations -END-")
    result = hp.getRoutes(client, api)
    print(" -- routes -BEGIN-")
    print(result)
    print(" -- routes -END-")









        