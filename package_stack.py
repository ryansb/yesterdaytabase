#!/usr/bin/env python2
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

import json
import boto3

session = boto3.Session(profile_name='personal')
s3 = session.client('s3')

BUCKET = 'demos.serverlesscode.com'
PREFIX = 'pub/lambda/yesterdaytabase/'


def munge_template():
    template = json.load(open('.serverless/cloudformation-template-update-stack.json'))

    template['Resources'].pop('ServerlessDeploymentBucket')
    template['Outputs'].pop('ServerlessDeploymentBucketName')

    # Instead, get the Lambda function from the serverlesscode distribution bucket
    template['Resources']['DbManagerLambdaFunction']['Properties']['Code'] = {
        'S3Bucket': BUCKET,
        'S3Key': PREFIX + 'code.zip',
    }

    # rename function since it's the only one in the package
    #template['Resources']['DbManagerLambdaFunction']['Properties']['FunctionName'] = 'yesterdaytabase'
    #template['Resources']['DbManagerLogGroup']['Properties']['LogGroupName'] = '/aws/lambda/yesterdaytabase'

    #template['Resources']['IamPolicyLambdaExecution']['DependsOn'] = ['DbManagerLogGroup', 'DbManagerLambdaFunction']

    # Add a parameter so the user can supply an event that includes the DB name, domain, and other config
    template['Resources']['DbManagerEventsRuleSchedule1']['Properties']['Targets'][0]['Input'] = {'Ref': 'SourceConfiguration'}
    template['Parameters'] = {
        'SourceConfiguration': {
            'Type': 'String',
            'Description': 'The configuration values to invoke the DB config with, see https://github.com/ryansb/yesterdaytabase for full docs',
            'Default': json.dumps(
                {
                    "config": {
                        "domain": "mysite.com",
                        "db": {
                            "name": "my-rds-dbname",
                            "security_group": "sg-12345678",
                            "subnet_group": "net-group-12345678"
                            }
                        }
                    }
                )
            }
        }

    template['Description'] = "Deploy the `yesterdaytabase` Lambda function to build new instances daily from fresh snapshots"
    return template


def upload_zip(sha):
    s3.put_object(
        ACL='public-read',
        Bucket=BUCKET,
        Key=PREFIX + 'code.zip',
        ContentType='application/zip',
        Metadata={'GitVersion': sha},
        Body=open('.serverless/yesterdaytabase.zip')
    )


def upload_template(sha, template):
    s3.put_object(
        ACL='public-read',
        Bucket=BUCKET,
        Key=PREFIX + 'template.json',
        ContentType='application/json',
        Metadata={'GitVersion': sha},
        Body=json.dumps(template, indent=2)
    )


def get_sha():
    import subprocess
    sha = subprocess.check_output('git rev-parse HEAD'.split(' ')).strip()
    if len(subprocess.check_output('git diff --shortstat'.split(' '))):
        sha += '-dirty'
    return sha


if __name__ == '__main__':
    upload_zip(get_sha())
    template = munge_template()
    upload_template(get_sha(), template)
    open('out.json', 'w').write(json.dumps(template, indent=2))

