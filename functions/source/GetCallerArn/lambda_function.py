import logging
import json
from datetime import timedelta
from time import sleep
import boto3
from crhelper import CfnResource

logger = logging.getLogger(__name__)
helper = CfnResource(json_logging=True, log_level='DEBUG')

try:
    cfn_client = boto3.client('cloudformation')
    ct_client = boto3.client('cloudtrail')
except Exception as init_exception:
    helper.init_failure(init_exception)


def get_caller_arn(stack_id):
    stack_properties = cfn_client.describe_stacks(StackName=stack_id)['Stacks'][0]
    try:
        parent_id = [t for t in stack_properties['Tags'] if t['Key'] == 'ParentStackId'][0]['Value']
    except ValueError:
        return "NotFound"
    except IndexError:
        return "NotFound"
    root_id = parent_id
    try:
        root_id = cfn_client.describe_stacks(StackName=parent_id)['Stacks'][0]['RootId']
    except ValueError:
        pass
    create_time = cfn_client.describe_stacks(StackName=root_id)['Stacks'][0]['CreationTime']
    retries = 50
    while True:
        retries -= 1
        try:
            response = ct_client.lookup_events(
                LookupAttributes=[
                    {'AttributeKey': 'ResourceName', 'AttributeValue': root_id},
                    {'AttributeKey': 'EventName', 'AttributeValue': 'CreateStack'}
                ],
                StartTime=create_time - timedelta(minutes=15),
                EndTime=create_time + timedelta(minutes=15)
            )
            if len(response['Events']) > 0:
                return json.loads(response['Events'][0]['CloudTrailEvent'])['userIdentity']['arn']
            logger.info('Event not in cloudtrail yet, %s retries left' % str(retries))
        except Exception as e:
            logger.error(str(e), exc_info=True)
        if retries == 0:
            return "NotFound"
        sleep(15)


@helper.create
def create(event, _):
    helper.Data['Arn'] = get_caller_arn(event['StackId'])
    return helper.Data['Arn'].split('/')[1]


def lambda_handler(event, context):
    helper(event, context)