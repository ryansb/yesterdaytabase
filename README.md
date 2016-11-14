# Yesterdaytabase

Yesterdaytabase is a Lambda function that pulls previous snapshots of RDS
databases for use as staging or testing environments. The function runs on a
schedule and recreates the DB with a CloudFormation stack.

## Usage

If you only have one database, launch the stack and fill in the
`SourceConfiguration` value with a one-line JSON object. The config is in this
format:

```
{
  "config": {
    "domain": "mysite.com", # the root of your Route53 zone
    "db": {
      "name": "my-rds-dbname",
      "security_group": "sg-12345678",
      "subnet_group": "net-group-12345678" # the RDS subnet group to launch the DB in
    }
  }
}
```

For more databases, create more CloudWatch Event rules that have the same JSON
format in their input field.

## Run it

Want to run it? Launch it and go. <a style="text-decoration: none" href="https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/new?stackName=yesterdaytabase&amp;templateURL=https://s3.amazonaws.com/demos.serverlesscode.com/pub%2flambda%2fyesterdaytabase%2ftemplate.json">
  <img style="height: 1em" src="https://serverlesscode.com/img/cloudformation-launch-stack.png" alt="Launch stack yesterdaytabase">
</a> Fill in the database you've got snapshots of and your Route53 domain.
