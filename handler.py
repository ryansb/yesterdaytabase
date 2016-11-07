# -*- coding: utf-8 -*-
# Author: Ryan Brown <sb@ryansb.com>

"""
This function creates a CFN stack from yesterday's production DB
snapshot and makes it available at 'dev-yesterday-db.clearviewsocial.com'
"""

from __future__ import print_function

import boto3
import botocore
import datetime
import json
import logging
import os
import traceback

log = logging.getLogger()
log.setLevel(logging.DEBUG)

rds = boto3.client('rds')
cfn = boto3.client('cloudformation')

DB_NAME = 'ryansb-psql-prod'
STACK_NAME = '{}-yesterdaytabase'.format(DB_NAME)
DOMAIN = 'ryansb.com'
RESTORE_TO_NAME = '{}-yesterday-{}'.format(DB_NAME, datetime.datetime.utcnow().strftime('%Y-%m-%d-%H%M'))
PRETTY_NAME = '{}-yesterday'.format(DB_NAME)
DB_SECURITY_GROUP = 'sg-461bcf3b'
DB_SUBNET_GROUP = 'default-vpc-3a9a805d'


def handler(event, context):
    if event.get("action") == "delete":
        log.info("Got event {}, deleting stack".format(json.dumps(event)))
        try:
            cfn.delete_stack(StackName=STACK_NAME)
            return {"action": "delete", "error": None}
        except:
            log.exception("Could not delete stack {}".format(STACK_NAME))
            return {"action": "delete", "message": "Could not delete stack {}".format(STACK_NAME), "error": traceback.format_exc()}


    try:
        directory = os.path.dirname(os.path.abspath(__file__))
        template = open(os.path.join(directory, "template.yml")).read()
    except:
        log.exception("Failed to open `template.yml` file with IOError")
        return {"message": "Couldn't read CloudFormation template.", "error": traceback.format_exc()}

    log.debug("Received event {}".format(json.dumps(event)))

    snapshots = rds.describe_db_snapshots()["DBSnapshots"]
    db_snapshots = [snap for snap in snapshots
                      if snap["DBInstanceIdentifier"] == DB_NAME]

    # get the most recent snapshot by sorting by date
    latest_snapshot = sorted(db_snapshots, reverse=True,
        key=lambda x: x["SnapshotCreateTime"])[0]
    identifier = latest_snapshot["DBSnapshotIdentifier"]

    stack_params = {
        "SnapshotID": identifier,
        "DiskSize": str(latest_snapshot["AllocatedStorage"]),
        "DomainRoot": DOMAIN,
        "DBName": RESTORE_TO_NAME,
        "HostName": PRETTY_NAME,
        "SecurityGroup": DB_SECURITY_GROUP,
        "SubnetGroup": DB_SUBNET_GROUP,
    }

    cfn_params = dict(
        StackName=STACK_NAME,
        TemplateBody=template,
        Parameters=[{"ParameterKey": k, "ParameterValue": v} for k, v in stack_params.items()]
    )

    if event.get("action", "create") in ["create", "update"]:
        try:
            stacks = cfn.describe_stacks(StackName=STACK_NAME)
        except botocore.exceptions.ClientError as exc:
            if 'does not exist' in exc.message:
                cfn.create_stack(**cfn_params)
                return {"action": "create", "error": None, "stack_args": cfn_params}
        else:
            if stacks["Stacks"][0]["StackStatus"].endswith("COMPLETE"):
                # stack can be updated
                cfn.update_stack(**cfn_params)
                return {"action": "update", "error": None, "stack_args": cfn_params}
            else:
                msg = "Stack %s is in state %s and cannot be updated" % (STACK_NAME, stacks["Stacks"][0]["StackStatus"])
                log.error(msg)
                return {"action": "update", "message": msg, "error": True, "stack_args": cfn_params}

    return {"action": None, "stack_args": cfn_params}
