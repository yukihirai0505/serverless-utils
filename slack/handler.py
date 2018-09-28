# import datetime
import copy
import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.request import Request, urlopen

SLACK_CHANNEL = os.environ.get('SLACK_CHANNEL', "")
HOOK_URL = "https://" + os.environ.get('HOOK_URL', "")
BASE_SLACK_MESSAGE = {
    'channel': SLACK_CHANNEL
}

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
# local debug
handler = logging.StreamHandler()
handler.setLevel(level=logging.DEBUG)
logger.addHandler(handler)

JST = timezone(timedelta(hours=+9), 'JST')


class DateTimeSupportJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super(DateTimeSupportJSONEncoder, self).default(o)


def handle_codedeploy(sns, context):
    sns_message = sns['Message']
    logger.info("CodeDeploy: " + json.dumps(sns_message, cls=DateTimeSupportJSONEncoder))

    _subject = sns['Subject']
    _region = sns_message['region']
    _account_id = sns_message['accountId']
    _deployment_id = sns_message['deploymentId']
    _link = "https://{region}.console.aws.amazon.com/codedeploy/home?region={region}#/deployments/{deployment_id}" \
        .format(region=_region, deployment_id=_deployment_id)
    _color = None

    slack_message = {
        "username": "aws-codedeploy",
        "icon_emoji": ":whale:",
        'attachments': []
    }
    fields = []

    if 'instanceId' in sns_message:
        # instance event
        fields = []
        _instance_id = sns_message['instanceId']
        _last_updated_at = sns_message['lastUpdatedAt']
        _instance_status = sns_message['instanceStatus']
        _lifecycle_events = sns_message['lifecycleEvents']

        if _instance_status == "Succeeded":
            _color = "good"
        elif _instance_status == "Failed":
            _color = "danger"

        fields.append({
            "title": 'InstanceId', "value": sns_message.get('instanceId'), "short": "true"
        })
        fields.append({
            "title": 'InstanceStatus', "value": sns_message.get('instanceStatus'), "short": "true"
        })
        if sns_message.get('lifecycleEvents'):
            lifecycle_ev = json.loads(sns_message.get('lifecycleEvents'))

        slack_message['attachments'] = [
            {
                "fallback": _subject,
                'color': _color,
                "pretext": "AWS CodeDeploy Notification",
                "title": "Deployment: {}".format(_deployment_id),
                "title_link": _link,
                "text": _subject,
                "fields": fields,
                "mrkdwn_in": ["fields"]
            }
        ]
    else:
        # deployment event
        _status = sns_message['status']

        fields.append({
            "title": 'Application', 'value': sns_message.get('applicationName'), "short": "true"
        })
        fields.append({
            "title": 'DeploymentGroup', 'value': sns_message.get('deploymentGroupName'), "short": "true"
        })
        fields.append({
            "title": 'Status', 'value': _status, "short": "true"
        })

        if _status == 'SUCCEEDED':
            _color = "good"
        elif _status == 'ABORTED' or _status == 'FAILED':
            _color = "danger"

        if sns_message.get('deploymentOverview'):
            dep_ov = json.loads(sns_message.get('deploymentOverview'))
            dep_ov_text = "Succeeded:{}, Failed:{}, InProgress:{}, Pending:{}"
            fields.append({
                "title": "DeploymentOverview",
                "value": dep_ov_text.format(dep_ov.get('Succeeded'),
                                            dep_ov.get('Failed'),
                                            dep_ov.get('InProgress'),
                                            dep_ov.get('Pending')),
                "short": "false"
            })

        if sns_message.get('errorInformation'):
            error_info = json.loads(sns_message.get('errorInformation'))
            fields.append({
                "title": 'ErrorCode', 'value': error_info.get('ErrorCode'), "short": "true"
            })
            fields.append({
                "title": 'ErrorMessage', 'value': error_info.get('ErrorMessage'), "short": "false"
            })

        _create_time = datetime.strptime(sns_message['createTime'], "%a %b %d %H:%M:%S %Z %Y") \
            .replace(tzinfo=timezone.utc) \
            .astimezone(tz=JST)
        _complete_time = sns_message.get('completeTime')
        if _complete_time:
            _complete_time = datetime.strptime(_complete_time, "%a %b %d %H:%M:%S %Z %Y") \
                .replace(tzinfo=timezone.utc) \
                .astimezone(tz=JST)

        slack_message['attachments'] = [
            {
                "fallback": _subject,
                'color': _color,
                "pretext": "AWS CodeDeploy Notification",
                "title": "Deployment: {}".format(_deployment_id),
                "title_link": _link,
                "text": _subject,
                "fields": fields,
                "mrkdwn_in": ["fields"]
            }
        ]

    slack_message.update(BASE_SLACK_MESSAGE)
    return slack_message


