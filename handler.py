# -*- coding: utf-8 -*-
# Copyright 2016 Ryan Brown <sb@ryansb.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This function creates a CFN stack from yesterday's production DB
snapshot and makes it available at 'dbname.yoursite.com'
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

cwd = os.path.dirname(os.path.abspath(__file__))


def handler(event, context):
    if not isinstance(event, dict):
        event = json.loads(event)

    log.debug("Received event {}".format(json.dumps(event)))

    if event.get('config') is None:
        cfg = json.load(open(os.path.join(cwd, 'config.json')))
    else:
        cfg = event.get('config')

    STACK_NAME = '{}-yesterdaytabase'.format(cfg['db']['name'])
    RESTORE_TO_NAME = '{}-{}'.format(cfg['db']['name'], datetime.datetime.utcnow().strftime('%Y-%m-%d-%H%M'))
    PRETTY_NAME = '{}-yesterday'.format(cfg['db']['name'])

    if event.get("action") == "delete":
        log.info("Got event {}, deleting stack".format(json.dumps(event)))
        try:
            cfn.delete_stack(StackName=STACK_NAME)
            return {"action": "delete", "error": None}
        except:
            log.exception("Could not delete stack {}".format(STACK_NAME))
            return {"action": "delete", "message": "Could not delete stack {}".format(STACK_NAME), "error": traceback.format_exc()}

    try:
        template = open(os.path.join(cwd, "template.yml")).read()
    except:
        log.exception("Failed to open `template.yml` file with IOError")
        return {"message": "Couldn't read CloudFormation template.", "error": traceback.format_exc()}


    snapshots = rds.describe_db_snapshots()["DBSnapshots"]
    db_snapshots = [snap for snap in snapshots
                      if snap["DBInstanceIdentifier"] == cfg['db']['name']]

    if not db_snapshots:
        return {"message": ("No matching DB snapshots - try again when there are"
                "snapshots for database {}").format(cfg['db']['name']),
                "error": "No DB snapshots", "action": event.get('action')}

    # get the most recent snapshot by sorting by date
    latest_snapshot = sorted(db_snapshots, reverse=True,
        key=lambda x: x["SnapshotCreateTime"])[0]
    identifier = latest_snapshot["DBSnapshotIdentifier"]

    stack_params = {
        "SnapshotID": identifier,
        "DiskSize": str(latest_snapshot["AllocatedStorage"]),
        "DomainRoot": cfg['domain'],
        "DBName": RESTORE_TO_NAME,
        "HostName": PRETTY_NAME,
        "SecurityGroup": cfg['db']['security_group'],
        "SubnetGroup": cfg['db']['subnet_group'],
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