def handle_asg(sns, context):
    sns_message = sns['Message']
    logger.info("AutoScaling: " + json.dumps(sns_message, cls=DateTimeSupportJSONEncoder))

    _subject = sns['Subject']

    _description = sns_message.get('Description')
    _region = str(sns_message['AutoScalingGroupARN']).split(":")[3]
    _asg_event = sns_message['Event']
    _asg_name = sns_message['AutoScalingGroupName']

    if re.search(r"EC2_INSTANCE_LAUNCH_ERROR|EC2_INSTANCE_TERMINATE_ERROR", _asg_event):
        _color = "danger"
    elif re.search(r"EC2_INSTANCE_LAUNCH|EC2_INSTANCE_TERMINATE", _asg_event):
        _color = "good"
    else:
        _color = "warning"

    _link = "https://{region}.console.aws.amazon.com/ec2/autoscaling/home?region={region}#AutoScalingGroups:id={asg};view=history" \
        .format(region=_region, asg=_asg_name)

    fields = []
    fields.append({
        "title": 'AutoScalingGroupName', "value": _asg_name, "short": "true"
    })
    fields.append({
        "title": 'Event', "value": _asg_event, "short": "true"
    })
    if sns_message.get('StatusCode'):
        fields.append({
            "title": "StatusCode", "value": sns_message.get('StatusCode'), "short": "true"
        })
    if sns_message.get('StatusMessage'):
        fields.append({
            "title": "StatusMessage", "value": sns_message.get('StatusMessage'), "short": "false"
        })

    slack_message = {
        "username": "aws-autoscaling",
        "icon_emoji": ":robot_face:",
        'attachments': [
            {
                "fallback": _subject,
                'color': _color,
                "pretext": "AWS AutoScaling Notification",
                "title": _subject,
                "title_link": _link,
                "text": _description,
                "fields": fields,
                "mrkdwn_in": ["fields"]
            },
            {
                'color': _color,
                "fields": [
                    {
                        "title": "Cause", "value": "{}".format(sns_message.get('Cause')), "short": "false"
                    }
                ],
                "mrkdwn_in": ["fields"]
            }
        ]
    }
    slack_message.update(BASE_SLACK_MESSAGE)
    return slack_message


def process_event(event, context):
    sns = event['Records'][0]['Sns']
    sns_message = json.loads(sns['Message'])
    # replace message from json to dict
    _sns = copy.deepcopy(sns)
    _sns['Message'] = sns_message
    # convert from utc to jst
    _sns['Timestamp'] = datetime.strptime(_sns['Timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ") \
        .replace(tzinfo=timezone.utc) \
        .astimezone(tz=JST)

    slack_message = {}
    if "AutoScalingGroupARN" in _sns['Message']:
        slack_message = handle_asg(_sns, context)
    elif "deploymentId" in _sns['Message']:
        slack_message = handle_codedeploy(_sns, context)
    else:
        logger.warning("Unsupported sns")

    post_data = json.dumps(slack_message, indent=4)
    logger.debug("post data:\n" + post_data)
    req = Request(url=HOOK_URL, data=post_data.encode("utf-8"), method='POST')
    try:
        response = urlopen(req)
        logger.info("Message posted to %s", slack_message['channel'])
    except HTTPError as e:
        logger.error("Request failed: %d %s", e.code, e.reason)
    except URLError as e:
        logger.error("Server connection failed: %s", e.reason)


def notify(event, context):
    logger.info("Event: " + json.dumps(event))
    process_event(event, context)
